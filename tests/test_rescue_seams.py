"""Adapter seams: forge surfaces compose (not rewritten); neighbor gig draft.

Hermetic: tmp rescue home, hand-built walks, no network.
"""

import pytest

from levi.rescue import audit, intake, plan, seams


SITE = "https://tacos.example"


def _approved_plan(tmp_path):
    inv = intake.issue_invitation(
        tmp_path, owner="M. Torres", business="Torres Tacos", site_url=SITE
    )
    intake.accept_invitation(tmp_path, inv.id)
    walk = {
        SITE: {
            "url": SITE,
            "status": 200,
            "title": "",
            "text": "Welcome.",
            "links": [],
            "forms": [],
        }
    }
    report = audit.run_audit(tmp_path, inv.id, audit.DEFAULT_CHECKS, walk)
    p = plan.build_plan(tmp_path, report)
    return plan.approve_plan(tmp_path, p.id, owner="M. Torres")


def test_neighbor_gig_draft_from_approved_plan(tmp_path):
    p = _approved_plan(tmp_path)
    gig = seams.neighbor_gig_draft(tmp_path, p)
    assert gig["category"] == "site-rescue"
    assert "Torres Tacos" in gig["title"]
    assert gig["rescue_plan_id"] == p.id
    assert gig["estimate"] > 0
    # The real NeighborOS pipeline accepted the draft (worker 7's module).
    assert gig["dispatched"] is True
    assert gig["neighbor_draft"]["status"] == "draft"
    assert "publish" in gig["dispatch_note"]  # publish still needs the owner


def test_forge_surfaces_open(tmp_path):
    # Composed, not rewritten: the adapters open the siblings' surfaces.
    browser = seams.forge_browser(tmp_path)
    assert hasattr(browser, "open")
    machine = seams.forge_computer(tmp_path)
    assert machine is not None


def test_version_episode_is_honest(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "before.json").write_text("{}")
    out = seams.version_episode(ep, "test commit")
    assert "versioned" in out
    if out["versioned"]:
        assert out["commit"]
    else:
        assert out["reason"]  # honest about why not


def test_missing_surface_raises_loudly(tmp_path, monkeypatch):
    import sys

    # None in sys.modules makes the import halt with ImportError.
    monkeypatch.setitem(sys.modules, "levi.forge.browser", None)
    with pytest.raises(seams.SurfaceUnavailableError):
        seams.forge_browser(tmp_path)
