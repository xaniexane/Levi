"""Tests for the five scaffolded intelligence classes (OE/DV/KT/LM/ST).

Scaffolded 2026-09-19 at the keeper's order. These assert the declared
physics and twin-doctrine wiring — not agent instances (none minted).
"""

from levi.agent.hemisphere import (
    HEMISPHERE_DOCTRINE,
    LEFT,
    RIGHT,
    make_hemisphere,
)
from levi.ci.mapping import COUNSEL_FOR_CLASS
from levi.intelligence import (
    CLASS_PHYSICS,
    NEW_CLASSES,
    REQUIRED_FIELDS,
    get_class,
    is_new_class,
)


def test_five_classes_declared():
    assert NEW_CLASSES == ("OE", "DV", "KT", "LM", "ST")
    assert set(CLASS_PHYSICS) == set(NEW_CLASSES)


def test_every_class_carries_required_fields():
    for code in NEW_CLASSES:
        rec = CLASS_PHYSICS[code]
        for field in REQUIRED_FIELDS:
            assert field in rec, f"{code} missing {field}"
            assert isinstance(rec[field], str) and rec[field].strip(), (
                f"{code}.{field} empty"
            )
        assert rec["code"] == code
        assert rec["status"] == "scaffolded"


def test_class_codes_are_two_letter():
    for code in NEW_CLASSES:
        assert len(code) == 2 and code.isupper(), code


def test_get_class_and_is_new_class():
    assert get_class("OE")["name"] == "Omen Intelligence"
    assert get_class("DV")["name"] == "Divot Intelligence"
    assert get_class("KT")["name"] == "Knot Intelligence"
    assert get_class("LM")["name"] == "Lichen Intelligence"
    assert get_class("ST")["name"] == "Stutter Intelligence"
    for code in NEW_CLASSES:
        assert is_new_class(code)
    assert not is_new_class("XI")
    assert not is_new_class("AI")


def test_doctrine_entries_for_all_five():
    for code in NEW_CLASSES:
        assert code in HEMISPHERE_DOCTRINE, f"no doctrine for {code}"
        for hemi in (LEFT, RIGHT):
            d = HEMISPHERE_DOCTRINE[code][hemi]
            assert d["role"].strip(), f"{code}/{hemi} role empty"
            assert d["character"].strip(), f"{code}/{hemi} character empty"


def test_make_hemisphere_seats_new_classes():
    for code in NEW_CLASSES:
        for hemi in (LEFT, RIGHT):
            h = make_hemisphere(hemi, f"probe-{code.lower()}", code, "twin:probe")
            assert h.class_tag == code
            assert h.hemisphere == hemi
            assert h.role == HEMISPHERE_DOCTRINE[code][hemi]["role"]
            assert code in h.mind_descriptor


def test_no_counsel_invented_for_new_classes():
    # Counsel names come from the keeper, not from scaffolding.
    for code in NEW_CLASSES:
        assert code not in COUNSEL_FOR_CLASS, (
            f"counsel invented for {code} — remove it"
        )
