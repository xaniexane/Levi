"""Tests for the LEVI-native chain framework (core/levi/chain/).

Hermetic: LEVI_HOME pinned to tmp, no network, no real side effects.
"""

import json
import os
import stat

import pytest

from levi.chain import (
    RAIL,
    SAFE_RAIL,
    ChainError,
    PermissionToken,
    RiskBand,
    build_chain,
    flow_link,
    grant,
    link,
    read_receipts,
    run_chain,
)


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _double(value):
    return value * 2


def _shout(value):
    return str(value).upper() + "!"


def test_build_chain_assembles_links_in_order(home):
    chain = build_chain(
        [
            {"name": "a", "fn": _double},
            {"name": "b", "fn": _shout, "risk": "safe"},
        ],
        id="order-test",
        name="Order Test",
    )
    assert chain.id == "order-test"
    assert [lnk.name for lnk in chain.links] == ["a", "b"]
    assert all(lnk.risk is RiskBand.SAFE for lnk in chain.links)


def test_build_chain_rejects_duplicate_names(home):
    with pytest.raises(ChainError):
        build_chain(
            [{"name": "dup", "fn": _double}, {"name": "dup", "fn": _shout}],
            id="dup-test",
        )


def test_build_chain_rejects_non_callable_and_empty(home):
    with pytest.raises(ChainError):
        build_chain([{"name": "x", "fn": 42}], id="bad-fn")
    with pytest.raises(ChainError):
        build_chain([], id="empty")


def test_build_chain_rejects_bad_risk_band(home):
    with pytest.raises(ChainError):
        build_chain([{"name": "x", "fn": _double, "risk": "nuclear"}], id="bad-risk")


def test_link_decorator(home):
    @link(name="triple", risk=RiskBand.SAFE, describe="times three")
    def triple(value):
        return value * 3

    chain = build_chain([triple], id="deco")
    receipt = run_chain(chain, 5, home=str(home))
    assert receipt.ok and receipt.output == 15


def test_safe_chain_runs_straight_through(home):
    # model -> parser -> tool -> memory: all pure, no permission needed.
    chain = build_chain(
        [
            link(name="model")(lambda v: f"raw:{v}"),
            link(name="parser")(lambda v: v.replace("raw:", "")),
            link(name="tool")(lambda v: v.split(",")),
            link(name="memory")(lambda v: {"stored": v}),
        ],
        id="pipeline",
    )
    receipt = run_chain(chain, "a,b", home=str(home))
    assert receipt.ok
    assert receipt.output == {"stored": ["a", "b"]}
    assert [r.link_name for r in receipt.links] == [
        "model",
        "parser",
        "tool",
        "memory",
    ]
    assert all(r.executed and r.permission_token_id is None for r in receipt.links)
    assert all(tuple(r.rail) == SAFE_RAIL for r in receipt.links)


def test_consequential_link_refuses_without_permission(home):
    calls = []

    def world_effect(value):
        calls.append(value)
        return "changed the world"

    chain = build_chain(
        [
            link(name="prep")(lambda v: v + 1),
            link(name="effect", risk=RiskBand.CONSEQUENTIAL)(world_effect),
        ],
        id="gate-test",
    )
    receipt = run_chain(chain, 1, home=str(home))

    assert receipt.ok is False
    # The effect never ran: the gate held.
    assert calls == []
    denied = receipt.links[-1]
    assert denied.link_name == "effect"
    assert denied.executed is False
    assert denied.permission_token_id is None
    assert "permission denied" in denied.detail
    # A refusal is still receipted.
    assert len(receipt.links) == 2
    assert tuple(denied.rail) == RAIL


def test_consequential_link_runs_with_recorded_token(home):
    seen = []

    def effect(value):
        seen.append(value)
        return f"did:{value}"

    chain = build_chain(
        [link(name="effect", risk=RiskBand.CONSEQUENTIAL)(effect)],
        id="grant-test",
    )
    token = grant(
        "effect", by="keeper", scope="grant-test", note="test grant", home=str(home)
    )
    assert isinstance(token, PermissionToken)
    receipt = run_chain(chain, "go", permissions=[token], home=str(home))

    assert receipt.ok and receipt.output == "did:go"
    assert seen == ["go"]
    got = receipt.links[0]
    assert got.executed and got.permission_token_id == token.token_id
    # The grant was recorded in the permission ledger.
    ledger = (home / "chain" / "permissions.jsonl").read_text()
    assert token.token_id in ledger


def test_ledger_token_authorizes_without_threading(home):
    def effect(value):
        return f"did:{value}"

    chain = build_chain(
        [link(name="effect", risk=RiskBand.CONSEQUENTIAL)(effect)],
        id="ledger-test",
    )
    token = grant("effect", scope="ledger-test", home=str(home))
    # No permissions passed in — the on-disk ledger backs the gate.
    receipt = run_chain(chain, "go", home=str(home))
    assert receipt.ok
    assert receipt.links[0].permission_token_id == token.token_id


def test_grantor_mints_token_at_runtime(home):
    def effect(value):
        return f"did:{value}"

    chain = build_chain(
        [link(name="effect", risk=RiskBand.CONSEQUENTIAL)(effect)],
        id="grantor-test",
    )

    asked = []

    def grantor(link_obj, plan, preview):
        asked.append((link_obj.name, plan, preview))
        return grant(
            link_obj.name, by="runtime-grantor", scope="grantor-test", home=str(home)
        )

    receipt = run_chain(chain, "go", grantor=grantor, home=str(home))
    assert receipt.ok and receipt.output == "did:go"
    assert len(asked) == 1 and asked[0][0] == "effect"
    assert "WORLD-EFFECT" in asked[0][2]  # the preview warned honestly


def test_grantor_denial_stops_chain(home):
    chain = build_chain(
        [
            link(name="effect", risk=RiskBand.CONSEQUENTIAL)(lambda v: v),
            link(name="never")(lambda v: "unreached"),
        ],
        id="deny-test",
    )
    receipt = run_chain(chain, "x", grantor=lambda *a: None, home=str(home))
    assert receipt.ok is False
    assert [r.link_name for r in receipt.links] == ["effect"]  # stopped there
    assert receipt.output is None


def test_failed_link_stops_chain_fail_closed(home):
    def boom(value):
        raise RuntimeError("kaboom")

    chain = build_chain(
        [
            link(name="ok1")(lambda v: v),
            link(name="boom")(boom),
            link(name="ok2")(lambda v: v),
        ],
        id="fail-test",
    )
    receipt = run_chain(chain, "x", home=str(home))
    assert receipt.ok is False
    assert [r.link_name for r in receipt.links] == ["ok1", "boom"]
    failed = receipt.links[-1]
    assert failed.executed and "RuntimeError" in failed.detail
    assert "kaboom" in failed.error


def test_verifier_rejects_bad_output(home):
    chain = build_chain(
        [
            link(name="maybe", verifier=lambda out: out > 10)(lambda v: v),
        ],
        id="verify-test",
    )
    receipt = run_chain(chain, 3, home=str(home))
    assert receipt.ok is False
    assert "VERIFY FAILED" in receipt.links[0].detail

    receipt2 = run_chain(chain, 30, home=str(home))
    assert receipt2.ok and receipt2.output == 30


def test_receipts_are_append_only_jsonl_owner_only(home):
    chain = build_chain([link(name="a")(lambda v: v)], id="rcpt-test")
    run_chain(chain, "x", home=str(home))
    run_chain(chain, "y", home=str(home))

    path = home / "chain" / "receipts.jsonl"
    assert path.exists()
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600, f"receipt ledger must be owner-only, got {oct(mode)}"
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["link_name"] == "a" and first["run_id"].startswith("chain-")
    # read_receipts sees the same records
    assert len(read_receipts(str(home))) == 2


def test_chain_receipt_renders(home):
    chain = build_chain(
        [
            link(name="a")(lambda v: v),
            link(name="b", risk=RiskBand.CONSEQUENTIAL)(lambda v: v),
        ],
        id="render-test",
    )
    receipt = run_chain(chain, "x", home=str(home))
    text = receipt.render()
    assert "render-test" in text and "FAILED" in text
    assert "[safe] a" in text and "[consequential] b" in text


def test_flow_link_embeds_a_flow(home):
    flow = {
        "id": "mini",
        "name": "Mini",
        "start": "p",
        "nodes": [
            {"id": "p", "kind": "predicate", "expr": "1 + 1 == 2", "label": "P"},
            {"id": "n", "kind": "note", "text": "done", "label": "N"},
        ],
        "edges": [{"id": "e1", "from": "p", "to": "n"}],
    }
    chain = build_chain([flow_link(flow, dry_run=True)], id="flow-embed")
    token = grant("mini", scope="flow-embed", home=str(home))
    receipt = run_chain(chain, {"seed": 1}, permissions=[token], home=str(home))
    assert receipt.ok
    flow_receipt = receipt.output
    assert flow_receipt.ok and flow_receipt.flow_id == "mini"


def test_flow_link_is_consequential_by_default_and_denied(home):
    flow = {
        "id": "mini2",
        "start": "n",
        "nodes": [{"id": "n", "kind": "note", "text": "x", "label": "N"}],
        "edges": [],
    }
    lnk = flow_link(flow)
    assert lnk.risk is RiskBand.CONSEQUENTIAL
    chain = build_chain([lnk], id="flow-deny")
    receipt = run_chain(chain, None, home=str(home))
    assert receipt.ok is False
    assert receipt.links[0].executed is False
