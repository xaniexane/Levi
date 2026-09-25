"""Hermetic tests for the LEVI universal job organ (core/levi/jobs/).

No HOME writes (tmp_path only), no network, no randomness — every
assertion is deterministic. All example data is synthetic. Chauncey's
real data never appears here; profiles in tests are fictional.
"""

import pytest

from levi.automation.hitl import GateDenied, auto_approve, auto_deny
from levi.jobs import apply as apply_engine
from levi.jobs import chains as chains_engine
from levi.jobs import gig as gig_engine
from levi.jobs import intel as intel_engine
from levi.jobs import prep as prep_engine
from levi.jobs import sourcing as sourcing_engine
from levi.jobs import triage as triage_engine
from levi.jobs.modes import Mode, capabilities, parse_mode, require
from levi.jobs.profiles import PROFILE_FIELDS, ProfileStore
from levi.jobs.store import Warehouse, import_workbook


def _jobs_dir(tmp_path):
    return tmp_path / "jobs"


def _profile(tmp_path, name="fictional"):
    ps = ProfileStore(_jobs_dir(tmp_path))
    ps.scaffold(name)
    ps.set_field(name, "job_types_target", "chat support, customer service")
    ps.set_field(name, "job_types_avoid", "management")
    ps.set_field(name, "target_pay_min", 15)
    ps.set_field(name, "target_pay_max", 25)
    ps.set_field(name, "remote_preference", "remote")
    ps.set_field(name, "top_skills", "chat, typing")
    ps.set_field(name, "felony_on_record", "N")
    return ps.get(name)


def _warehouse(tmp_path):
    return Warehouse(_jobs_dir(tmp_path))


# -- profiles ---------------------------------------------------------------


def test_profile_scaffold_has_all_blank_fields(tmp_path):
    ps = ProfileStore(_jobs_dir(tmp_path))
    prof = ps.scaffold("fictional")
    assert set(prof.fields) == set(PROFILE_FIELDS)
    assert prof.fields["full_name"] == ""
    assert prof.fields["top_skills"] == []


def test_profile_set_rejects_unknown_field(tmp_path):
    ps = ProfileStore(_jobs_dir(tmp_path))
    ps.create("fictional")
    with pytest.raises(ValueError, match="unknown profile field"):
        ps.set_field("fictional", "social_security_number", "000-00-0000")


def test_profile_missing_raises_keyerror(tmp_path):
    ps = ProfileStore(_jobs_dir(tmp_path))
    with pytest.raises(KeyError):
        ps.get("nobody")


def test_profile_files_are_owner_only(tmp_path):
    import os
    import stat

    ps = ProfileStore(_jobs_dir(tmp_path))
    ps.create("fictional")
    path = ps._path("fictional")
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


# -- warehouse ------------------------------------------------------------------


def test_warehouse_add_get_update_remove(tmp_path):
    wh = _warehouse(tmp_path)
    row = wh.add_row("review_buffer", {"job_title": "Role", "company": "Co"})
    assert row["id"] == 1
    assert wh.get_row("review_buffer", 1)["job_title"] == "Role"
    wh.update_row("review_buffer", 1, {"priority": "high"})
    assert wh.get_row("review_buffer", 1)["priority"] == "high"
    wh.remove_row("review_buffer", 1)
    assert wh.list_rows("review_buffer") == []
    with pytest.raises(KeyError):
        wh.get_row("review_buffer", 1)


def test_warehouse_unknown_table_raises(tmp_path):
    wh = _warehouse(tmp_path)
    with pytest.raises(ValueError, match="unknown warehouse table"):
        wh.add_row("nope", {})


def test_warehouse_find_and_log(tmp_path):
    wh = _warehouse(tmp_path)
    wh.add_row("blacklist", {"entry_type": "company", "name": "BadCo", "active": "Y"})
    found = wh.find("blacklist", name="BadCo")
    assert len(found) == 1
    log = wh.log_automation("test-action", "Success", notes="x")
    assert log["log_no"] == 1
    assert log["action_type"] == "test-action"


def test_import_workbook_reads_sheets(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    xlsx = tmp_path / "v2.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Review Buffer"
    ws.append(["REVIEW BUFFER"])
    ws.append(["Date Added", "Job Title", "Company", "Pay Range"])
    ws.append(["2026-01-01", "Chat Agent", "GoodCo", "$18/hr"])
    ws.append([])  # empty row skipped
    ws2 = wb.create_sheet("Blacklist")
    ws2.append(["BLACKLIST"])
    ws2.append(["Entry Type (Company/Role/Board)", "Name", "Reason", "Active (Y/N)"])
    ws2.append(["Company", "BadCo", "test", "Y"])
    wb.save(xlsx)

    wh = _warehouse(tmp_path)
    counts = import_workbook(xlsx, wh)
    assert counts["review_buffer"] == 1
    assert counts["blacklist"] == 1
    row = wh.list_rows("review_buffer")[0]
    assert row["job_title"] == "Chat Agent"
    assert row["source"] == "workbook"


# -- sourcing --------------------------------------------------------------------


def test_sourcing_stages_and_dedupes(tmp_path):
    wh = _warehouse(tmp_path)
    listing = {
        "job_title": "Chat Agent",
        "company": "GoodCo",
        "url": "https://example.test/j/1",
    }
    r1 = sourcing_engine.ingest_listings(wh, [listing], dry_run=False)
    assert r1["staged"] == 1
    r2 = sourcing_engine.ingest_listings(wh, [listing], dry_run=False)
    assert r2["refreshed"] == 1 and r2["staged"] == 0
    assert len(wh.list_rows("review_buffer")) == 1


def test_sourcing_dry_run_writes_nothing(tmp_path):
    wh = _warehouse(tmp_path)
    rep = sourcing_engine.ingest_listings(
        wh, [{"job_title": "Chat Agent", "company": "GoodCo"}], dry_run=True
    )
    assert rep["staged"] == 1
    assert wh.list_rows("review_buffer") == []


def test_sourcing_rejects_blacklist_and_hard_restriction(tmp_path):
    wh = _warehouse(tmp_path)
    intel_engine.add_blacklist(wh, "company", "BadCo", "test", "hard")
    intel_engine.add_restriction(wh, "Equipment", "Requires Windows PC", "hard", "x")
    rep = sourcing_engine.ingest_listings(
        wh,
        [
            {"job_title": "Driver", "company": "BadCo"},
            {
                "job_title": "Clerk",
                "company": "OkCo",
                "notes": "requires windows pc on site",
            },
        ],
        dry_run=False,
    )
    assert rep["rejected_blacklist"] == 1
    assert rep["rejected_restriction"] == 1
    assert wh.list_rows("review_buffer") == []


# -- triage -----------------------------------------------------------------------


def test_score_rubric_exact_and_deterministic(tmp_path):
    prof = _profile(tmp_path)
    listing = {
        "job_title": "Chat Support Agent",
        "company": "GoodCo",
        "pay_range": "$18-$22/hr",
        "location_remote": "Remote",
        "equipment_provided": "Y",
        "notes": "chat typing support",
    }
    s1 = triage_engine.score_listing(listing, prof)
    s2 = triage_engine.score_listing(listing, prof)
    assert s1["score"] == 10  # 1+3+2+2+2+1 = 11 -> capped at 10
    assert s1 == s2
    assert set(s1["breakdown"]) >= {
        "role_fit",
        "pay_fit",
        "remote_fit",
        "skills_overlap",
        "equipment",
    }


def test_score_avoid_type_caps_at_two(tmp_path):
    prof = _profile(tmp_path)
    listing = {
        "job_title": "Shift Management Lead",
        "company": "GoodCo",
        "pay_range": "$18-$22/hr",
        "location_remote": "Remote",
        "equipment_provided": "Y",
        "notes": "chat typing",
    }
    s = triage_engine.score_listing(listing, prof)
    assert s["score"] <= 2
    assert s["capped"]


def test_score_felony_screen_caps(tmp_path):
    ps = ProfileStore(_jobs_dir(tmp_path))
    ps.scaffold("rec")
    ps.set_field("rec", "felony_on_record", "Y")
    prof = ps.get("rec")
    listing = {
        "job_title": "Chat Support Agent",
        "company": "GoodCo",
        "pay_range": "$18-$22/hr",
        "location_remote": "Remote",
        "felony_friendly": "N",
    }
    s = triage_engine.score_listing(listing, prof)
    assert s["score"] <= 2
    assert any("felony" in f for f in s["flags"])


def test_triage_promotes_at_threshold(tmp_path):
    wh = _warehouse(tmp_path)
    prof = _profile(tmp_path)
    sourcing_engine.ingest_listings(
        wh,
        [
            {
                "job_title": "Chat Support Agent",
                "company": "GoodCo",
                "pay_range": "$18-$22/hr",
                "location_remote": "Remote",
                "equipment_provided": "Y",
                "notes": "chat typing support",
            },
            {
                "job_title": "Janitor",
                "company": "CleanCo",
                "pay_range": "$9/hr",
                "location_remote": "On-site",
            },
        ],
        dry_run=False,
    )
    rep = triage_engine.triage_buffer(wh, prof, threshold=7, dry_run=False)
    assert rep["promoted"] == 1 and rep["parked"] == 1
    queue = wh.list_rows("apply_queue")
    assert len(queue) == 1 and queue[0]["priority_rank"] == 1


def test_triage_dry_run_scores_without_writing(tmp_path):
    wh = _warehouse(tmp_path)
    prof = _profile(tmp_path)
    sourcing_engine.ingest_listings(
        wh,
        [
            {
                "job_title": "Chat Support Agent",
                "company": "GoodCo",
                "pay_range": "$18-$22/hr",
                "location_remote": "Remote",
                "equipment_provided": "Y",
                "notes": "chat typing support",
            },
        ],
        dry_run=False,
    )
    rep = triage_engine.triage_buffer(wh, prof, threshold=7, dry_run=True)
    assert rep["promoted"] == 1
    assert wh.list_rows("apply_queue") == []
    assert wh.list_rows("review_buffer")[0].get("match_score") in (None, "", 0)


# -- apply -------------------------------------------------------------------------


def test_apply_packet_dry_run_writes_nothing(tmp_path):
    wh = _warehouse(tmp_path)
    prof = _profile(tmp_path)
    q = wh.add_row("apply_queue", {"job_title": "Chat Agent", "company": "GoodCo"})
    packet = apply_engine.build_packet(wh, prof, q["id"], dry_run=True)
    assert packet["dry_run"] is True
    assert packet["prefill"]["phone"] == prof.get("phone")
    assert wh.get_row("apply_queue", q["id"]).get("status") != "packet-ready"


def test_apply_authorize_denied_raises(tmp_path):
    wh = _warehouse(tmp_path)
    q = wh.add_row("apply_queue", {"job_title": "Chat Agent", "company": "GoodCo"})
    with pytest.raises(GateDenied):
        apply_engine.authorize_submission(wh, q["id"], auto_deny, dry_run=False)
    assert wh.get_row("apply_queue", q["id"]).get("status") != "authorized"


def test_apply_log_never_writes_on_dry_run_or_denial(tmp_path):
    wh = _warehouse(tmp_path)
    q = wh.add_row("apply_queue", {"job_title": "Chat Agent", "company": "GoodCo"})
    out = apply_engine.log_submission(
        wh, q["id"], auto_approve, dry_run=True, confirmation=True
    )
    assert out["logged"] is False
    assert wh.list_rows("application_log") == []
    with pytest.raises(GateDenied):
        apply_engine.log_submission(wh, q["id"], auto_deny, dry_run=False)


def test_apply_log_writes_only_on_human_confirmation(tmp_path):
    wh = _warehouse(tmp_path)
    q = wh.add_row("apply_queue", {"job_title": "Chat Agent", "company": "GoodCo"})
    out = apply_engine.log_submission(
        wh, q["id"], auto_approve, dry_run=False, confirmation=True
    )
    assert out["logged"] is True
    assert len(wh.list_rows("application_log")) == 1
    assert wh.get_row("apply_queue", q["id"])["completed"] == "Y"


def test_apply_record_response_validates(tmp_path):
    wh = _warehouse(tmp_path)
    row = wh.add_row("application_log", {"job_title": "X", "company": "Y"})
    with pytest.raises(ValueError, match="unknown response_type"):
        apply_engine.record_response(wh, row["id"], "hired-tomorrow")
    updated = apply_engine.record_response(wh, row["id"], "interview")
    assert updated["response_received"] == "Y"


# -- prep ----------------------------------------------------------------------------


def test_cover_letter_marks_unknown_placeholders(tmp_path):
    ps = ProfileStore(_jobs_dir(tmp_path))
    ps.scaffold("sparse")
    prof = ps.get("sparse")
    wh = _warehouse(tmp_path)
    tpl = prep_engine.add_template(
        wh, "Generic", opening_hook="Hi {hiring_manager}, I'm {name}."
    )
    draft = prep_engine.compose_cover_letter(
        prof, {"job_title": "Clerk", "company": "Acme"}, tpl
    )
    assert draft["draft"] is True
    assert "[hiring_manager]" in draft["text"]  # unknown stays visible
    assert "[your name]" in draft["text"]  # unset profile field stays visible


def test_prep_packet_scaffold_and_fill(tmp_path):
    wh = _warehouse(tmp_path)
    pkt = prep_engine.build_prep_packet(wh, "Clerk", "Acme", dry_run=False)
    assert pkt["prep_status"] == "scaffolded"
    assert pkt["star_story_1"] == ""
    updated = prep_engine.update_prep(
        wh, pkt["id"], star_story_1="S...", prep_status="ready"
    )
    assert updated["prep_status"] == "ready"
    with pytest.raises(ValueError, match="unknown prep fields"):
        prep_engine.update_prep(wh, pkt["id"], salary="1M")


# -- gig -------------------------------------------------------------------------------


def test_gig_rules_evaluate_never_accept(tmp_path):
    wh = _warehouse(tmp_path)
    gig_engine.add_offer(wh, "DashX", "Dinner block", pay=48, distance_mi=3)
    gig_engine.add_offer(wh, "DashX", "Tiny block", pay=12, distance_mi=3)
    rep = gig_engine.evaluate_offers(
        wh, {"min_pay": 40, "max_distance_mi": 5}, dry_run=False
    )
    assert rep["would_accept"] == 1
    # evaluation alone never changes offer status
    assert all(r["status"] == "open" for r in wh.list_rows("gig_offers"))


def test_gig_accept_requires_human_approval(tmp_path):
    wh = _warehouse(tmp_path)
    offer = gig_engine.add_offer(wh, "DashX", "Dinner block", pay=48)
    with pytest.raises(GateDenied):
        gig_engine.accept_offer(wh, offer["id"], auto_deny, dry_run=False)
    out = gig_engine.accept_offer(wh, offer["id"], auto_approve, dry_run=True)
    assert out["approved"] is True
    assert (
        wh.get_row("gig_offers", offer["id"])["status"] == "open"
    )  # dry-run: untouched


def test_gig_income_summary_math(tmp_path):
    wh = _warehouse(tmp_path)
    gig_engine.log_income(wh, "DashX", "block a", 48, hours_worked=3)
    gig_engine.log_income(wh, "TaskY", "task b", 30, hours_worked=1)
    s = gig_engine.income_summary(wh)
    assert s["total"] == 78.0 and s["gigs"] == 2
    assert s["per_hour"] == 19.5
    with pytest.raises(ValueError, match="amount must be numeric"):
        gig_engine.log_income(wh, "DashX", "bad", "lots")


# -- modes --------------------------------------------------------------------------------


def test_modes_gate_capabilities():
    assert capabilities(Mode.LIGHT)["write"] is False
    assert capabilities(Mode.LIGHT)["read"] is True
    assert capabilities(Mode.OFFLINE)["enrich_external"] is False
    assert capabilities(Mode.FULL)["ingest"] is True
    with pytest.raises(PermissionError):
        require(Mode.LIGHT, "ingest")
    with pytest.raises(ValueError, match="unknown mode"):
        parse_mode("turbo")
    assert parse_mode(None) is Mode.FULL


# -- chains ----------------------------------------------------------------------------------


def test_chain_morning_sweep_dry_run(tmp_path):
    wh = _warehouse(tmp_path)
    prof = _profile(tmp_path)
    receipt = chains_engine.run_chain(
        wh,
        prof,
        "morning-sweep",
        {
            "mode": Mode.FULL,
            "listings": [
                {
                    "job_title": "Chat Support Agent",
                    "company": "GoodCo",
                    "pay_range": "$18-$22/hr",
                    "location_remote": "Remote",
                    "equipment_provided": "Y",
                    "notes": "chat typing",
                }
            ],
            "threshold": 7,
        },
        dry_run=True,
    )
    assert receipt["status"] == "ok"
    assert receipt["verification"]["passed"] is True
    assert wh.list_rows("review_buffer") == []  # dry-run wrote nothing


def test_chain_blocked_condition_stops_run(tmp_path):
    wh = _warehouse(tmp_path)
    prof = _profile(tmp_path)
    receipt = chains_engine.run_chain(
        wh, prof, "morning-sweep", {"mode": Mode.LIGHT}, dry_run=True
    )
    assert receipt["status"] == "blocked"
    assert receipt["actions"] == []


def test_chain_unknown_chain_raises(tmp_path):
    wh = _warehouse(tmp_path)
    prof = _profile(tmp_path)
    with pytest.raises(ValueError, match="unknown chain"):
        chains_engine.run_chain(wh, prof, "nope", dry_run=True)


def test_chain_gate_denied_recorded(tmp_path):
    wh = _warehouse(tmp_path)
    prof = _profile(tmp_path)
    receipt = chains_engine.run_chain(
        wh, prof, "gig-watch", {"mode": Mode.FULL}, responder=auto_deny, dry_run=True
    )
    assert receipt["status"] == "gate-denied"


def test_chain_to_flow_is_valid_flows_manifest(tmp_path):
    for chain in chains_engine.list_chains():
        manifest = chains_engine.to_flow(chain.id)
        assert manifest["id"] == f"jobs-chain-{chain.id}"
        mermaid = chains_engine.chain_mermaid(chain.id)
        assert mermaid.startswith("flowchart")
