"""Stake-under-fog quoting — the quote prices its own confidence.

The quoting engine stakes reputation points on every quote: the
stake is an implicit confidence claim (``stake / 100``) that the
final price will land within tolerance of the quote. When the job
settles, :func:`settle_quote` scores the claim — a hit returns the
stake plus an equal reward; a miss loses the stake. Calibration is
tracked honestly over time via the Brier score, so the engine's
confidence means something measurable.

Same Mandella lineage as the academy's stake drills; separate
ledger, separate key — provider reputation is its own book.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from levi.neighboros import _seal

START_BALANCE = 100
MAX_STAKE = 100
DEFAULT_TOLERANCE = 0.15


def _quotes_dir(provider_id: str, home: Optional[Path] = None) -> Path:
    d = _seal.pkg_dir(home) / "quote_stakes" / provider_id
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _write_json(path: Path, record: Dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _state_path(provider_id: str, home: Optional[Path] = None) -> Path:
    return _quotes_dir(provider_id, home) / "state.json"


def _load_state(provider_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    p = _state_path(provider_id, home)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"provider_id": provider_id, "balance": START_BALANCE,
            "open": {}, "calibration": []}


def _save_state(state: Dict[str, Any], provider_id: str,
                home: Optional[Path] = None) -> None:
    _write_json(_state_path(provider_id, home), state)


def _utcnow(now: Optional[float] = None) -> str:
    ts = now if now is not None else time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def provider_balance(provider_id: str, home: Optional[Path] = None) -> int:
    return int(_load_state(provider_id, home)["balance"])


def stake_quote(provider_id: str, quote_id: str, quoted_price: float,
                stake: int, home: Optional[Path] = None,
                now: Optional[float] = None) -> Dict[str, Any]:
    """Stake reputation on a quote before the work settles."""
    if not provider_id or not provider_id.strip():
        raise ValueError("provider_id must be non-empty")
    if not quote_id or not quote_id.strip():
        raise ValueError("quote_id must be non-empty")
    quoted_price = float(quoted_price)
    if quoted_price <= 0:
        raise ValueError("quoted_price must be positive")
    stake = int(stake)
    state = _load_state(provider_id, home)
    if quote_id in state["open"]:
        raise ValueError(f"quote {quote_id!r} already has an open stake — settle it first")
    if stake < 1:
        raise ValueError("stake must be at least 1 point")
    if stake > MAX_STAKE:
        raise ValueError(f"stake may not exceed {MAX_STAKE} points")
    if stake > state["balance"]:
        raise ValueError(
            f"stake {stake} exceeds balance {state['balance']}")
    state["balance"] -= stake
    state["open"][quote_id] = {
        "quoted_price": quoted_price, "stake": stake,
        "staked_at": _utcnow(now),
    }
    _save_state(state, provider_id, home)
    return {"provider_id": provider_id, "quote_id": quote_id,
            "quoted_price": quoted_price, "stake": stake,
            "balance": state["balance"],
            "implicit_confidence": round(stake / MAX_STAKE, 3)}


def settle_quote(provider_id: str, quote_id: str, actual_price: float,
                 tolerance: float = DEFAULT_TOLERANCE,
                 home: Optional[Path] = None,
                 now: Optional[float] = None) -> Dict[str, Any]:
    """Settle a quote against the actual price.

    Hit: ``abs(actual - quoted) / quoted <= tolerance`` → stake back
    plus equal reward. Miss: stake lost. Either way the calibration
    ledger learns.
    """
    state = _load_state(provider_id, home)
    if quote_id not in state["open"]:
        raise KeyError(f"no open stake for quote {quote_id!r}")
    open_stake = state["open"].pop(quote_id)
    actual_price = float(actual_price)
    if actual_price <= 0:
        raise ValueError("actual_price must be positive")
    tolerance = float(tolerance)
    if not 0 <= tolerance <= 1:
        raise ValueError("tolerance must be 0..1")
    quoted = open_stake["quoted_price"]
    stake = open_stake["stake"]
    drift = abs(actual_price - quoted) / quoted
    hit = drift <= tolerance
    payout = 2 * stake if hit else 0
    state["balance"] += payout
    confidence = stake / MAX_STAKE
    state["calibration"].append({
        "quote_id": quote_id, "confidence": round(confidence, 3),
        "outcome": 1 if hit else 0, "drift": round(drift, 3),
        "settled_at": _utcnow(now),
    })
    _save_state(state, provider_id, home)
    return {"provider_id": provider_id, "quote_id": quote_id, "hit": hit,
            "drift": round(drift, 3), "tolerance": tolerance,
            "stake": stake, "payout": payout, "balance": state["balance"]}


def calibration_report(provider_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Brier-scored calibration of the provider's quote-confidence claims."""
    events = _load_state(provider_id, home)["calibration"]
    n = len(events)
    if n == 0:
        return {"provider_id": provider_id, "n": 0, "brier": None,
                "label": "no data — stake a quote first"}
    brier = sum((e["confidence"] - e["outcome"]) ** 2 for e in events) / n
    brier = round(brier, 3)
    if brier < 0.10:
        label = "well calibrated — quote confidence matches settlement"
    elif brier < 0.20:
        label = "roughly calibrated"
    else:
        label = "poorly calibrated — quotes drift more than the stakes admit"
    return {"provider_id": provider_id, "n": n, "brier": brier, "label": label}
