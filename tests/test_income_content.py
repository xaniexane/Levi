"""Tests for Income Batch B (content-engines, slots 21-32).

Covers: registry presence (ids, slots, kind), run() smoke per generator
(dry-run + real), dry-run safety (no deliverable files), entry-price
bounds, and end-to-end run via engine.run_generator.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from levi.income import engine as eng  # noqa: E402
import levi.income.gen_content  # noqa: E402,F401  (self-registers)

EXPECTED = {
    21: ("newsletter-drafter", 3.0),
    22: ("changelog-composer", 2.0),
    23: ("product-description-forge", 4.0),
    24: ("faq-builder", 2.5),
    25: ("meeting-notes-structurer", 2.0),
    26: ("invoice-pack", 3.0),
    27: ("contract-lite-kit", 4.0),
    28: ("resume-kit", 5.0),
    29: ("study-guide-builder", 3.0),
    30: ("caption-forge", 2.0),
    31: ("press-release-drafter", 4.0),
    32: ("lesson-plan-builder", 3.0),
}

SAMPLE_PARAMS = {
    "newsletter-drafter": {
        "title": "Test Weekly",
        "bullets": ["Launch: We shipped v2", "Hiring: Two roles open"],
        "cta": "Subscribe today",
    },
    "changelog-composer": {
        "version": "1.2.0",
        "date": "2026-09-17",
        "entries": [
            {"type": "added", "text": "Dark mode toggle"},
            {"type": "fixed", "text": "Login crash on Android"},
        ],
    },
    "product-description-forge": {
        "name": "WidgetPro",
        "audience": "small teams",
        "specs": [
            {"feature": "One-click export", "benefit": "Save 2 hours a week"},
            {"feature": "Offline mode", "benefit": "Work anywhere"},
        ],
    },
    "faq-builder": {
        "title": "Support FAQ",
        "categories": [
            {"name": "Billing",
             "faqs": [{"q": "How do I cancel?", "a": "Email support."}]},
        ],
    },
    "meeting-notes-structurer": {
        "title": "Sprint planning",
        "date": "2026-09-17",
        "attendees": ["Ava", "Ben"],
        "notes": "Discussion\nDECISION: Ship Friday\nACTION: Write release notes (Ava)",
    },
    "invoice-pack": {
        "doctype": "invoice",
        "business": "Test Co",
        "client": "Client X",
        "number": "INV-TEST-1",
        "tax_rate": 0.1,
        "items": [{"desc": "Consulting", "qty": 2, "rate": 50.0}],
    },
    "contract-lite-kit": {
        "provider": "Provider P",
        "client": "Client C",
        "service": "Web design",
        "start_date": "2026-10-01",
        "term": "3 months",
        "fee": "$1,500",
        "payment_terms": "Net 15",
    },
    "resume-kit": {
        "name": "Test User",
        "contact": ["test@example.com"],
        "summary": "Builder of things.",
        "skills": ["Python", "Writing"],
        "experience": [{"role": "Dev", "org": "Acme", "dates": "2020-2024",
                        "bullets": ["Shipped product X"]}],
        "target_role": "Engineer",
        "target_company": "Acme",
    },
    "study-guide-builder": {
        "subject": "Biology",
        "objectives": ["Name cell parts"],
        "key_terms": [{"term": "Mitochondria", "definition": "The powerhouse"}],
        "quiz": [{"q": "What is ATP?", "a": "Energy currency"}],
    },
    "caption-forge": {
        "topic": "Morning coffee ritual",
        "platform": "instagram",
        "tone": "playful",
        "key_points": ["Slow mornings win"],
        "cta": "Link in bio",
    },
    "press-release-drafter": {
        "organization": "Test Org",
        "headline": "Test Org launches thing",
        "location": "Springfield, IL",
        "date": "2026-09-17",
        "facts": ["The thing is great.", "Available now."],
        "quote": "We are thrilled.",
        "quote_by": "Jane Doe, CEO",
    },
    "lesson-plan-builder": {
        "subject": "Math",
        "title": "Fractions intro",
        "grade": "3",
        "objectives": ["Identify halves"],
        "activities": [{"name": "Warmup", "minutes": 5, "desc": "Count objects."}],
        "assessment": "Exit ticket quiz.",
    },
}


def _tmp_home():
    return Path(tempfile.mkdtemp(prefix="levi-income-test-"))


class TestBatchBRegistry(unittest.TestCase):
    def test_all_twelve_registered(self):
        self.assertEqual(len(EXPECTED), 12)
        for slot, (gid, price) in EXPECTED.items():
            gen = eng.REGISTRY.get(gid)
            self.assertEqual(eng.REGISTRY.slot_of(gid), slot, gid)
            self.assertEqual(gen.kind, "content-engine", gid)
            self.assertEqual(gen.version, "1.0.0", gid)
            self.assertEqual(gen.entry_price_usd, price, gid)
            self.assertTrue(callable(gen.run), gid)

    def test_no_slot_collisions_and_unique_ids(self):
        listed = eng.REGISTRY.list()
        slots = [e["slot"] for e in listed]
        ids = [e["id"] for e in listed]
        self.assertEqual(len(slots), len(set(slots)))
        self.assertEqual(len(ids), len(set(ids)))

    def test_entry_prices_within_doctrine(self):
        for slot, (gid, price) in EXPECTED.items():
            self.assertIsNotNone(price, gid)
            self.assertGreaterEqual(price, 1.0, gid)
            self.assertLessEqual(price, 5.0, gid)

    def test_expected_artifacts_exist_in_module(self):
        # every _DEFS entry must resolve to a real callable in the module
        import levi.income.gen_content as mod
        for slot, (gid, price) in EXPECTED.items():
            fn = eng.REGISTRY.get(gid).run
            self.assertTrue(callable(fn), gid)
            self.assertIn("_run_", fn.__name__, gid)


class TestBatchBRunSmoke(unittest.TestCase):
    def _ctx(self, dry, params=None):
        return {"levi_home": _tmp_home(), "dry_run": dry,
                "params": params or {}}

    def test_dry_run_reports_without_writing(self):
        for slot, (gid, _) in EXPECTED.items():
            gen = eng.REGISTRY.get(gid)
            home = _tmp_home()
            ctx = {"levi_home": home, "dry_run": True,
                   "params": SAMPLE_PARAMS[gid]}
            report = gen.run(ctx)
            self.assertIsInstance(report, eng.WorkReport, gid)
            self.assertEqual(report.generator_id, gid, gid)
            self.assertTrue(report.produced, gid)
            self.assertTrue(report.notes, gid)
            work = home / ".levi" / "income" / "work" / gid
            self.assertFalse(work.exists(),
                             f"{gid}: dry-run must not write deliverables")

    def test_real_run_writes_artifacts(self):
        for slot, (gid, _) in EXPECTED.items():
            gen = eng.REGISTRY.get(gid)
            home = _tmp_home()
            ctx = {"levi_home": home, "dry_run": False,
                   "params": SAMPLE_PARAMS[gid]}
            report = gen.run(ctx)
            work = home / ".levi" / "income" / "work" / gid
            self.assertTrue(work.is_dir(), gid)
            written = sorted(p.name for p in work.iterdir() if p.is_file())
            self.assertEqual(sorted(report.produced), written, gid)
            for p in work.iterdir():
                self.assertGreater(p.stat().st_size, 0,
                                   f"{gid}/{p.name} must be non-empty")

    def test_quoted_amount_bounds(self):
        for slot, (gid, _) in EXPECTED.items():
            gen = eng.REGISTRY.get(gid)
            report = gen.run(self._ctx(True, SAMPLE_PARAMS[gid]))
            q = report.quoted_amount_usd
            self.assertTrue(q is None or 1.0 <= q <= 5.0,
                            f"{gid}: quoted {q!r} outside 1.0-5.0")

    def test_minimal_params_do_not_crash(self):
        for slot, (gid, _) in EXPECTED.items():
            gen = eng.REGISTRY.get(gid)
            home = _tmp_home()
            report = gen.run({"levi_home": home, "dry_run": False, "params": {}})
            self.assertIsInstance(report, eng.WorkReport, gid)
            self.assertTrue(report.produced, gid)

    def test_json_artifacts_parse(self):
        for gid in ("changelog-composer", "faq-builder",
                    "meeting-notes-structurer", "study-guide-builder",
                    "caption-forge", "lesson-plan-builder"):
            gen = eng.REGISTRY.get(gid)
            home = _tmp_home()
            gen.run({"levi_home": home, "dry_run": False,
                     "params": SAMPLE_PARAMS[gid]})
            work = home / ".levi" / "income" / "work" / gid
            for jf in work.glob("*.json"):
                json.loads(jf.read_text(encoding="utf-8"))

    def test_invoice_math(self):
        gen = eng.REGISTRY.get("invoice-pack")
        home = _tmp_home()
        gen.run({"levi_home": home, "dry_run": False,
                 "params": SAMPLE_PARAMS["invoice-pack"]})
        txt = (home / ".levi" / "income" / "work" / "invoice-pack"
               / "INV-TEST-1.txt").read_text()
        # 2 x $50 = $100 subtotal, 10% tax = $10, total $110
        self.assertIn("110.00", txt)

    def test_meeting_notes_extraction(self):
        gen = eng.REGISTRY.get("meeting-notes-structurer")
        home = _tmp_home()
        gen.run({"levi_home": home, "dry_run": False,
                 "params": SAMPLE_PARAMS["meeting-notes-structurer"]})
        data = json.loads(
            (home / ".levi" / "income" / "work" / "meeting-notes-structurer"
             / "minutes.json").read_text())
        self.assertEqual(data["decisions"], ["Ship Friday"])
        self.assertEqual(data["actions"][0]["action"], "Write release notes")
        self.assertEqual(data["actions"][0]["owner"], "Ava")

    def test_engine_run_generator_end_to_end(self):
        old = os.environ.get("LEVI_HOME")
        home = _tmp_home()
        os.environ["LEVI_HOME"] = str(home)
        try:
            for slot, (gid, _) in EXPECTED.items():
                rec = eng.run_generator(gid, dry_run=True,
                                        params=SAMPLE_PARAMS[gid])
                self.assertEqual(rec["generator_id"], gid, gid)
                self.assertEqual(rec["slot"], slot, gid)
                self.assertTrue(rec["dry_run"], gid)
                self.assertTrue(rec["produced"], gid)
        finally:
            if old is None:
                os.environ.pop("LEVI_HOME", None)
            else:
                os.environ["LEVI_HOME"] = old

    def test_record_income_not_called_by_run(self):
        # runs record WorkReports, never income events
        old = os.environ.get("LEVI_HOME")
        home = _tmp_home()
        os.environ["LEVI_HOME"] = str(home)
        try:
            eng.run_generator("newsletter-drafter", dry_run=False,
                              params=SAMPLE_PARAMS["newsletter-drafter"])
            self.assertFalse((home / ".levi" / "income" / "events.jsonl").exists())
        finally:
            if old is None:
                os.environ.pop("LEVI_HOME", None)
            else:
                os.environ["LEVI_HOME"] = old


if __name__ == "__main__":
    unittest.main()
