"""Consent boundary: no walk-in without invitation.

Hermetic: tmp rescue home, fake browser surface, no network.
"""

import pytest

from levi.rescue import intake, seams
from levi.rescue.intake import ConsentRefusedError


SITE = "https://tacos.example"


def _invited(home, **over):
    kw = dict(
        owner="M. Torres", business="Torres Tacos", site_url=SITE, note="fix my site"
    )
    kw.update(over)
    return intake.issue_invitation(home, **kw)


class _FakePage:
    def __init__(self, url, links=()):
        self.url = url
        self.status = 200
        self.title = "T"
        self.text = "# T\nCall 217-555-0100."
        self.links = [{"href": href} for href in links]
        self.forms = []


class _FakeBrowser:
    def __init__(self, pages):
        self.pages = pages

    def open(self, url):
        try:
            return self.pages[url]
        except KeyError:
            raise IOError("404: %s" % url) from None


def test_unknown_invitation_refused(tmp_path):
    with pytest.raises(ConsentRefusedError):
        intake.require_consent(tmp_path, "inv-9999")


def test_invited_but_not_accepted_refused(tmp_path):
    inv = _invited(tmp_path)
    with pytest.raises(ConsentRefusedError):
        intake.require_consent(tmp_path, inv.id)


def test_accepted_invitation_walks(tmp_path):
    inv = _invited(tmp_path)
    intake.accept_invitation(tmp_path, inv.id, owner_note="walk it")
    got = intake.require_consent(tmp_path, inv.id)
    assert got.accepted and got.id == inv.id


def test_scope_bounds_enforced(tmp_path):
    inv = _invited(tmp_path)
    assert inv.allows("https://tacos.example/menu")
    assert not inv.allows("https://other.example/")


def test_walk_refuses_out_of_scope_urls(tmp_path):
    inv = _invited(tmp_path)
    intake.accept_invitation(tmp_path, inv.id)
    browser = _FakeBrowser(
        {
            SITE: _FakePage(
                SITE,
                links=["https://tacos.example/menu", "https://other.example/steal"],
            ),
            "https://tacos.example/menu": _FakePage("https://tacos.example/menu"),
        }
    )
    out = seams.walk_invitation(tmp_path, inv.id, browser=browser)
    assert SITE in out["walk"]
    assert "https://tacos.example/menu" in out["walk"]
    assert "https://other.example/steal" not in out["walk"]
    refused = out["receipts"][-1]["refused"]
    assert any(
        r["url"] == "https://other.example/steal" and "scope" in r["reason"]
        for r in refused
    )


def test_walk_requires_consent_first(tmp_path):
    inv = _invited(tmp_path)  # never accepted
    with pytest.raises(ConsentRefusedError):
        seams.walk_invitation(tmp_path, inv.id, browser=_FakeBrowser({}))


def test_invitation_rejects_non_http(tmp_path):
    with pytest.raises(ValueError):
        _invited(tmp_path, site_url="ftp://tacos.example")
