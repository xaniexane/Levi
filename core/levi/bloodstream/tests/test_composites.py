"""Interpenetration composition law: strictest (maximum) risk ceiling wins.

Composites are nameable, testable, reversible: register() fails fast on
dangling part references; unregister() removes the name completely.
"""
import pytest

from levi.bloodstream.composites import Composite, CompositeRegistry


class _Part:
    def __init__(self, **attrs):
        for k, v in attrs.items():
            setattr(self, k, v)


class _Dict:
    def __init__(self, items):
        self._items = items

    def get(self, key):
        return self._items.get(key)


@pytest.fixture
def parts():
    return dict(
        skills=_Dict({
            "file_read": _Part(risk_level=1),
            "shell_exec": _Part(risk_level=3),
        }),
        specialists=_Dict({
            "researcher": _Part(risk_ceiling=2),
        }),
        automations=_Dict({
            "nightly_digest": _Part(risk_ceiling=1),
        }),
    )


@pytest.fixture
def registry(data_dir):
    return CompositeRegistry(data_dir=data_dir / "bloodstream")


def test_strictest_ceiling_inheritance(parts, registry):
    comp = Composite(
        name="ops",
        persona_id="mentor",  # personas are lenses: contribute 0
        skill_ids=["file_read", "shell_exec"],
        specialist_ids=["researcher"],
        automation_ids=["nightly_digest"],
    )
    registry.register(comp, **parts)
    assert registry.risk_ceiling(comp, **parts) == 3  # max(1, 3, 2, 1, 0)


def test_persona_only_composite_has_zero_ceiling(parts, registry):
    comp = Composite(name="chat", persona_id="friend")
    registry.register(comp, **parts)
    assert registry.risk_ceiling(comp, **parts) == 0


def test_register_fails_fast_on_unknown_part(parts, registry):
    comp = Composite(name="bad", skill_ids=["no_such_skill"])
    with pytest.raises(ValueError, match="unknown parts"):
        registry.register(comp, **parts)
    assert registry.get("bad") is None


def test_unregister_is_reversible(parts, registry):
    comp = Composite(name="temp", skill_ids=["file_read"])
    registry.register(comp, **parts)
    assert registry.get("temp") is not None
    assert registry.unregister("temp") is True
    assert registry.get("temp") is None
    assert registry.unregister("temp") is False


def test_registry_persists_and_reloads(parts, registry, data_dir):
    comp = Composite(name="ops", skill_ids=["shell_exec"],
                     description="ops bundle")
    registry.register(comp, **parts)
    reloaded = CompositeRegistry(data_dir=data_dir / "bloodstream")
    got = reloaded.get("ops")
    assert got is not None
    assert got.skill_ids == ["shell_exec"]
    assert got.description == "ops bundle"
    assert reloaded.risk_ceiling(got, **parts) == 3
