"""Hermetic tests for the Oberon revival: actionable notes.

Listing actions never executes anything; execution is tested with an
injected fake runner. No network, no HOME writes.
"""

from levi.archive.actions import confirm_and_run, find_actions, preview, run_action
from levi.archive.record import ArchiveRecord


def _rec(**kw):
    fields = dict(
        id="arch-act",
        title="Actionable",
        era="test",
        kind="software",
        summary="s",
        mechanism="m",
        decline="d",
        revival_recipe="r",
        levi_application="a",
        rating="useful-pattern",
        status="dead",
    )
    fields.update(kw)
    return ArchiveRecord(**fields)


FENCED = """Some prose.

```levi
levi archive stats
# a comment is skipped
levi archive search transclusion
```

More prose.
"""


def test_find_actions_parses_fences():
    scan = find_actions(_rec(summary=FENCED))
    assert [a.command for a in scan.actions] == [
        "levi archive stats",
        "levi archive search transclusion",
    ]
    assert scan.actions[0].argv == ["levi", "archive", "stats"]
    assert scan.actions[0].source_field == "summary"
    assert scan.warnings == []


def test_find_actions_scans_all_text_fields():
    rec = _rec(
        mechanism="```levi\nlevi archive stats\n```",
        levi_application="```levi\nlevi archive collections\n```",
    )
    scan = find_actions(rec)
    assert len(scan.actions) == 2
    assert {a.source_field for a in scan.actions} == {"mechanism", "levi_application"}


def test_find_actions_rejects_non_levi_lines():
    rec = _rec(summary="```levi\nrm -rf /\nlevi archive stats\n```")
    scan = find_actions(rec)
    assert [a.command for a in scan.actions] == ["levi archive stats"]
    assert len(scan.warnings) == 1
    assert "not a `levi ...` command" in scan.warnings[0]


def test_find_actions_no_fences():
    scan = find_actions(_rec(summary="plain text, no fences"))
    assert scan.actions == [] and scan.warnings == []


def test_preview_lists_without_running():
    out = preview(_rec(summary=FENCED))
    assert "levi archive stats" in out
    assert "levi archive search transclusion" in out


def test_run_action_uses_injected_runner():
    seen = []

    def fake_runner(argv):
        seen.append(argv)
        return 3

    scan = find_actions(_rec(summary=FENCED))
    code = run_action(scan.actions[0], runner=fake_runner)
    assert code == 3
    assert seen == [["levi", "archive", "stats"]]


def test_confirm_and_run_yes_runs():
    ran_flag = []

    def fake_runner(argv):
        ran_flag.append(argv)
        return 0

    scan = find_actions(_rec(summary=FENCED))
    ran, code = confirm_and_run(scan.actions[0], runner=fake_runner, ask=lambda p: "y")
    assert (ran, code) == (True, 0)
    assert ran_flag == [["levi", "archive", "stats"]]


def test_confirm_and_run_refuses_by_default():
    ran_flag = []

    def fake_runner(argv):
        ran_flag.append(argv)
        return 0  # pragma: no cover - must never be called

    scan = find_actions(_rec(summary=FENCED))
    for answer in ("", "n", "no", "maybe"):
        ran, code = confirm_and_run(
            scan.actions[0], runner=fake_runner, ask=lambda p, a=answer: a
        )
        assert (ran, code) == (False, 0)
    assert ran_flag == []
