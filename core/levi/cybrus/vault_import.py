"""Bulk CSV importer for the Cybrus credential vault (LEVI-original).

Imports Google Password Manager exports (``name,url,username,password,note``)
into :class:`levi.cybrus.vault.CredentialVault`, encrypted at rest. The
source CSV is NEVER modified — only read.

LAWS (invariants; the test module is the machine-checkable proof gate —
never called "formal proof"):

  L1 no-leak:        ``import_google_csv`` returns only counts. It never
                     logs, prints, or raises messages containing passwords,
                     usernames, or URLs. Errors name row numbers and
                     reasons, never values.
  L2 encrypted-rest: secrets reach disk only through
                     ``CredentialVault``'s encrypted blob. This module
                     performs no direct file writes of secrets.
  L3 atomic-batch:   every row is validated before any write happens. An
                     unreadable CSV or missing required columns raises
                     ``CsvImportError`` and the vault is left untouched. One
                     lock-held write pass applies all valid rows.
  L4 keep-first:     for a duplicate ``(service, username)`` — already in
                     the vault or repeated within the CSV — the FIRST value
                     wins. The row is counted as ``duplicates``, never
                     overwritten.
  L5 safe-names:     every service/username is canonicalized to
                     ``[A-Za-z0-9._-]``, 1-64 chars, deterministically.
                     Rows that cannot yield a valid pair are counted
                     ``invalid`` — never stored raw.
  L6 local-only:     no network, no subprocess, no external sends.
  L7 saf-honesty:     ``pick_saf_folder`` never fabricates a directory. It
                     returns only (a) the operator-supplied
                     ``CYBRUS_SAF_DIR`` when it exists and is a readable
                     directory, (b) a path returned by the host-registered
                     SAF picker bridge, or (c) raises
                     ``SafNotAvailableError``. The system folder-picker UI
                     itself can only run on the Android runtime — this
                     module provides the integration point, not the UI —
                     so on other runtimes without a bridge it refuses
                     loudly instead of silently substituting a path.
  L8 no-silent-overwrite:
                     no public function in this module creates or truncates
                     a file at a path that already exists without an
                     explicit ``overwrite=True`` opt-in. The refusal is an
                     ``OverwriteRefusedError`` (a ``FileExistsError``)
                     naming the path — never secret values. (Vault
                     overwrites are additionally impossible: L4 keep-first
                     means an import never replaces an existing entry.)
  L9 honest-report:   the report dict keys are pinned (L1 consumers depend
                     on them); the human-readable report from
                     ``describe_import`` always states ``no changes
                     applied`` explicitly when zero rows were imported,
                     instead of looking like a silent success.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import getpass
import hashlib
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from levi.cybrus._paths import store_lock
from levi.cybrus.vault import CredentialVault, VaultError

_REQUIRED_COLUMNS = ("name", "url", "username", "password")
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_INVALID_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]")
_MAX_NAME_LEN = 64

#: Operator override for the SAF folder picker: a pre-authorized directory.
#: Used only when it exists and is a readable directory; a bad value
#: raises ``SafNotAvailableError`` instead of falling back silently (L7).
SAF_ENV_DIR = "CYBRUS_SAF_DIR"


class CsvImportError(Exception):
    """The CSV itself is unusable: unreadable, undecodable, or missing
    required columns. The vault is untouched when this is raised."""


class SafNotAvailableError(Exception):
    """No SAF folder picker is available on this runtime.

    The Android Storage Access Framework picker UI can only run on the
    Android runtime. This error means neither a host picker bridge was
    registered (see :func:`register_saf_picker`) nor a usable
    ``CYBRUS_SAF_DIR`` was supplied — so the import refuses rather than
    guessing a directory (L7)."""


class OverwriteRefusedError(FileExistsError):
    """A write was refused because the target file already exists and no
    explicit ``overwrite=True`` opt-in was given (L8). A ``FileExistsError``
    subclass so existing ``OSError`` handling keeps working."""


def _canonical_service(url: str) -> str:
    """Map a URL to a vault-safe service name.

    Preferred: the URL host, lowercased, when it is a plausible hostname
    (``[A-Za-z0-9._-]+``); truncated to 64 chars. Anything else — missing
    URL, unparsable host, whitespace or exotic syntax — falls back to the
    deterministic ``csv-import-<sha1(url)[:12]>`` so garbage can never
    become a misleading service name.
    """
    host = ""
    text = (url or "").strip()
    if text:
        # urlsplit needs a scheme to find the host; Google rows always
        # carry one, but be tolerant of bare hosts.
        candidate = text if "://" in text else "https://" + text
        try:
            from urllib.parse import urlsplit

            host = (urlsplit(candidate).hostname or "").lower()
        except ValueError:
            host = ""
    # Only plausible hostnames are used directly; anything else (spaces,
    # userinfo remnants, exotic syntax) falls back to the deterministic
    # hash form so garbage can never become a misleading service name.
    if host and re.fullmatch(r"[A-Za-z0-9._-]+", host):
        cleaned = host[:_MAX_NAME_LEN]
        if _NAME_RE.match(cleaned):
            return cleaned
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return "csv-import-" + digest


def _canonical_username(username: str) -> Optional[str]:
    """Canonicalize a CSV username. ``@`` -> ``_at_`` (readable, reversible
    in spirit), other invalid chars stripped, truncated to 64 chars.
    Returns None when no valid username can be produced."""
    text = (username or "").strip()
    if not text:
        return None
    cleaned = _INVALID_CHARS_RE.sub("", text.replace("@", "_at_"))[:_MAX_NAME_LEN]
    return cleaned if _NAME_RE.match(cleaned) else None


def _validate_rows(path: Path) -> Tuple[List[Tuple[str, str, str]], int]:
    """Parse + validate the whole CSV BEFORE any vault write (L3).

    Returns ``(valid_rows, invalid_count)`` where each valid row is
    ``(service, username, password)``. Raises :class:`CsvImportError` when
    the file cannot be read or lacks required columns — the vault is
    untouched in that case.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CsvImportError(f"cannot read CSV {path}: {exc.strerror or exc}") from exc
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvImportError(f"CSV {path} is not valid UTF-8") from exc

    try:
        reader = csv.DictReader(text.splitlines())
        header = reader.fieldnames or []
        missing = [c for c in _REQUIRED_COLUMNS if c not in header]
        if missing:
            raise CsvImportError(
                "CSV %s missing required column(s): %s" % (path, ", ".join(missing))
            )
        valid: List[Tuple[str, str, str]] = []
        invalid = 0
        for lineno, row in enumerate(reader, start=2):
            try:
                password = (row.get("password") or "").strip()
                if not password:
                    invalid += 1
                    continue
                username = _canonical_username(row.get("username") or "")
                if username is None:
                    invalid += 1
                    continue
                service = _canonical_service(row.get("url") or "")
                valid.append((service, username, password))
            except Exception:
                # Fail closed per-row: never let one bad row abort or
                # leak — count it and move on. (L1: no values in the
                # message.)
                invalid += 1
        return valid, invalid
    except CsvImportError:
        raise
    except Exception as exc:
        raise CsvImportError(f"CSV {path} could not be parsed: {type(exc).__name__}") from exc


# ---------------------------------------------------------------------------
# SAF folder picker (Android Storage Access Framework integration point)
#
# The system folder-picker UI (ACTION_OPEN_DOCUMENT_TREE) can only run on
# the Android runtime inside an Activity. This module does NOT fake that:
# there is no Tkinter/Qt dialog fallback, no cwd guess, no tmpdir
# substitution. Instead it exposes the integration point the Android host
# wires into:
#
#   Android host wiring (apps/cybrus-android):
#     from levi.cybrus import vault_import
#     def android_pick(purpose: str) -> str | None:
#         # MainActivity fires Intent(ACTION_OPEN_DOCUMENT_TREE),
#         # waits for onActivityResult, resolves the returned tree URI to
#         # an app-accessible filesystem path, and returns it
#         # (None when the user cancels).
#         ...
#     vault_import.register_saf_picker(android_pick)
#
# The bridge callback contract: ``fn(purpose) -> Optional[str]`` — a
# readable filesystem path (content:// URIs must be resolved by the host),
# or None when the user cancels. Anything else is a loud
# ``SafNotAvailableError``, never a silent substitution (L7).
# ---------------------------------------------------------------------------

# The host-registered SAF picker bridge. None until the Android host (or a
# test double) calls register_saf_picker().
_SAF_PICKER: Optional[Callable[[str], Optional[str]]] = None


def register_saf_picker(
    fn: Optional[Callable[[str], Optional[str]]],
) -> None:
    """Register (or unregister, with None) the host SAF picker bridge.

    The Android host calls this once at startup with a callback that shows
    the system folder picker and returns the chosen directory as a
    filesystem path, or None on cancel. See the section header above for
    the exact contract.
    """
    global _SAF_PICKER
    _SAF_PICKER = fn


def android_runtime() -> bool:
    """Best-effort detection of the Android runtime.

    Used only for diagnostics — ``pick_saf_folder`` works identically
    everywhere: bridge or CYBRUS_SAF_DIR, else a loud refusal (L7)."""
    if "android" in sys.platform:
        return True
    return bool(os.environ.get("ANDROID_ART_ROOT") or os.environ.get("ANDROID_DATA"))


def pick_saf_folder(*, purpose: str = "csv-import") -> Path:
    """Return the user-chosen SAF directory for ``purpose``.

    Resolution order (L7 — nothing is ever fabricated):
      1. ``CYBRUS_SAF_DIR`` when set: must exist and be a readable
         directory, else ``SafNotAvailableError`` (misconfiguration is
         loud, not silently ignored).
      2. The host-registered picker bridge (:func:`register_saf_picker`):
         its result must be an existing directory, else
         ``SafNotAvailableError``.
      3. Otherwise ``SafNotAvailableError`` explaining that the Android
         runtime (with a registered picker) or ``CYBRUS_SAF_DIR`` is
         required.

    Threat-model note: ``CYBRUS_SAF_DIR`` takes precedence over the
    registered bridge BY DESIGN — it is the operator's explicit override.
    A process inheriting its environment from a malicious parent could
    therefore have its picked folder redirected without the host picker
    ever running. On the Android host this is a non-issue (the app owns
    its process env); on shared shells, treat the env as the operator's
    word and prefer the bridge.

    Never returns a guessed path. Never touches the network (L6).
    """
    env_dir = os.environ.get(SAF_ENV_DIR, "").strip()
    if env_dir:
        picked = Path(env_dir).expanduser()
        if picked.is_dir() and os.access(picked, os.R_OK):
            return picked
        raise SafNotAvailableError(
            f"{SAF_ENV_DIR}={env_dir} is not a readable directory; "
            "set it to a pre-authorized folder or register a SAF picker"
        )

    if _SAF_PICKER is not None:
        try:
            chosen = _SAF_PICKER(purpose)
        except SafNotAvailableError:
            raise
        except Exception as exc:
            raise SafNotAvailableError(
                "SAF picker bridge failed: %s" % type(exc).__name__
            ) from exc
        if not chosen:
            raise SafNotAvailableError(
                "SAF picker was cancelled or returned no folder"
            )
        if not isinstance(chosen, (str, os.PathLike)):
            # Type-confusion guard (RED-3): a misbehaving bridge returning
            # a non-string truthy value must surface as the loud
            # SafNotAvailableError L7 promises — never a raw TypeError
            # from Path(...) that callers catching SafNotAvailableError
            # would miss.
            raise SafNotAvailableError(
                "SAF picker bridge returned a non-path value of type %s; "
                "the contract is Optional[str]" % type(chosen).__name__
            )
        picked = Path(chosen).expanduser()
        if picked.is_dir():
            return picked
        raise SafNotAvailableError(
            "SAF picker returned a path that is not a directory: %s" % picked
        )

    raise SafNotAvailableError(
        "no SAF folder picker available: this needs the Android runtime "
        "with a registered picker (see register_saf_picker), or set "
        f"{SAF_ENV_DIR} to a pre-authorized directory"
    )


# ---------------------------------------------------------------------------
# Honest reporting + overwrite-guarded report files
# ---------------------------------------------------------------------------


def describe_import(counts: Dict[str, int]) -> str:
    """Human-readable one-line import report.

    The counts-dict keys are pinned (L1/L9 contract); this is the human
    surface. When zero rows were imported the line explicitly states
    ``no changes applied`` — a no-op never looks like a silent success.
    Counts only, never credential values (L1).
    """
    line = "imported=%d duplicates=%d invalid=%d services=%d" % (
        counts["imported"],
        counts["duplicates"],
        counts["invalid"],
        counts["services"],
    )
    if counts.get("imported", 0) == 0:
        line += " — no changes applied"
    return line


def write_import_report(
    path: "str | Path",
    counts: Dict[str, int],
    *,
    overwrite: bool = False,
) -> Path:
    """Write the human-readable import report to ``path``.

    Overwrite guard (L8): when ``path`` already exists and
    ``overwrite`` is not True, raises :class:`OverwriteRefusedError`
    instead of silently truncating it. Pass ``overwrite=True`` for the
    explicit opt-in. The report holds counts only — never passwords,
    usernames, or URLs (L1).

    The write is atomic (tmp + rename) and symlink-safe (R2G-3): the tmp
    file gets an unpredictable name via ``tempfile.mkstemp`` (O_CREAT |
    O_EXCL, so a pre-planted path can never be it), the body is written
    through the open fd (no pathname re-open, so no symlink following),
    and before the rename we verify via ``lstat`` that the tmp path is
    still the regular file ``mkstemp`` created — anything else aborts
    instead of installing. ``os.replace`` replaces a pre-existing
    ``target`` symlink itself; it never follows it.
    """
    target = Path(path).expanduser()
    if target.exists() and not overwrite:
        raise OverwriteRefusedError(
            "refusing to overwrite existing file %s "
            "(pass overwrite=True to replace it)" % target
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    body = describe_import(counts) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=target.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        # Guard: the tmp path must still be the regular file mkstemp
        # created — not swapped for a symlink or anything else.
        st = os.lstat(tmp_name)
        if not stat.S_ISREG(st.st_mode):
            raise OSError(
                "refusing to install report: temp file %s is not a "
                "regular file" % tmp_name
            )
        os.replace(tmp_name, target)
    except BaseException:
        # Best-effort cleanup: never leave the tmp file behind.
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
    return target


def import_google_csv(
    path: "str | Path",
    vault: CredentialVault,
    *,
    on_duplicate: str = "keep-first",
) -> Dict[str, int]:
    """Import a Google Password Manager CSV into ``vault``.

    Returns counts only — ``{"imported", "duplicates", "invalid",
    "services"}`` — never credentials (L1). The key set is pinned: use
    :func:`describe_import` for the human-readable report, which states
    ``no changes applied`` explicitly when nothing was imported (L9).
    The write pass is a single lock-held load → modify → save, so
    concurrent writers cannot drop entries (L3/L4).
    """
    if on_duplicate != "keep-first":
        raise ValueError(
            "unsupported on_duplicate mode %r: only 'keep-first' is implemented"
            % (on_duplicate,)
        )
    csv_path = Path(path)
    valid_rows, invalid = _validate_rows(csv_path)

    imported = 0
    duplicates = 0
    touched_services = set()

    # Single atomic write pass (L3): validate-first already done, now one
    # locked load → apply → save.
    entries_path = vault._entries_path()
    try:
        with store_lock(entries_path):
            entries = vault._load_entries()
            for service, username, password in valid_rows:
                users = entries.setdefault(service, {})
                if username in users:
                    # Keep-first (L4): vault value or earlier CSV row wins.
                    duplicates += 1
                    continue
                users[username] = password
                touched_services.add(service)
                imported += 1
            vault._save_entries(entries)
    except VaultError:
        raise
    except Exception as exc:
        # Never leak values; the lock context guarantees the blob was
        # either fully written or not (atomic tmp+replace inside).
        raise VaultError(
            "import write pass failed: %s" % type(exc).__name__
        ) from exc

    return {
        "imported": imported,
        "duplicates": duplicates,
        "invalid": invalid,
        "services": len(touched_services),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: import a Google Passwords CSV into the Cybrus vault.

    Prints counts only — never credentials (L1). The master passphrase
    comes from a getpass prompt (never argv, never env, never stored).
    When nothing is imported the report explicitly says ``no changes
    applied`` (L9).
    """
    parser = argparse.ArgumentParser(
        description="Import a Google Password Manager CSV into the Cybrus vault."
    )
    parser.add_argument("csv_path", help="Path to the Google Passwords CSV export")
    parser.add_argument(
        "--vault-dir",
        default=None,
        help="Vault directory (default: the standard Cybrus vault location)",
    )
    parser.add_argument(
        "--saf",
        action="store_true",
        help=(
            "Resolve csv_path through the SAF folder picker: the path is "
            "resolved (symlinks included) and jailed inside the picked "
            "folder — anything outside is refused. Requires the Android "
            "runtime with a registered picker, or CYBRUS_SAF_DIR."
        ),
    )
    parser.add_argument(
        "--report-path",
        default=None,
        help="Write the human-readable import report to this file "
        "(counts only). Refuses to overwrite an existing file unless "
        "--overwrite-report is given.",
    )
    parser.add_argument(
        "--overwrite-report",
        action="store_true",
        help="Explicit opt-in: allow --report-path to replace an existing file.",
    )
    args = parser.parse_args(argv)

    csv_path = Path(args.csv_path)
    if args.saf:
        # SAF folder picker integration (L7): the picked folder is the
        # authority for where the CSV comes from. EVERY path — relative or
        # absolute — is resolved (symlinks included) and jailed inside the
        # picked folder. Relative `..` segments and symlinks pointing
        # outside are refused (R2G-1, R2G-2).
        try:
            folder = pick_saf_folder(purpose="csv-import")
        except SafNotAvailableError as exc:
            print(f"error: SAF folder picker unavailable: {exc}")
            return 1
        folder_resolved = folder.resolve()
        candidate = csv_path if csv_path.is_absolute() else folder / csv_path
        try:
            csv_resolved = candidate.resolve()
        except OSError as exc:
            print(f"error: --saf: cannot resolve {csv_path}: {exc}")
            return 1
        try:
            csv_resolved.relative_to(folder_resolved)
        except ValueError:
            print(
                f"error: --saf: {csv_path} is outside the picked "
                f"folder {folder}"
            )
            return 1
        csv_path = csv_resolved

    passphrase = getpass.getpass("Cybrus master passphrase: ")
    try:
        vault = CredentialVault(
            passphrase,
            directory=Path(args.vault_dir) if args.vault_dir else None,
        )
    except (ValueError, VaultError) as exc:
        print(f"error: cannot open vault: {exc}")
        return 2

    try:
        counts = import_google_csv(str(csv_path), vault)
    except (CsvImportError, VaultError, ValueError) as exc:
        print(f"error: import failed: {exc}")
        return 1

    print(describe_import(counts))

    if args.report_path:
        try:
            report_file = write_import_report(
                args.report_path, counts, overwrite=args.overwrite_report
            )
        except (OverwriteRefusedError, OSError) as exc:
            print(f"error: {exc}")
            return 1
        print(f"report written to {report_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
