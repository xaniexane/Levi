"""Zero-config quickstart for the Cybrus standalone product.

One call: master password in, vault initialized, first credential generated,
stored encrypted, and verified by round-trip — with a receipt.

Secrets discipline (law):
  - The master password comes from the explicit argument, the
    ``CYBRUS_MASTER_PASSWORD`` env var, or a getpass prompt (TTY only).
    It is NEVER taken via argv and NEVER printed or logged.
  - The generated credential password is returned in the receipt dict for
    the caller to show exactly once; this module never prints it.
  - Tests use a throwaway passphrase in a tmp home — never a real secret.

Homes:
  - ``CYBRUS_HOME`` env var wins (hermetic tests, bundles).
  - Otherwise the engine default (``~/.levi/cybrus/``, ``LEVI_HOME``
    override honored) — the standalone product opens the same vault the
    engine uses, so nothing is duplicated.
"""

from __future__ import annotations

import getpass
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ENV_HOME = "CYBRUS_HOME"
ENV_MASTER = "CYBRUS_MASTER_PASSWORD"


def product_home(home: Optional[Path] = None) -> Path:
    """Product home: ``home`` wins, then CYBRUS_HOME, then ~/.levi/cybrus/."""
    if home is not None:
        return Path(home)
    env = os.environ.get(ENV_HOME, "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".levi" / "cybrus"


def _vault_kwargs(home: Optional[Path] = None) -> Dict[str, Any]:
    """Vault constructor kwargs for the product home.

    One vault everywhere: when the product is isolated (CYBRUS_HOME /
    explicit home), the engine's ``LEVI_HOME`` convention is routed at the
    product home so quickstart AND the broker open the same vault.
    Otherwise the engine default is used untouched.
    """
    if home is not None or os.environ.get(ENV_HOME, "").strip():
        os.environ.setdefault("LEVI_HOME", str(product_home(home)))
    return {}


def resolve_master_password(explicit: Optional[str] = None) -> str:
    """Resolve the master password without ever echoing it.

    Precedence: explicit argument -> CYBRUS_MASTER_PASSWORD -> getpass
    prompt (TTY only; raises in non-interactive use without a source).
    """
    if explicit:
        return explicit
    env = os.environ.get(ENV_MASTER, "")
    if env:
        return env
    if sys.stdin.isatty():
        pw = getpass.getpass("Cybrus master password: ")
        if not pw:
            raise ValueError("master password required")
        return pw
    raise ValueError(
        "no master password: pass one explicitly, set "
        f"{ENV_MASTER}, or run on a TTY"
    )


def quickstart(
    service: str,
    username: str,
    master_password: Optional[str] = None,
    home: Optional[Path] = None,
    password_length: int = 24,
) -> Dict[str, Any]:
    """Run the zero-config quickstart. Returns a receipt dict.

    Steps: layout -> vault init -> generate -> store -> verify.
    The generated password is in ``receipt["credential"]["password"]`` —
    the caller shows it exactly once and never logs it.
    """
    from levi.cybrus.product import PRODUCT_NAME, PRODUCT_VERSION, price_line
    from levi.cybrus.vault import CredentialVault, generate_password

    started = time.monotonic()
    steps: List[Dict[str, Any]] = []
    home_path = product_home(home)

    def step(name: str, detail: str) -> None:
        steps.append({"name": name, "detail": detail})

    service = service.strip()
    username = username.strip()
    if not service or not username:
        raise ValueError("quickstart needs a service and a username")
    pw = resolve_master_password(master_password)

    # 1. layout
    home_path.mkdir(parents=True, exist_ok=True)
    os.chmod(home_path, 0o700)
    step("layout", f"product home ready at {home_path}")

    # 2. vault init (creates salt on first run; unlocks after)
    vault = CredentialVault(pw, **_vault_kwargs(home))
    step("vault-init", f"vault unlocked (backend: {vault.backend})")

    # 3. generate
    generated = generate_password(password_length)
    step("generate", f"{password_length}-char password generated locally")

    # 4. store
    vault.store(service, username, generated)
    step("store", f"credential stored encrypted for {service} / {username}")

    # 5. verify round-trip
    retrieved = vault.get(service, username)
    if retrieved != generated:
        raise RuntimeError("vault round-trip mismatch — refusing to continue")
    step("verify", "round-trip verified: stored secret decrypts correctly")

    finished = time.monotonic()
    return {
        "product": PRODUCT_NAME,
        "version": PRODUCT_VERSION,
        "home": str(home_path),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(finished - started, 3),
        "steps": steps,
        "credential": {
            "service": service,
            "username": username,
            # Shown exactly once by the caller. Never logged.
            "password": generated,
        },
        "vault_backend": vault.backend,
        "price": price_line(),
    }


def status(
    home: Optional[Path] = None, master_password: Optional[str] = None
) -> Dict[str, Any]:
    """Smoke-check the product home. Unlocks the vault only when a master
    password is available (explicit arg or CYBRUS_MASTER_PASSWORD)."""
    from levi.cybrus.product import PRODUCT_NAME, PRODUCT_VERSION

    home_path = product_home(home)
    report: Dict[str, Any] = {
        "product": PRODUCT_NAME,
        "version": PRODUCT_VERSION,
        "home": str(home_path),
        "home_exists": home_path.exists(),
        "vault_unlocked": False,
        "vault_backend": None,
        "stored_services": [],
        "ok": False,
    }
    pw = master_password or os.environ.get(ENV_MASTER, "")
    if pw:
        try:
            from levi.cybrus.vault import CredentialVault

            vault = CredentialVault(pw, **_vault_kwargs(home))
            report["vault_unlocked"] = True
            report["vault_backend"] = vault.backend
            report["stored_services"] = vault.list_services()
        except Exception as exc:  # wrong password, corrupt store, ...
            report["vault_error"] = f"{type(exc).__name__}"
    report["ok"] = bool(report["home_exists"])
    return report
