"""Hermetic tests for levi.ux.dynamic — the dynamic-UI protocol emitter.

The emitter is the agent-side half of the allowlist: everything it builds
must be protocol-compliant, and everything protocol-violating must raise
DynamicUIError before it can reach the client. No network, no filesystem.
"""

from __future__ import annotations

import json

import pytest

from levi.ux import dynamic
from levi.ux.dynamic import (
    DynamicUIError,
    buttons,
    card,
    envelope,
    form,
    intent_action,
    progress,
    text,
    url_action,
    validate_payload,
)


def good_button(label: str = "Go") -> dict:
    return {"label": label, "action": intent_action("demo.run")}


# ---------------------------------------------------------------- envelope


def test_envelope_shape_is_protocol_compliant():
    payload = envelope(
        text("Hello"),
        buttons([good_button()]),
        card("Title", "Body", [good_button("OK")]),
        form(
            [{"name": "goal", "label": "Goal", "field": "text", "required": True}],
            "Save",
            intent_action("goal.set"),
            title="Set a goal",
        ),
        progress(0.5, label="Loading"),
        progress(label="Working", indeterminate=True),
    )
    assert payload["kind"] == "dynamic-ui"
    assert payload["version"] == 1
    assert len(payload["elements"]) == 6
    # Must survive a JSON round-trip as plain data.
    assert json.loads(json.dumps(payload)) == payload


def test_envelope_rejects_empty_and_oversized():
    with pytest.raises(DynamicUIError):
        envelope()
    with pytest.raises(DynamicUIError):
        envelope(*([text("x")] * 17))


def test_envelope_requires_kind_and_version():
    with pytest.raises(DynamicUIError):
        validate_payload({"version": 1, "elements": [text("x")]})
    with pytest.raises(DynamicUIError):
        validate_payload({"kind": "dynamic-ui", "version": 99, "elements": [text("x")]})
    with pytest.raises(DynamicUIError):
        validate_payload("not a dict")


# ------------------------------------------------------------- element types


def test_unknown_element_type_rejected():
    with pytest.raises(DynamicUIError, match="unknown element type"):
        validate_payload(
            {
                "kind": "dynamic-ui",
                "version": 1,
                "elements": [{"type": "video", "src": "x.mp4"}],
            }
        )


def test_unknown_field_type_rejected():
    with pytest.raises(DynamicUIError, match="field type"):
        form(
            [{"name": "d", "label": "D", "field": "date"}], "Save", intent_action("x.y")
        )


def test_unknown_button_style_rejected():
    with pytest.raises(DynamicUIError, match="button style"):
        buttons([{"label": "Go", "action": intent_action("x.y"), "style": "rainbow"}])


def test_unknown_text_tone_rejected():
    with pytest.raises(DynamicUIError, match="tone"):
        text("hi", tone="spicy")


def test_unknown_action_kind_rejected():
    with pytest.raises(DynamicUIError, match="unknown action kind"):
        buttons([{"label": "Go", "action": {"kind": "exec", "cmd": "rm -rf ~"}}])


def test_non_dict_element_rejected():
    with pytest.raises(DynamicUIError, match="must be a dict"):
        validate_payload(
            {"kind": "dynamic-ui", "version": 1, "elements": ["just a string"]}
        )


# -------------------------------------------------------------------- actions


def test_intent_action_allows_jsonable_args():
    act = intent_action("goal.set", {"name": "ship it", "tags": ["a", "b"], "n": 3})
    assert act == {
        "kind": "intent",
        "intent": "goal.set",
        "args": {"name": "ship it", "tags": ["a", "b"], "n": 3},
    }


def test_intent_action_rejects_non_jsonable_args():
    with pytest.raises(DynamicUIError, match="plain JSON data"):
        intent_action("goal.set", {"fn": lambda: None})
    with pytest.raises(DynamicUIError, match="keys must be strings"):
        intent_action("goal.set", {1: "x"})


def test_intent_action_rejects_bad_names():
    with pytest.raises(DynamicUIError):
        intent_action("goal set!")  # spaces / punctuation not allowed
    with pytest.raises(DynamicUIError):
        intent_action("")


def test_destructive_intent_requires_confirm():
    with pytest.raises(DynamicUIError, match="confirm=True"):
        intent_action("memory.delete")
    # confirm=True is accepted and preserved
    act = intent_action("memory.delete", confirm=True)
    assert act["confirm"] is True
    # non-destructive intents do not need it
    assert "confirm" not in intent_action("goal.set")


def test_url_action_allows_http_https():
    assert url_action("https://example.com/x")["url"] == "https://example.com/x"
    assert url_action("http://example.com")["url"] == "http://example.com"


def test_url_action_rejects_dangerous_schemes():
    for bad in (
        "javascript:alert(1)",
        "data:text/html,<h1>x</h1>",
        "file:///etc/passwd",
        "ftp://example.com/x",
    ):
        with pytest.raises(DynamicUIError, match="url scheme"):
            url_action(bad)


def test_url_action_confirms_by_default():
    assert url_action("https://example.com")["confirm"] is True


# --------------------------------------------------------------------- limits


def test_text_length_cap():
    with pytest.raises(DynamicUIError, match="exceeds"):
        text("x" * 2001)


def test_too_many_buttons_rejected():
    with pytest.raises(DynamicUIError):
        buttons([good_button(f"b{i}") for i in range(9)])


def test_too_many_form_fields_rejected():
    with pytest.raises(DynamicUIError):
        form(
            [{"name": f"f{i}", "label": "L", "field": "text"} for i in range(11)],
            "Save",
            intent_action("x.y"),
        )


def test_select_options_bounds():
    with pytest.raises(DynamicUIError, match="2–"):
        form(
            [{"name": "c", "label": "C", "field": "select", "options": ["only-one"]}],
            "Save",
            intent_action("x.y"),
        )
    with pytest.raises(DynamicUIError):
        form(
            [
                {
                    "name": "c",
                    "label": "C",
                    "field": "select",
                    "options": [f"o{i}" for i in range(13)],
                }
            ],
            "Save",
            intent_action("x.y"),
        )


def test_field_name_pattern_enforced():
    with pytest.raises(DynamicUIError, match="field name"):
        form(
            [{"name": "bad name!", "label": "L", "field": "text"}],
            "Save",
            intent_action("x.y"),
        )


def test_select_default_must_be_an_option():
    with pytest.raises(DynamicUIError, match="one of the options"):
        form(
            [
                {
                    "name": "c",
                    "label": "C",
                    "field": "select",
                    "options": ["a", "b"],
                    "default": "zzz",
                }
            ],
            "Save",
            intent_action("x.y"),
        )


def test_progress_value_clamped_and_numeric():
    assert progress(2.0)["value"] == 1.0
    assert progress(-1.0)["value"] == 0.0
    with pytest.raises(DynamicUIError, match="numeric"):
        progress(True)


# ----------------------------------------------------------------- round trip


def test_validate_payload_normalizes_raw_dict():
    raw = {
        "kind": "dynamic-ui",
        "version": 1,
        "elements": [
            {"type": "text", "text": "hi", "tone": "muted", "extra": "dropped"},
            {
                "type": "buttons",
                "buttons": [
                    {"label": "Go", "action": {"kind": "intent", "intent": "x.y"}}
                ],
            },
        ],
    }
    out = validate_payload(raw)
    assert out["elements"][0] == {"type": "text", "text": "hi", "tone": "muted"}
    assert out["elements"][1]["buttons"][0]["style"] == "primary"


def test_reexported_from_levi_ux():
    assert dynamic.envelope is envelope
    assert dynamic.DynamicUIError is DynamicUIError
    for name in (
        "text",
        "buttons",
        "card",
        "form",
        "progress",
        "intent_action",
        "url_action",
    ):
        assert callable(getattr(dynamic, name)), name
