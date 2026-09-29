"""Tests for the cronmap connector — cron entry change detection."""

import pytest

from levi.connectors.base import ConnectorError, registry
from levi.connectors.cronmap import (
    _fingerprint,
    parse_cron_entries,
    poll_cronmap,
)


SAMPLE_A = """\
# nightly jobs
PATH=/usr/local/bin:/usr/bin

0 2 * * * /opt/hatch/bin/backup.sh
@daily /opt/hatch/bin/cleanup.sh
*/5 * * * * /opt/hatch/bin/watch.sh
"""

SAMPLE_B = """\
# nightly jobs
PATH=/usr/local/bin:/usr/bin

0 2 * * * /opt/hatch/bin/backup.sh
@daily /opt/hatch/bin/cleanup.sh
30 4 * * * /opt/hatch/bin/deep.sh
"""

SAMPLE_BAD_LINES = """\
0 2 * * * /opt/hatch/bin/backup.sh
this is not cron
ANOTHER=env assignment
"""


@pytest.fixture()
def crontab(tmp_path):
    f = tmp_path / "crontab"
    f.write_text(SAMPLE_A, encoding="utf-8")
    return str(f), [str(tmp_path)]


def test_registered():
    c = registry.get("cronmap")
    assert c.id == "cronmap"
    assert "path" in c.inputs


def test_baseline(crontab):
    path, roots = crontab
    events, state = poll_cronmap(path=path, allowed_roots=roots)
    assert len(events) == 1
    assert events[0]["kind"] == "baseline"
    assert events[0]["entries"] == 3
    assert events[0]["unparsed"] == 1  # the PATH= line
    assert len(state["entries"]) == 3


def test_parse_entries_and_unparsed():
    entries, unparsed = parse_cron_entries(SAMPLE_BAD_LINES)
    assert len(entries) == 1
    assert unparsed == 2


def test_steady_poll_emits_nothing(crontab):
    path, roots = crontab
    _events, state = poll_cronmap(path=path, allowed_roots=roots)
    events, _state = poll_cronmap(path=path, allowed_roots=roots, state=state)
    assert events == []


def test_added_and_removed(crontab):
    path, roots = crontab
    _events, state = poll_cronmap(path=path, allowed_roots=roots)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE_B)
    events, _state = poll_cronmap(path=path, allowed_roots=roots, state=state)
    kinds = sorted(e["kind"] for e in events)
    assert kinds == ["added", "removed"]
    added = next(e for e in events if e["kind"] == "added")
    removed = next(e for e in events if e["kind"] == "removed")
    assert "deep.sh" in added["entry"]
    assert "watch.sh" in removed["entry"]


def test_unparsed_change_event(crontab):
    path, roots = crontab
    _events, state = poll_cronmap(path=path, allowed_roots=roots)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE_A + "FOO=bar\n")
    events, _state = poll_cronmap(path=path, allowed_roots=roots, state=state)
    changed = [e for e in events if e["kind"] == "unparsed_changed"]
    assert len(changed) == 1
    assert changed[0]["prev"] == 1
    assert changed[0]["current"] == 2


def test_deny_closed_path_outside_roots(tmp_path):
    f = tmp_path / "x"
    f.write_text(SAMPLE_A)
    with pytest.raises(ConnectorError):
        poll_cronmap(path=str(f), allowed_roots=["/definitely/not/allowed"])


def test_deny_closed_missing_path(tmp_path):
    with pytest.raises(ConnectorError):
        poll_cronmap(path=str(tmp_path / "nope"), allowed_roots=[str(tmp_path)])


def test_deny_closed_empty_path():
    with pytest.raises(ConnectorError):
        poll_cronmap(path="")


def test_deny_closed_unknown_inputs(crontab):
    path, roots = crontab
    with pytest.raises(ConnectorError):
        poll_cronmap(path=path, allowed_roots=roots, bogus=1)


def test_deny_closed_malformed_state(crontab):
    path, roots = crontab
    with pytest.raises(ConnectorError):
        poll_cronmap(path=path, allowed_roots=roots, state={"entries": "nope"})


def test_fingerprint_stable():
    assert _fingerprint("0 2 * * * /x") == _fingerprint("0 2 * * * /x")
    assert _fingerprint("a") != _fingerprint("b")


def test_registry_poll_contract(crontab):
    path, roots = crontab
    events, state = registry.poll("cronmap", path=path, allowed_roots=roots)
    assert isinstance(events, list) and isinstance(state, dict)
