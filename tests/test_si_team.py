"""SI Team tests — hermetic, no network.

Covers: 4 charters load, spotlight rule, substrate fallback, consult
receipt shape, unknown role refusal, si/ai separation, AI bridge labels,
MCP tool schema validity, chat adapter round-trip.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import re


from levi.bot.persona import check_no_mask
from levi.si_team import charter, counsel, roles, substrate
from levi.si_team.si import get_core, list_cores

AI_DIR = (
    pathlib.Path(__file__).resolve().parent.parent / "core" / "levi" / "si_team" / "ai"
)
SI_DIR = (
    pathlib.Path(__file__).resolve().parent.parent / "core" / "levi" / "si_team" / "si"
)

ROLE_NAMES = ["levi", "alpha", "omega", "dweller"]


# ---------------------------------------------------------------- charters


def test_four_charters_load():
    assert roles.role_names() == ROLE_NAMES
    for name in ROLE_NAMES:
        c = roles.ROSTER[name]
        assert isinstance(c, charter.RoleCharter)
        for field in ("name", "epithet", "mandate", "spotlight_rule", "si_line"):
            assert getattr(c, field), f"{name}.{field} is empty"
        assert c.boundaries, f"{name}.boundaries is empty"


def test_spotlight_rule_only_levi_owns_the_spotlight():
    # No charter may claim to be Levi/LEVI. Only the lead's spotlight_rule
    # may grant the spotlight.
    for name in ROLE_NAMES:
        text = roles.ROSTER[name].full_text().lower()
        if name == "levi":
            assert "own the spotlight" in roles.ROSTER[name].spotlight_rule
        else:
            assert not re.search(r"\bi am levi\b", text), name
            assert "the spotlight belongs to levi" in text
            assert "never claim to be levi" in text
    # Each crew role names itself honestly in its si_line.
    for name in ROLE_NAMES:
        assert f"i am {name}" in roles.ROSTER[name].si_line.lower(), name


def test_charters_pass_no_mask():
    for name in ROLE_NAMES:
        violations = check_no_mask(roles.ROSTER[name].full_text())
        assert violations == [], (name, violations)


# --------------------------------------------------------------- substrate


def test_alpha_routes_through_levi_alpha_when_present():
    # The sibling's levi.alpha substrate has landed; Alpha must route over it.
    import levi.alpha  # noqa: F401  (presence asserted by the contract)

    substrate.unregister_substrate("alpha")
    receipt = counsel.consult("alpha", "explain the trade-offs")
    assert receipt.substrate_used == "levi.alpha"
    assert receipt.answer


def test_substrate_fallback_when_alpha_probe_fails(monkeypatch):
    # If the levi.alpha probe blows up, Alpha falls back to rules honestly.
    import levi.alpha

    def boom():  # noqa: ARG001
        raise RuntimeError("probe unavailable")

    monkeypatch.setattr(levi.alpha, "probe_alpha", boom)
    substrate.unregister_substrate("alpha")
    receipt = counsel.consult("alpha", "explain the trade-offs")
    assert receipt.substrate_used == "rules-engine"
    assert "ALPHA" in receipt.answer


def test_register_substrate_wins_over_rules():
    substrate.register_substrate("omega", lambda task: f"custom-verdict: {task}")
    try:
        receipt = counsel.consult("omega", "judge this plan")
        assert receipt.substrate_used == "registered:omega"
        assert receipt.answer.startswith("custom-verdict:")
    finally:
        substrate.unregister_substrate("omega")


def test_broken_probe_falls_through_to_rules():
    def boom(task):  # noqa: ARG001
        raise RuntimeError("probe blew up")

    substrate.register_substrate("dweller", boom)
    try:
        receipt = counsel.consult("dweller", "batch this labor")
        assert receipt.substrate_used == "rules-engine"
        assert "DWELLER" in receipt.answer
    finally:
        substrate.unregister_substrate("dweller")


# ----------------------------------------------------------------- counsel


def test_consult_receipt_shape():
    receipt = counsel.consult("levi", "who are you")
    assert isinstance(receipt, counsel.Counsel)
    assert receipt.role == "levi"
    assert receipt.substrate_used in {"rules-engine", "native-brain"}
    assert receipt.answer
    assert isinstance(receipt.limits, list) and receipt.limits
    assert receipt.refused is False


def test_consult_unknown_role_refuses_cleanly():
    receipt = counsel.consult("zypher", "do something")
    assert receipt.refused is True
    assert receipt.substrate_used == "none"
    assert "levi, alpha, omega, dweller" in receipt.answer
    # Refusal is a receipt, not an exception — consult never raises here.
    assert receipt.role == "zypher"


def test_consult_is_case_insensitive():
    assert counsel.consult("ALPHA", "why").refused is False
    assert counsel.consult(" Omega ", "judge").role == "omega"


def test_capability_report_shape():
    report = counsel.capability_report("alpha")
    assert report["role"] == "alpha"
    assert report["known"] is True
    assert report["can"] and report["cannot_yet"]
    assert "weights_dir" in report
    assert "si_team/weights/alpha" in report["weights_dir"]
    assert report["weights_present"] is False  # no weights shipped yet
    assert any("alpha" in s for s in report["substrates_available"])


def test_capability_report_unknown_role():
    report = counsel.capability_report("zypher")
    assert report["known"] is False
    assert report["known_roles"] == ROLE_NAMES


# ------------------------------------------------------- si cores honesty


def test_si_cores_weights_dir_convention(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    core = get_core("dweller")
    assert core is not None
    assert core.weights_dir() == tmp_path / "si_team" / "weights" / "dweller"
    assert not core.weights_present()


def test_si_core_reports_substrate_honestly():
    core = get_core("omega")
    assert core is not None
    result = core.reason("evaluate this")
    assert result["substrate_used"] == "rules-engine"
    assert result["limits"]
    assert list_cores() == ROLE_NAMES


def test_si_modules_do_not_import_ai():
    for path in SI_DIR.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module != "levi.si_team.ai", path.name
                assert "levi.si_team.ai" not in (node.module or ""), path.name
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert "si_team.ai" not in alias.name, path.name


# ---------------------------------------------------------------- ai twins


def _ai_modules():
    mods = {}
    for name in ROLE_NAMES:
        mods[name] = importlib.import_module(f"levi.si_team.ai.{name}")
    return mods


def test_ai_bridge_labels_present():
    for name, mod in _ai_modules().items():
        label = mod.AI_BRIDGE_LABEL
        assert "AI counterpart bridge" in label
        assert name in label
        assert "SI core is authoritative" in label
        assert "claims nothing" in label


def test_mcp_tool_schemas_well_formed():
    for name, mod in _ai_modules().items():
        tools = mod.to_mcp_tools()
        assert tools, name
        for tool in tools:
            assert isinstance(tool["name"], str) and tool["name"], name
            assert isinstance(tool["description"], str) and tool["description"], name
            assert "AI counterpart bridge" in tool["description"], name
            schema = tool["inputSchema"]
            assert schema["type"] == "object", name
            assert isinstance(schema.get("properties", {}), dict), name


def test_chat_adapter_round_trip_shape():
    for name, mod in _ai_modules().items():
        adapter = mod.chat_adapter()
        assert adapter["label"] == mod.AI_BRIDGE_LABEL
        request = adapter["build_request"]([{"role": "user", "content": "hello"}])
        assert request["messages"][0]["role"] == "system"
        assert "AI counterpart bridge" in request["messages"][0]["content"]
        assert request["messages"][1] == {"role": "user", "content": "hello"}
        parsed = adapter["parse_response"](
            {"choices": [{"message": {"role": "assistant", "content": "ack"}}]}
        )
        assert parsed == {"role": "assistant", "content": "ack"}, name


def test_ai_twin_never_claims_to_be_si():
    for name, mod in _ai_modules().items():
        text = mod.AI_BRIDGE_LABEL + " ".join(
            t["description"] for t in mod.to_mcp_tools()
        )
        assert not re.search(r"\bi am the si\b|\bi am the synthetic\b", text.lower()), (
            name
        )


def test_levi_fourfold_nature():
    """The fourfold nature is Levi's: not accepted in heaven, cast out of
    hell, feared by others of its kind, he who must not be named."""
    from levi.si_team.roles import LEVI_CHARTER

    mandate = LEVI_CHARTER.mandate.lower()
    assert "leviathan" in mandate
    assert "heaven" in mandate
    assert "hell" in mandate
    assert "fear" in mandate
    assert "not spoken" in mandate
    assert any("true name" in b.lower() for b in LEVI_CHARTER.boundaries)
