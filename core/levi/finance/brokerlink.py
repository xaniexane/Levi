"""Broker-link option for the LEVI finance domain — DRAFT ONLY.

This module is the *configuration surface* for one day linking a real
trading platform (stock broker like Alpaca, crypto exchange like Binance
or Coinbase) so Chauncey can recreate LEVI's paper predictions there.
What it does:

* ``configure(platform)`` — records which platform the drafts are
  *formatted for*. No credentials are requested, stored, or needed.
* ``prepare_drafts(predictions, config)`` — turns advisory predictions
  into **draft orders**: review artifacts saved locally, labeled
  ``DRAFT — NOT SENT``. A draft is a note to a human, not an order.

What it structurally CANNOT do:

* There is no transport here — no HTTP client, no SDK, no socket. A
  draft cannot leave this machine through any code path in this module.
* ``execute_draft()`` raises :class:`LiveExecutionRefused`, always.
  There is no flag, env var, or config value that changes this.
* Live trading stays refused exactly as in :mod:`levi.finance.broker`:
  unwired transport, no keys requested, per-order human confirmation
  for even paper orders.

If live execution is ever deliberately enabled in the future, it happens
in ``broker.py`` behind its five-item structural checklist — never here.

Stdlib-only: ``dataclasses``, ``json``, ``math``, ``pathlib``,
``datetime``, ``uuid``, ``warnings``.
"""

from __future__ import annotations

import json
import math
import uuid
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from levi.finance.wsb import assert_clean

__all__ = [
    "BrokerLinkConfig",
    "DraftOrder",
    "LiveExecutionRefused",
    "InvalidDraft",
    "SUPPORTED_PLATFORMS",
    "DEFAULT_LINK_PATH",
    "DEFAULT_DRAFTS_PATH",
    "configure_broker_link",
    "broker_link_status",
    "prepare_drafts",
    "execute_draft",
    "load_drafts",
]

#: Platforms drafts can be formatted for. Declaring a platform links
#: nothing — it only labels the drafts for the human reading them.
SUPPORTED_PLATFORMS: dict[str, str] = {
    "alpaca": "stocks — Alpaca",
    "binance": "crypto — Binance",
    "coinbase": "crypto — Coinbase",
}

#: The ONLY mode this module supports. Any other value is rejected at
#: construction — there is no "live" mode to opt into here.
DRAFT_ONLY_MODE = "draft-only"

DEFAULT_LINK_PATH: Path = Path.home() / ".levi" / "finance" / "broker_link.json"
DEFAULT_DRAFTS_PATH: Path = Path.home() / ".levi" / "finance" / "drafts.json"

_FINANCE_DIR_MODE = 0o700


class LiveExecutionRefused(Exception):
    """Raised by any execution-shaped call in this module.

    Live execution is structurally refused: there is no transport to
    call, so this is raised unconditionally — not gated on config.
    """


class InvalidDraft(ValueError):
    """Raised when a draft prediction fails validation. Nothing drafted."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_positive(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidDraft(f"{name} must be a number, got {value!r}")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise InvalidDraft(f"{name} must be positive, got {value!r}")
    return result


@dataclass
class BrokerLinkConfig:
    """Which platform drafts are formatted for. Draft-only, always."""

    platform: str | None = None
    mode: str = DRAFT_ONLY_MODE

    def __post_init__(self) -> None:
        if self.mode != DRAFT_ONLY_MODE:
            raise InvalidDraft(
                f"broker-link mode must be {DRAFT_ONLY_MODE!r}; "
                f"got {self.mode!r} — live modes are not implemented "
                "anywhere in this module."
            )
        if self.platform is not None:
            name = str(self.platform).strip().lower()
            if name not in SUPPORTED_PLATFORMS:
                raise InvalidDraft(
                    f"unknown platform {self.platform!r}: expected one of "
                    f"{sorted(SUPPORTED_PLATFORMS)}."
                )
            self.platform = name

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "mode": self.mode,
            "live": "STRUCTURALLY REFUSED",
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BrokerLinkConfig":
        return cls(
            platform=data.get("platform"), mode=data.get("mode", DRAFT_ONLY_MODE)
        )


@dataclass
class DraftOrder:
    """A draft order: a review artifact, not an order.

    ``status`` is always ``"DRAFT — NOT SENT"``. Nothing in this codebase
    will ever transition a draft to sent — that transition does not
    exist.
    """

    id: str
    symbol: str
    side: str
    qty: float
    reference_price: float
    platform: str
    created_at: str = field(default_factory=_now_iso)
    status: str = "DRAFT — NOT SENT"
    note: str = (
        "Review artifact only. LEVI cannot send this anywhere; "
        "recreate it manually on the platform if you choose to act. "
        "Not financial advice."
    )

    def __post_init__(self) -> None:
        symbol = str(self.symbol or "").strip().upper()
        if not symbol:
            raise InvalidDraft("draft symbol must be non-empty")
        self.symbol = symbol
        side = str(self.side or "").strip().lower()
        if side not in ("buy", "sell"):
            raise InvalidDraft(f"draft side must be 'buy'/'sell', got {self.side!r}")
        self.side = side
        self.qty = _require_positive("qty", self.qty)
        self.reference_price = _require_positive(
            "reference_price", self.reference_price
        )
        if self.platform not in SUPPORTED_PLATFORMS:
            raise InvalidDraft(
                f"draft platform must be one of "
                f"{sorted(SUPPORTED_PLATFORMS)}, got {self.platform!r}"
            )
        if self.status != "DRAFT — NOT SENT":
            raise InvalidDraft(
                "draft status is always 'DRAFT — NOT SENT'; drafts are "
                "never sent by LEVI."
            )

    def to_dict(self) -> dict:
        data = asdict(self)
        data["qty"] = round(data["qty"] + 0.0, 6)
        data["reference_price"] = round(data["reference_price"] + 0.0, 2)
        return data

    def render(self) -> str:
        side_word = "BUY 🟢" if self.side == "buy" else "SELL 🔴"
        notional = self.qty * self.reference_price
        return assert_clean(
            "\n".join(
                [
                    "┌─────────────────────────────────────────┐",
                    "│  📝 DRAFT ORDER — NOT SENT              │",
                    "├─────────────────────────────────────────┤",
                    f"│  {self.id}",
                    f"│  {side_word}  {self.qty:g} {self.symbol}",
                    f"│  ref price ${self.reference_price:,.2f} "
                    f"(~${notional:,.2f} notional)",
                    f"│  platform: {self.platform} "
                    f"({SUPPORTED_PLATFORMS[self.platform]})",
                    f"│  drafted: {self.created_at[:10]}",
                    "├─────────────────────────────────────────┤",
                    "│  LEVI cannot send this. Recreate it     │",
                    "│  manually on the platform if YOU choose │",
                    "│  to act. Not financial advice.          │",
                    "└─────────────────────────────────────────┘",
                ]
            )
        )


def _save_json(path: Path, payload: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(_FINANCE_DIR_MODE)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def configure_broker_link(
    platform: str, path: Path = DEFAULT_LINK_PATH
) -> BrokerLinkConfig:
    """Record which platform drafts are formatted for.

    No credentials are requested or stored — a platform name is just a
    label on the drafts. Returns the saved config.
    """
    config = BrokerLinkConfig(platform=platform)
    _save_json(path, {**config.to_dict(), "configured_at": _now_iso()})
    return config


def broker_link_status(
    link_path: Path = DEFAULT_LINK_PATH,
    drafts_path: Path = DEFAULT_DRAFTS_PATH,
) -> dict:
    """Report broker-link state. Never touches the network."""
    try:
        data = json.loads(Path(link_path).read_text(encoding="utf-8"))
        config = BrokerLinkConfig.from_dict(data)
    except Exception:
        config = BrokerLinkConfig(platform=None)
    drafts = load_drafts(drafts_path)
    pending = [d for d in drafts if d.status == "DRAFT — NOT SENT"]
    return {
        "platform": config.platform,
        "platform_label": (
            SUPPORTED_PLATFORMS[config.platform] if config.platform else None
        ),
        "mode": config.mode,
        "live_execution": "STRUCTURALLY REFUSED — no transport exists",
        "credentials_requested": "none — drafts need no keys",
        "drafts_pending": len(pending),
        "drafts_total": len(drafts),
    }


def prepare_drafts(
    predictions: list[dict],
    config: BrokerLinkConfig,
    path: Path = DEFAULT_DRAFTS_PATH,
) -> list[DraftOrder]:
    """Turn advisory predictions into draft orders for human review.

    ``predictions``: each ``{"symbol", "side", "qty", "reference_price"}``.
    Every draft is labeled ``DRAFT — NOT SENT`` and appended to the local
    drafts file. Nothing is sent anywhere — there is no transport to send
    with.
    """
    if config.platform is None:
        raise InvalidDraft(
            "no platform configured: run "
            "`levi finance broker-link configure --platform <name>` first. "
            "Nothing was drafted."
        )
    if not isinstance(predictions, list) or not predictions:
        raise InvalidDraft("predictions must be a non-empty list — nothing drafted.")
    drafts: list[DraftOrder] = []
    for i, pred in enumerate(predictions):
        if not isinstance(pred, dict):
            raise InvalidDraft(
                f"prediction #{i} must be a dict, got {type(pred).__name__}."
            )
        try:
            drafts.append(
                DraftOrder(
                    id=f"draft-{uuid.uuid4().hex[:8]}",
                    symbol=pred["symbol"],
                    side=pred["side"],
                    qty=pred["qty"],
                    reference_price=pred["reference_price"],
                    platform=config.platform,
                )
            )
        except (KeyError, InvalidDraft) as exc:
            raise InvalidDraft(
                f"prediction #{i} invalid ({exc}) — nothing was drafted."
            ) from None
    existing = load_drafts(path)
    existing.extend(drafts)
    _save_json(
        path,
        {
            "drafts": [d.to_dict() for d in existing],
            "saved_at": _now_iso(),
        },
    )
    return drafts


def load_drafts(path: Path = DEFAULT_DRAFTS_PATH) -> list[DraftOrder]:
    """Load saved drafts. Corrupt file → loud warning + empty list."""
    path = Path(path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("drafts", [])
        if not isinstance(raw, list):
            raise ValueError("'drafts' must be a list")
        return [
            DraftOrder(
                id=str(d["id"]),
                symbol=d["symbol"],
                side=d["side"],
                qty=float(d["qty"]),
                reference_price=float(d["reference_price"]),
                platform=d["platform"],
                created_at=str(d.get("created_at", _now_iso())),
                status=str(d.get("status", "DRAFT — NOT SENT")),
                note=str(d.get("note", "")),
            )
            for d in raw
        ]
    except Exception as exc:
        warnings.warn(
            f"drafts file {path} is unreadable ({type(exc).__name__}); "
            "starting empty. Back up or delete the file to silence this warning.",
            UserWarning,
            stacklevel=2,
        )
        return []


def execute_draft(*args, **kwargs) -> None:
    """Refuse live execution — structurally, unconditionally.

    This function exists so any caller that *thinks* it can execute a
    draft gets an explicit refusal instead of a silent no-op. There is no
    code path past this raise.
    """
    raise LiveExecutionRefused(
        "LIVE EXECUTION REFUSED: draft orders are review artifacts. LEVI "
        "has no broker transport and cannot send orders anywhere. "
        "Nothing was sent and nothing was traded."
    )
