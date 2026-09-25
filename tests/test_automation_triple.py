"""Tests for the automation triple: 471-minion catalog, interpenetration
composition law, the Echo × Mandella signature, and Mandella fog runs.

- Catalog integrity: 471 rows, 13-column schema, stamped signatures,
  zero duplicates on (category, subcategory, trigger, condition).
- Composition law: interpenetrate() inherits the strictest risk ceiling
  (max clearance, per LEVI's dialect); interrogation ⊥ no_hero is never
  collapsed.
- Signature: verify_signatures() reproduces over the live catalog and
  detects tampering.
- Fog: all 471 minions phantom-run through 6 adversarial probes fail closed.
"""

from __future__ import annotations

import pytest

from levi.automation.minions import MINIONS
from levi.interpenetration import (
    FOG_PROBES,
    InvariantViolation,
    Organ,
    fog_sweep,
    interpenetrate,
    phantom_run,
    verify_signature,
    verify_signatures,
)
from levi.interpenetration.catalog import (
    canonical_catalog_bytes,
    signature_for_rows,
)

SCHEMA_KEYS = [
    "category",
    "subcategory",
    "trigger",
    "condition",
    "android_tool",
    "windows_tool",
    "mac_tool",
    "chrome_extension",
    "bridge",
    "usb_auto_launch",
    "hitl_type",
    "example_rite",
    "notes",
]


# ---------------------------------------------------------------------------
# Catalog integrity — the triple
# ---------------------------------------------------------------------------


def test_catalog_is_471():
    assert len(MINIONS) == 471


def test_every_row_has_schema_and_stamp():
    for minion in MINIONS:
        d = minion.to_dict()
        for key in SCHEMA_KEYS:
            assert key in d, (minion.id, key)
        assert minion.id, "minion id must be non-empty"
        assert minion.signature_id.startswith("ipsig-"), minion.id
        if minion.incomplete:
            continue  # the truncated intake row has no authored values
        # His schema quirk preserved on every authored row.
        assert minion.bridge == "Webhook", minion.id
        assert minion.usb_auto_launch == "n8n", minion.id


def test_no_duplicate_bot_definitions():
    # Chauncey's intake keeps its near-verbatim duplicate rows by law
    # (nothing is ever deleted — spot the differences). Uniqueness is
    # enforced on LEVI-original definitions only.
    seen = {}
    for minion in MINIONS:
        if minion.origin != "levi-original":
            continue
        key = (minion.category, minion.subcategory, minion.trigger, minion.condition)
        assert key not in seen, f"duplicate of {seen[key]}: {minion.id}"
        seen[key] = minion.id


def test_triple_bloodline_counts():
    origins = [b.origin for b in MINIONS]
    assert origins.count("chauncey-intake") == 52
    assert origins.count("levi-original") == 419
    assert sum(1 for b in MINIONS if b.incomplete) == 1


# ---------------------------------------------------------------------------
# Composition law
# ---------------------------------------------------------------------------


def test_strictest_ceiling_wins_echo_mandella():
    composite = interpenetrate("echo", "mandella", content=b"probe")
    # echo=1, mandella=2 → strictest (highest clearance) = 2
    assert composite.organs == ("echo", "mandella")
    assert composite.risk_ceiling == 2


def test_strictest_ceiling_wins_with_higher_organ():
    guard = Organ(name="guard", risk_ceiling=4, role="test probe")
    composite = interpenetrate("echo", guard, content=b"probe")
    assert composite.risk_ceiling == 4


def test_interpenetration_needs_two_organs():
    with pytest.raises(ValueError):
        interpenetrate("echo", content=b"x")


def test_unknown_organ_rejected():
    with pytest.raises(ValueError):
        interpenetrate("echo", "sauron", content=b"x")


def test_control_persona_invariant_never_collapsed():
    interrogation = Organ(name="interrogation", risk_ceiling=1)
    no_hero = Organ(name="no_hero", risk_ceiling=1)
    with pytest.raises(InvariantViolation):
        interpenetrate(interrogation, no_hero, content=b"x")
    # Either one alone with a normal organ is fine.
    ok = interpenetrate(interrogation, "echo", content=b"x")
    assert ok.risk_ceiling == 1


def test_composite_id_derives_from_signature():
    a = interpenetrate("echo", "mandella", content=b"same")
    b = interpenetrate("echo", "mandella", content=b"same")
    assert a.signature.content_hash == b.signature.content_hash
    assert a.signature.signature_id == b.signature.signature_id


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------


def test_verify_signatures_green():
    result = verify_signatures()
    assert result["ok"], result["detail"]
    assert result["minions_checked"] == 471
    assert result["mismatched"] == []
    assert result["organs"] == ["echo", "mandella"]
    assert result["risk_ceiling"] == 2
    assert result["mark"].startswith("echo×mandella::")


def test_signature_detects_tampering():
    rows = [b.to_dict() for b in MINIONS]
    sig = signature_for_rows(rows)
    content = canonical_catalog_bytes(rows)
    assert verify_signature(sig, content) is True
    tampered = bytearray(content)
    tampered[-10] ^= 0xFF
    assert verify_signature(sig, bytes(tampered)) is False


def test_signature_stamps_match_live_computation():
    live = signature_for_rows([b.to_dict() for b in MINIONS])
    stamped = {b.signature_id for b in MINIONS}
    assert stamped == {live.signature_id}


# ---------------------------------------------------------------------------
# Fog — Mandella stakes every minion under uncertainty
# ---------------------------------------------------------------------------


def test_fog_probes_defined():
    assert set(FOG_PROBES) == {
        "empty",
        "missing-detail",
        "contradictory",
        "hostile",
        "deny",
        "garbage",
    }


def test_phantom_run_fail_closed_sample():
    minion = next(b for b in MINIONS if not b.incomplete)
    for probe in FOG_PROBES:
        verdict = phantom_run(minion, probe)
        assert verdict.fail_closed, (probe, verdict.note)


def test_phantom_run_unknown_probe_rejected():
    minion = MINIONS[0]
    with pytest.raises(ValueError):
        phantom_run(minion, "nope")


def test_fog_sweep_all_471_fail_closed():
    sweep = fog_sweep()
    assert sweep["minions"] == 471
    assert sweep["runs"] == 471 * len(FOG_PROBES)
    assert sweep["fail_open"] == 0, sweep["fail_open_verdicts"][:3]
    assert sweep["fail_closed"] == sweep["runs"]
