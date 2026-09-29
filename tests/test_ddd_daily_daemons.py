# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Proof for the DDD daily income daemons (law → guard → prove).

Laws under test:
  L1 draft-only (advisory_only/draft_only flags; drafts DRAFT-labeled,
     land in the inbox dir, never escape it)
  L2/L3 no payment, no outbound (outbound kinds refused loudly; static
     scan: no forbidden tokens/defs in daemon sources)
  L4 honest zero-state (missing/empty queue → honest receipt; rows are
     never invented)
  L5 multi-run idempotent (3x/day; each run drafts only the NEXT undrafted
     queue rows — a row drafted once is never drafted again the same day)
  L6 named sites only (audit daemon reads only queued URLs; unreachable
     pages reported honestly, never invented)
"""

from __future__ import annotations

import csv
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from levi.ddd.daemons import DAEMON_IDS
from levi.ddd.daemons import base as daemon_base
from levi.ddd.daemons.audit_daemon import AuditDaemon, _polite_read
from levi.ddd.daemons.leads_daemon import LeadsDaemon
from levi.ddd.daemons.listing_daemon import ListingDaemon
from levi.ddd.daemons.register import AUTOMATION_SPECS, register_all
from levi.ddd.daemons.skills import DAEMON_SKILLS
from levi.dynasty.dna import AgentError, DynastyAgent

DAEMON_CLASSES = (AuditDaemon, ListingDaemon, LeadsDaemon)

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,31}$")

#: Tokens that must never appear in a draft-only daemon's source.
FORBIDDEN_TOKENS = [
    "smtplib",
    "stripe",
    "paypal",
    "twilio",
    "requests.post",
    "requests.put",
    "requests.delete",
    ".publish(",
    "auto_post",
    "send_email",
    "send_sms",
    "create_charge",
    "charge_customer",
    "subprocess",
]

#: Method definitions that must never exist on a draft-only daemon.
FORBIDDEN_DEFS = re.compile(
    r"^\s*def\s+(send|publish|charge|post|contact)\s*\(", re.MULTILINE
)


def _daemon(tmp_path: Path, cls, **kw):
    qd = tmp_path / "queues"
    idx = tmp_path / "inbox"
    rd = tmp_path / "receipts"
    qd.mkdir(exist_ok=True)
    idx.mkdir(exist_ok=True)
    rd.mkdir(exist_ok=True)
    return cls(queues_dir=qd, inbox_dir=idx, receipts_dir=rd, **kw)


def _write_queue(tmp_path: Path, filename: str, header: str, rows: list) -> Path:
    qd = tmp_path / "queues"
    qd.mkdir(exist_ok=True)
    path = qd / filename
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header.split(","))
        w.writerows(rows)
    return path


# ── registration / identity ──────────────────────────────────────────


def test_three_daemons_registered():
    assert DAEMON_IDS == ("audit-daemon", "listing-daemon", "leads-daemon")
    assert len(DAEMON_CLASSES) == 3
    for cls in DAEMON_CLASSES:
        assert issubclass(cls, DynastyAgent)
        assert issubclass(cls, daemon_base.DDDDailyDaemon)


def test_ids_unique_valid_and_names_provisional():
    ids = [c.daemon_id for c in DAEMON_CLASSES]
    assert len(set(ids)) == 3 == len(set(DAEMON_IDS))
    for cls in DAEMON_CLASSES:
        assert _ID_RE.match(cls.daemon_id), f"bad id {cls.daemon_id!r}"
        assert "provisional" in cls.display_name.lower()
        assert cls.queue_filename
        assert cls.queue_columns


def test_queue_columns_match_templates():
    repo = Path(__file__).resolve().parents[1] / "core" / "levi" / "ddd" / "daemons"
    for cls in DAEMON_CLASSES:
        tpl = repo / "queue_templates" / cls.queue_filename
        assert tpl.is_file(), f"missing template for {cls.daemon_id}"
        with tpl.open(encoding="utf-8") as fh:
            header = next(csv.reader(fh))
        assert tuple(header) == tuple(cls.queue_columns), cls.daemon_id


def test_templates_have_headers_only_zero_data_rows():
    repo = Path(__file__).resolve().parents[1] / "core" / "levi" / "ddd" / "daemons"
    for name in ("prospects.csv", "inventory.csv", "leads.csv"):
        tpl = repo / "queue_templates" / name
        with tpl.open(encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        assert len(rows) == 1, f"{name} must carry headers only — no fake data"


# ── L1/L2/L3: draft-only, no payment, no outbound ────────────────────


def test_advisory_only_flags_on_every_daemon(tmp_path):
    for cls in DAEMON_CLASSES:
        assert cls.advisory_only is True, cls.__name__
        assert cls.draft_only is True, cls.__name__
        assert cls.outbound_actions == (), cls.__name__
        assert cls.allowed_wares == (), cls.__name__
        d = _daemon(tmp_path, cls)
        assert d.advisory_only is True
        assert d.draft_only is True


def test_outbound_kinds_refused_loudly(tmp_path):
    for cls in DAEMON_CLASSES:
        d = _daemon(tmp_path, cls)
        for kind in ("send", "publish", "post", "charge", "outreach", "contact"):
            with pytest.raises(AgentError):
                d.handle({"kind": kind})
            with pytest.raises(AgentError):
                d.refuse_outbound(kind)


def test_no_forbidden_tokens_or_defs_in_daemon_sources():
    pkg = Path(daemon_base.__file__).parent
    for mod in (
        "base.py",
        "audit_daemon.py",
        "listing_daemon.py",
        "leads_daemon.py",
        "skills.py",
    ):
        src = (pkg / mod).read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert token not in src, f"{mod} contains forbidden {token!r}"
        assert not FORBIDDEN_DEFS.search(src), f"{mod} defines an outbound method"


# ── L4: honest zero-state — never invents ───────────────────────────


def test_missing_queue_yields_honest_no_queue_receipt(tmp_path):
    for cls in DAEMON_CLASSES:
        d = _daemon(tmp_path, cls)
        receipt = d.run_daily()
        assert receipt["status"] == "no-queue"
        assert receipt["rows_seen"] == 0
        assert receipt["drafts_written"] == []
        assert "nothing" in receipt["note"].lower()
        # inbox untouched
        assert not list((tmp_path / "inbox").glob("*.md"))


def test_empty_queue_yields_honest_empty_receipt(tmp_path):
    for cls in DAEMON_CLASSES:
        _write_queue(tmp_path, cls.queue_filename, ",".join(cls.queue_columns), [])
        d = _daemon(tmp_path, cls)
        receipt = d.run_daily()
        assert receipt["status"] == "empty-queue"
        assert receipt["rows_seen"] == 0
        assert receipt["drafts_written"] == []
        assert not list((tmp_path / "inbox").glob("*.md"))


def test_never_invents_rows(tmp_path):
    _write_queue(
        tmp_path,
        "prospects.csv",
        "business,url,contact_name,notes",
        [["Acme Bakery", "http://127.0.0.1:9/", "Ann", ""]],
    )
    d = _daemon(tmp_path, AuditDaemon)
    receipt = d.run_daily()
    assert receipt["rows_seen"] == 1
    assert receipt["rows_used"] == 1
    written = receipt["drafts_written"]
    assert len(written) == 1
    body = Path(written[0]).read_text(encoding="utf-8")
    assert "Acme Bakery" in body
    assert "DRAFT" in body
    # nothing beyond the one queued row appears as a business section
    sections = re.findall(r"^## (?!#)", body, re.MULTILINE)
    assert len(sections) == 1


# ── L1: drafts land in the inbox, labeled, confined ─────────────────


def test_drafts_land_in_inbox_labeled_and_confined(tmp_path):
    _write_queue(
        tmp_path,
        "inventory.csv",
        "item,description,keywords,condition,cost_basis,photo_ref",
        [["Widget", "A fine widget", "widget,gadget", "like new", "20", ""]],
    )
    d = _daemon(tmp_path, ListingDaemon)
    receipt = d.run_daily()
    assert receipt["status"] == "ok"
    inbox = tmp_path / "inbox"
    files = list(inbox.glob("*.md"))
    assert len(files) == 1
    body = files[0].read_text(encoding="utf-8")
    assert "DRAFT" in body
    assert "never posted" in body.lower()
    assert "Widget" in body
    assert "ESTIMATE" in body  # pricing labeled honestly
    # confined to the inbox dir
    assert inbox.resolve() in files[0].resolve().parents


# ── L5: multi-run idempotent (row-level dedupe) ─────────────────────


def test_second_run_same_day_writes_nothing_new(tmp_path):
    _write_queue(
        tmp_path,
        "inventory.csv",
        "item,description,keywords,condition,cost_basis,photo_ref",
        [["Widget", "desc", "kw", "new", "10", ""]],
    )
    d = _daemon(tmp_path, ListingDaemon)
    first = d.run_daily()
    assert first["status"] == "ok"
    before = list((tmp_path / "inbox").glob("*.md"))
    second = d.run_daily()
    assert second["status"] == "already-drafted"
    assert "already drafted" in second["note"].lower()
    after = list((tmp_path / "inbox").glob("*.md"))
    assert before == after


def test_second_run_drafts_only_new_rows(tmp_path):
    """Row-level dedupe: run 2 drafts the NEXT rows, never re-drafts."""
    _write_queue(
        tmp_path,
        "leads.csv",
        "business,review_text,rating,source,contact_name,notes",
        [
            ["Bistro Nine", "Great tacos!", "5", "Google", "Maya", ""],
            ["Tire Barn", "Waited 3 hours", "2", "Facebook", "Sam", ""],
        ],
    )
    d = _daemon(tmp_path, LeadsDaemon)
    first = d.run_daily()
    assert first["status"] == "ok"
    assert first["rows_used"] == 2
    body1 = Path(first["drafts_written"][0]).read_text(encoding="utf-8")
    assert "Bistro Nine" in body1 and "Tire Barn" in body1
    # new lead lands in the queue
    with (tmp_path / "queues" / "leads.csv").open("a") as fh:
        fh.write("Pizza Cove,Best pie in town,5,Google,Lee,\n")
    second = d.run_daily()
    assert second["status"] == "ok"
    assert second["rows_seen"] == 3
    assert second["rows_used"] == 1  # only the new row
    body2 = Path(second["drafts_written"][0]).read_text(encoding="utf-8")
    assert "Pizza Cove" in body2
    assert "Bistro Nine" not in body2  # never re-drafted
    assert "Tire Barn" not in body2


def test_duplicate_row_readded_is_skipped(tmp_path):
    """An identical row re-added later is the same signature → skipped."""
    _write_queue(
        tmp_path,
        "leads.csv",
        "business,review_text,rating,source,contact_name,notes",
        [["Bistro Nine", "Great tacos!", "5", "Google", "Maya", ""]],
    )
    d = _daemon(tmp_path, LeadsDaemon)
    assert d.run_daily()["status"] == "ok"
    # identical row re-appended (e.g. re-exported queue)
    with (tmp_path / "queues" / "leads.csv").open("a") as fh:
        fh.write("Bistro Nine,Great tacos!,5,Google,Maya,\n")
    receipt = d.run_daily()
    assert receipt["rows_seen"] == 2
    assert receipt["rows_used"] == 0
    assert receipt["status"] == "already-drafted"


def test_row_signatures_stable():
    d = LeadsDaemon()
    row = {
        "business": "X",
        "review_text": "hi",
        "rating": "5",
        "source": "",
        "contact_name": "",
        "notes": "",
    }
    assert d._row_signature(row) == d._row_signature(dict(row))


# ── L6: named sites only, polite reads, honest failures ─────────────


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = (
            "<html><head><title>Fixture Shop</title>"
            '<meta name="description" content="A fixture.">'
            "</head><body>"
            '<img src="a.jpg"><img src="b.jpg" alt="bee">'
            '<a href="/in">in</a><a href="https://example.com/x">out</a>'
            "</body></html>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture()
def loopback_url():
    server = HTTPServer(("127.0.0.1", 0), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    thread.join()


def test_polite_read_measures_what_it_sees(loopback_url):
    facts = _polite_read(loopback_url)
    assert facts["ok"] is True
    assert facts["title"] == "Fixture Shop"
    assert facts["meta_description"] == "A fixture."
    assert facts["has_viewport"] is False  # measured missing
    assert facts["imgs_total"] == 2
    assert facts["imgs_without_alt"] == 1
    assert facts["links_internal"] == 1
    assert facts["links_external"] == 1
    assert "first_byte_s" in facts  # measured, approximate


def test_polite_read_unreachable_is_honest():
    facts = _polite_read("http://127.0.0.1:9/")
    assert facts["ok"] is False
    assert "unreachable" in facts["reason"]


def test_polite_read_rejects_non_http():
    facts = _polite_read("ftp://example.com/x")
    assert facts["ok"] is False


def test_audit_draft_marks_unreachable_honestly(tmp_path):
    _write_queue(
        tmp_path,
        "prospects.csv",
        "business,url,contact_name,notes",
        [["Dead Site Co", "http://127.0.0.1:9/", "", ""]],
    )
    d = _daemon(tmp_path, AuditDaemon)
    receipt = d.run_daily()
    body = Path(receipt["drafts_written"][0]).read_text(encoding="utf-8")
    assert "unreachable" in body.lower()
    assert "No findings invented" in body


# ── skills + automation specs ───────────────────────────────────────


def test_daemon_skills_shape():
    assert len(DAEMON_SKILLS) == 3
    ids = [s.id for s in DAEMON_SKILLS]
    assert ids == ["ddd.daily-audit", "ddd.daily-listing", "ddd.daily-leads"]
    for s in DAEMON_SKILLS:
        assert s.category == "ddd"
        assert int(s.risk_level) == 0  # INFO
        assert s.permissions == []
        assert s.requires_confirmation is False
        assert s.handler is not None


def test_automation_specs_shape():
    assert len(AUTOMATION_SPECS) == 3
    ids = [a["id"] for a in AUTOMATION_SPECS]
    assert ids == ["ddd-daily-audit", "ddd-daily-listing", "ddd-daily-leads"]
    skill_ids = {s.id for s in DAEMON_SKILLS}
    for spec in AUTOMATION_SPECS:
        assert spec["trigger"].value == "schedule"
        assert spec["risk_ceiling"] == 0
        assert "08:00/13:00/18:00 America/Chicago" in spec["trigger_config"]["schedule"]
        assert spec["trigger_config"]["cron_job_id"] == spec["id"]
        for action in spec["actions"]:
            assert action.skill_id in skill_ids
            assert action.risk_level == 0


def test_register_all_is_idempotent(tmp_path):
    """register_all() twice → second run creates nothing new."""
    data_dir = tmp_path / "autos"
    first = register_all(data_dir=data_dir)
    assert sorted(first) == ["ddd-daily-audit", "ddd-daily-leads", "ddd-daily-listing"]
    second = register_all(data_dir=data_dir)
    assert second == []


def test_leads_draft_labels_and_never_posts(tmp_path):
    """Leads daemon: review-reply drafts are DRAFT-labeled and never posted
    (hard rule — machine drafts, human posts); nobody is contacted."""
    _write_queue(
        tmp_path,
        "leads.csv",
        "business,review_text,rating,source,contact_name,notes",
        [
            ["Bistro Nine", "Great tacos!", "5", "Google", "Maya", ""],
            ["Tire Barn", "Waited 3 hours", "2", "Facebook", "Sam", ""],
        ],
    )
    d = _daemon(tmp_path, LeadsDaemon)
    receipt = d.run_daily()
    assert receipt["status"] == "ok"
    assert receipt["rows_seen"] == 2
    assert receipt["rows_used"] == 2
    assert len(receipt["drafts_written"]) == 1
    body = Path(receipt["drafts_written"][0]).read_text(encoding="utf-8")
    assert "DRAFT" in body
    assert "NEVER POSTED" in body  # review-reply hard rule, stated aloud
    assert "nobody contacted" in body.lower()
    assert "Bistro Nine" in body
    assert "Tire Barn" in body
    # confined to the inbox dir
    inbox = tmp_path / "inbox"
    assert inbox.resolve() in Path(receipt["drafts_written"][0]).resolve().parents


def test_leads_daemon_caps_at_five_rows_per_day(tmp_path):
    """6+ lead rows → only 5 drafted."""
    _write_queue(
        tmp_path,
        "leads.csv",
        "business,review_text,rating,source,contact_name,notes",
        [[f"Biz {i}", "ok", "5", "", "", ""] for i in range(6)],
    )
    d = _daemon(tmp_path, LeadsDaemon)
    receipt = d.run_daily()
    assert receipt["status"] == "ok"
    assert receipt["rows_seen"] == 6
    assert receipt["rows_used"] == 5
