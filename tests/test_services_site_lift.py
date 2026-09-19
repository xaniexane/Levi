"""Tests for the strengthened Site Lift five-pass program."""

from types import SimpleNamespace

import pytest

from levi.services.cli import cmd_service
from levi.services.site_lift import (
    GOALS,
    AbsorbReturn,
    CheckResult,
    Compost,
    Graft,
    LiftError,
    describe_program,
    load_report,
    recommend_team,
    run_lift_program,
    save_report,
    snapshot_site,
)

FULL_PAGE = """<!doctype html><html><head>
<title>Easy Touch Massage — Springfield</title>
<meta name="description" content="Therapeutic massage in Springfield.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:title" content="Easy Touch Massage">
<script src="https://www.googletagmanager.com/gtag/js"></script>
</head><body>
<h1>Massage that actually helps</h1>
<a href="tel:+12175550137">Call now</a>
<a href="/book">Book your session</a>
<a href="/pricing">Prices & packages — from $60</a>
<a href="/gallery">See our work</a>
<a href="https://instagram.com/easytouch">Instagram</a>
<img src="room.jpg" alt="treatment room">
<form action="/contact"><input name="name"></form>
<section><h2>Testimonials</h2><p>Five stars — best massage in town.</p></section>
<section><h2>FAQ</h2><p>Frequently asked questions answered here.</p></section>
</body></html>"""

THIN_PAGE = """<html><head></head><body><p>hello</p><img src="x.jpg"></body></html>"""


def _site(tmp_path, pages):
    d = tmp_path / "site"
    d.mkdir()
    for i, html in enumerate(pages):
        (d / f"p{i}.html").write_text(html)
    return d


def test_snapshot_counts_pages(tmp_path):
    snap = snapshot_site(_site(tmp_path, [FULL_PAGE, THIN_PAGE]))
    assert snap.pages == 2
    assert snap.titles and snap.forms == 1


def test_snapshot_missing_dir():
    with pytest.raises(LiftError):
        snapshot_site("/nonexistent-site-dir-xyz")


def test_full_program_all_five_passes(tmp_path):
    site = _site(tmp_path, [FULL_PAGE, FULL_PAGE, FULL_PAGE])
    report = run_lift_program(
        site,
        provider="levi",
        grafts=[
            Graft(
                pattern="sticky booking bar",
                source="lift portfolio #12",
                note="lifted conversions 18%",
            )
        ],
        composts=[
            Compost(
                failure="autoplay hero video", lesson="killed mobile load; never again"
            )
        ],
        absorb_return=AbsorbReturn(
            absorbed_from="top competitor booking flow",
            reversed_into="inverted steps: choose time before service",
            improvement="one-tap rebook for returning clients",
            returned_form="a booking rail that reads like a concierge, not a form",
            unreplicable_note="cadence and copy are ours alone",
        ),
        showcase_summary="Springfield's sharpest booking experience.",
    )
    assert [r.round_id for r in report.rounds] == [
        "round-1",
        "round-2",
        "sig-a",
        "sig-b",
        "round-3",
    ]
    # foundation + feature fully pass on the rich fixture
    r1 = report.rounds[0]
    assert all(c.passed for c in r1.checks), [
        c.check_id for c in r1.checks if not c.passed
    ]
    # goal tally covers all five goals
    assert all(g in report.goal_tally and report.goal_tally[g] > 0 for g in GOALS)


def test_thin_site_fails_foundations(tmp_path):
    site = _site(tmp_path, [THIN_PAGE])
    report = run_lift_program(site)
    r1 = report.rounds[0]
    failed = [c.check_id for c in r1.checks if not c.passed]
    assert "f-title" in failed and "f-contact" in failed
    # unattested signatures fail honestly
    sig_b = report.rounds[3]
    assert not any(c.passed for c in sig_b.checks)
    crown = report.rounds[4]
    showcase = [c for c in crown.checks if c.check_id == "c-showcase"][0]
    assert not showcase.passed


def test_empty_attestations_flagged(tmp_path):
    site = _site(tmp_path, [FULL_PAGE])
    report = run_lift_program(site)
    sig_a = report.rounds[2]
    assert not any(c.passed for c in sig_a.checks)


def test_report_roundtrip(tmp_path):
    site = _site(tmp_path, [FULL_PAGE])
    report = run_lift_program(site, showcase_summary="ready")
    p = save_report(report, home=tmp_path)
    assert p.exists()
    back = load_report(report.report_id, home=tmp_path)
    assert back is not None
    assert back.report_id == report.report_id
    assert len(back.rounds) == 5
    assert back.goal_tally == report.goal_tally
    assert load_report("nope", home=tmp_path) is None


def test_describe_program():
    prog = describe_program()
    assert [p["id"] for p in prog] == [
        "round-1",
        "round-2",
        "sig-a",
        "sig-b",
        "round-3",
    ]


def test_empty_provider_rejected(tmp_path):
    site = _site(tmp_path, [FULL_PAGE])
    with pytest.raises(LiftError):
        run_lift_program(site, provider="  ")


# ---------------------------------------------------------------------------
# Crown reachability, href/src scanning, tailored team recommendation.
# ---------------------------------------------------------------------------

#: Instagram appears ONLY in the href — the link text says nothing.
HREF_INSTAGRAM_PAGE = """<html><head><title>Shop</title></head><body>
<a href="https://instagram.com/easytouch">Follow us</a>
</body></html>"""

#: gtag appears ONLY in the script src — no analytics word anywhere in text.
GTM_SRC_PAGE = """<html><head><title>Shop</title></head><body>
<script src="https://www.googletagmanager.com/gtag/js"></script>
<p>hello</p>
</body></html>"""


def _full_program(tmp_path, pages, **kw):
    site = _site(tmp_path, pages)
    grafts = [Graft(pattern="sticky booking bar", source="portfolio #12")]
    composts = [Compost(failure="autoplay hero", lesson="killed mobile load")]
    absorb = AbsorbReturn(
        absorbed_from="competitor booking flow",
        reversed_into="time before service",
        improvement="one-tap rebook",
        returned_form="a booking rail that reads like a concierge",
    )
    return run_lift_program(
        site,
        provider="levi",
        grafts=grafts,
        composts=composts,
        absorb_return=absorb,
        showcase_summary=kw.pop("showcase_summary", "ready"),
        **kw,
    )


def test_thin_site_crown_fails_honestly(tmp_path):
    site = _site(tmp_path, [THIN_PAGE])
    report = run_lift_program(site)
    crown = report.rounds[4]
    goal_checks = [c for c in crown.checks if c.check_id.startswith("c-goal-")]
    assert len(goal_checks) == len(GOALS)
    # every goal fails on the thin fixture — and the evidence says which
    # measured checks failed, not just a count
    assert not any(c.passed for c in goal_checks)
    by_goal = {c.check_id: c for c in goal_checks}
    assert "failing:" in by_goal["c-goal-bring"].evidence
    assert "f-title" in by_goal["c-goal-bring"].evidence
    # intrigue has a single measured check: the evidence names it
    assert "t-gallery" in by_goal["c-goal-intrigue"].evidence
    assert "f-pages" in by_goal["c-goal-feature"].evidence


def test_rich_site_passes_crown_fully(tmp_path):
    report = _full_program(tmp_path, [FULL_PAGE, FULL_PAGE, FULL_PAGE])
    crown = report.rounds[4]
    failures = [c.check_id for c in crown.checks if not c.passed]
    assert not failures, failures
    # single-measured-check goals pass with threshold 1
    by_goal = {c.check_id: c for c in crown.checks if c.check_id.startswith("c-goal-")}
    assert by_goal["c-goal-intrigue"].passed
    assert by_goal["c-goal-feature"].passed


def test_href_only_instagram_triggers_social(tmp_path):
    site = _site(tmp_path, [HREF_INSTAGRAM_PAGE])
    report = run_lift_program(site)
    r2 = report.rounds[1]
    social = [c for c in r2.checks if c.check_id == "t-social"][0]
    assert social.passed
    assert "link urls" in social.evidence


def test_script_src_only_gtm_triggers_analytics(tmp_path):
    site = _site(tmp_path, [GTM_SRC_PAGE])
    report = run_lift_program(site)
    r2 = report.rounds[1]
    analytics = [c for c in r2.checks if c.check_id == "t-analytics"][0]
    assert analytics.passed
    assert "script srcs" in analytics.evidence


def test_recommend_team_output_shape(tmp_path):
    site = _site(tmp_path, [THIN_PAGE])
    report = run_lift_program(site)
    rec = recommend_team(report)
    assert rec.report_id == report.report_id
    assert isinstance(rec.slots, list) and rec.slots
    assert isinstance(rec.packs, list)
    assert isinstance(rec.model_mix, dict)
    assert isinstance(rec.upgrade_advice, list)
    assert isinstance(rec.pitch, str) and rec.pitch


def test_failed_booking_maps_to_booker(tmp_path):
    site = _site(tmp_path, [THIN_PAGE])
    report = run_lift_program(site)
    rec = recommend_team(report)
    slot_ids = [s["slot_id"] for s in rec.slots]
    assert "face" in slot_ids  # always included
    assert "booker" in slot_ids  # t-booking failed
    # Genesis basic: every seat is rules, all real-or-authorized
    assert all(s["model_id"] == "rules" for s in rec.slots)
    assert all(s["model_status"] == "real" for s in rec.slots)
    assert rec.model_mix == {"rules": len(rec.slots)}
    assert "booking-pack" in [p["pack_id"] for p in rec.packs]


def test_recommend_team_unknown_check_ids_defensive(tmp_path):
    site = _site(tmp_path, [THIN_PAGE])
    report = run_lift_program(site)
    report.rounds[0].checks.append(
        CheckResult(
            check_id="zzz-mystery",
            label="mystery gap",
            goals=("bring",),
            kind="measured",
            passed=False,
            evidence="n/a",
        )
    )
    rec = recommend_team(report)  # must not crash
    assert "face" in [s["slot_id"] for s in rec.slots]


def test_recommend_team_crown_failure_adds_owner_review(tmp_path):
    site = _site(tmp_path, [THIN_PAGE])
    report = run_lift_program(site)
    rec = recommend_team(report)
    assert rec.owner_review is not None
    assert "Owner review" in rec.owner_review
    assert rec.owner_review in rec.pitch


def test_recommend_team_clean_site_face_only(tmp_path):
    report = _full_program(tmp_path, [FULL_PAGE, FULL_PAGE, FULL_PAGE])
    rec = recommend_team(report)
    assert [s["slot_id"] for s in rec.slots] == ["face"]
    assert rec.packs == []
    assert rec.owner_review is None
    assert "no measured gaps" in rec.pitch


# ---------------------------------------------------------------------------
# Hardening: snapshot edge cases + the CLI end-to-end.
# ---------------------------------------------------------------------------


def test_snapshot_ignores_non_html_and_html_named_dirs(tmp_path):
    d = tmp_path / "site"
    d.mkdir()
    (d / "index.html").write_text(FULL_PAGE)
    (d / "notes.txt").write_text(FULL_PAGE)  # full page, wrong suffix
    (d / "page.htmlx").write_text(FULL_PAGE)  # not a real html suffix
    (d / "trap.html").mkdir()  # a directory, not a page
    snap = snapshot_site(d)
    assert snap.pages == 1
    assert snap.titles  # the real page was parsed


def test_snapshot_malformed_html_survives(tmp_path):
    d = tmp_path / "site"
    d.mkdir()
    (d / "broken.html").write_bytes(
        b"\xff\xfe<html><head><title>X</title><body><a href=/oops><img><form>"
    )
    snap = snapshot_site(d)
    assert snap.pages == 1  # parsed with replacement chars, no crash


def test_snapshot_rejects_file_path(tmp_path):
    f = tmp_path / "single.html"
    f.write_text(FULL_PAGE)
    with pytest.raises(LiftError):
        snapshot_site(f)


def _lift_args(site_dir, **over):
    kw = dict(
        service_cmd="lift",
        site_dir=str(site_dir),
        provider="levi",
        graft=[],
        gsource=[],
        gnote=[],
        compost=[],
        clesson=[],
        absorbed="",
        reversed="",
        improved="",
        returned="",
        unreplicable="",
        showcase="",
        with_team=False,
        pack=None,
        no_quote=False,
        giant_price=None,
        strategy="volume",
    )
    kw.update(over)
    return SimpleNamespace(**kw)


def test_cli_lift_end_to_end(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    site = _site(tmp_path, [FULL_PAGE, FULL_PAGE, FULL_PAGE])
    cmd_service(_lift_args(site))
    out = capsys.readouterr().out
    assert "[round-1] Round 1 — foundation lift: 8/8" in out
    assert "goal tally:" in out
    assert "report: lift_" in out
    # the report landed on disk under the redirected home
    lifts = list((tmp_path / "home" / "services" / "lifts").glob("*.json"))
    assert len(lifts) == 1
    report_id = lifts[0].stem
    # and the teams command can match it back
    args = SimpleNamespace(
        service_cmd="teams",
        report_id=report_id,
        pack=None,
        no_quote=True,
        giant_price=None,
        strategy="volume",
    )
    cmd_service(args)
    out = capsys.readouterr().out
    assert "team pack:" in out
    assert "offer: team_" in out


def test_cli_lift_bad_dir_refuses(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    cmd_service(_lift_args(tmp_path / "nope"))
    out = capsys.readouterr().out
    assert "Lift refused" in out


def test_report_id_traversal_rejected(tmp_path):
    site = _site(tmp_path, [FULL_PAGE])
    report = run_lift_program(site, report_id="../../evil")
    with pytest.raises(LiftError):
        save_report(report, home=tmp_path)
    with pytest.raises(LiftError):
        load_report("../../evil", home=tmp_path)
    # a dotted but safe id still works
    report2 = run_lift_program(site, report_id="lift_ok-1.2")
    p = save_report(report2, home=tmp_path)
    assert p.name == "lift_ok-1.2.json"
    assert load_report("lift_ok-1.2", home=tmp_path).report_id == "lift_ok-1.2"


def test_cli_teams_bad_report_id_refuses(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    cmd_service(
        SimpleNamespace(
            service_cmd="teams",
            report_id="../../evil",
            pack=None,
            no_quote=True,
            giant_price=None,
            strategy="volume",
        )
    )
    out = capsys.readouterr().out
    assert "Unknown lift report" in out
