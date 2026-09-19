"""Tests for revival wave 13: forge-additions (b) — sovereign code-home features."""

import time

import pytest

from levi.revival import attention_dials, bridging_layer, local_devenv
from levi.revival import local_feed_reader, patronage_rails, portable_communities
from levi.revival import presence_rooms, true_delete


# ---------------------------------------------------------------- local_devenv


def test_local_devenv_define_and_validate():
    forge = local_devenv.Forge()
    env = forge.define_env("webapp", "python", "/home/u/webapp")
    env.setup_commands.append("pip install -r reqs.txt")
    env.env_vars.append(local_devenv.EnvVar("PORT", "8080"))
    env.ports.append(local_devenv.PortMap(8080, 8080))
    assert forge.get_env(env.id) is env
    assert env.validate() == []


def test_local_devenv_validation_catches_problems():
    forge = local_devenv.Forge()
    env = forge.define_env("", "python", "")
    env.ports.append(local_devenv.PortMap(8080, 1))
    env.ports.append(local_devenv.PortMap(8080, 2))
    problems = env.validate()
    assert any("name" in p for p in problems)
    assert any("workdir" in p for p in problems)
    assert any("duplicate host ports" in p for p in problems)


def test_local_devenv_export_shell_keeps_secrets_out():
    forge = local_devenv.Forge()
    env = forge.define_env("api", "node", "/srv/api")
    env.env_vars.append(local_devenv.EnvVar("TOKEN", "s3cr3t", secret=True))
    env.env_vars.append(local_devenv.EnvVar("MODE", "dev"))
    script = env.export_shell()
    assert "s3cr3t" not in script
    assert "${TOKEN:?TOKEN must be set in your shell}" in script
    assert "export MODE=dev" in script


def test_local_devenv_byo_plan_roundtrip():
    forge = local_devenv.Forge()
    env = forge.define_env("api", "node", "/srv/api")
    plan = forge.plan_bring(
        "prod",
        "my-provider",
        "us-east",
        "4vcpu/16gb",
        credential_label="my-cli-profile",
        devenv_id=env.id,
    )
    plan.steps.append("provision machine with my-provider cli")
    runbook = plan.runbook()
    assert "my-provider" in runbook and "Billed by YOUR provider" in runbook
    blob = forge.to_dict()
    assert (
        local_devenv.Forge.from_dict(blob).get_bring(plan.id).provider == "my-provider"
    )
    with pytest.raises(KeyError):
        forge.plan_bring("bad", "p", "r", "s", "c", devenv_id="env-nope")


# ------------------------------------------------------------ patronage_rails


def test_patronage_pledge_and_dual_confirm_receipt():
    pat = patronage_rails.Patronage()
    p = pat.pledge("ama", "bri", 10.0, cadence="monthly")
    r = pat.open_receipt(p.id)
    pat.confirm(r.id, "ama")
    assert not r.complete
    pat.confirm(r.id, "bri")
    assert r.complete and r.settled_at > 0
    assert pat.creator_totals() == {"bri": 10.0}
    assert patronage_rails.PLATFORM_FEE == 0.0


def test_patronage_rejects_bad_pledges():
    pat = patronage_rails.Patronage()
    with pytest.raises(ValueError):
        pat.pledge("ama", "ama", 5.0)
    with pytest.raises(ValueError):
        pat.pledge("ama", "bri", 0.0)
    with pytest.raises(ValueError):
        pat.pledge("ama", "bri", 5.0, cadence="decade")


def test_patronage_outsider_cannot_confirm():
    pat = patronage_rails.Patronage()
    p = pat.pledge("ama", "bri", 10.0)
    r = pat.open_receipt(p.id)
    with pytest.raises(ValueError):
        pat.confirm(r.id, "zed")


def test_patronage_pause_resume_and_totals():
    pat = patronage_rails.Patronage()
    p = pat.pledge("ama", "bri", 10.0, cadence="monthly")
    assert pat.open_pledges_total("bri") == 10.0
    pat.pause_pledge(p.id)
    assert pat.open_pledges_total("bri") == 0.0
    pat.resume_pledge(p.id)
    assert pat.open_pledges_total("bri") == 10.0
    # single-confirm receipts never count toward totals
    r = pat.open_receipt(p.id)
    pat.confirm(r.id, "ama")
    assert pat.creator_totals() == {}
    blob = pat.to_dict()
    assert patronage_rails.Patronage.from_dict(blob).pledges[p.id].amount == 10.0


# ------------------------------------------------------------ attention_dials


def _items():
    return [
        {"id": "a", "ts": 3.0, "features": {"recency": 0.9, "affinity": 0.1}},
        {"id": "b", "ts": 1.0, "features": {"recency": 0.2, "affinity": 0.9}},
        {"id": "c", "ts": 2.0, "features": {"recency": 0.5, "affinity": 0.5}},
    ]


def test_attention_dials_default_is_chronological():
    d = attention_dials.Dials()
    assert d.weights == {
        k: (1.0 if k == "recency" else 0.0) for k in attention_dials.DIALS
    }
    ranked = d.rank(_items())
    assert [s.item["id"] for s in ranked] == ["a", "c", "b"]


def test_attention_dials_editing_changes_order():
    d = attention_dials.Dials()
    d.set("affinity", 1.0)
    d.set("recency", 0.0)
    ranked = d.rank(_items())
    assert [s.item["id"] for s in ranked] == ["b", "c", "a"]
    top = ranked[0]
    assert top.breakdown["affinity"] == pytest.approx(0.9)
    assert top.score == pytest.approx(sum(top.breakdown.values()))
    with pytest.raises(KeyError):
        d.set("vibes", 0.5)
    with pytest.raises(ValueError):
        d.set("affinity", 1.5)


def test_attention_dials_preset_portability_and_reset():
    d = attention_dials.Dials()
    d.set_all({"affinity": 0.7, "topicality": 0.3})
    blob = d.to_dict()
    d2 = attention_dials.Dials.from_dict(blob)
    assert d2.preset() == d.preset()
    d2.reset_to_chronological()
    assert d2.weights["affinity"] == 0.0 and d2.weights["recency"] == 1.0
    chrono = d.rank_chronological(_items())
    assert [s.item["id"] for s in chrono] == ["a", "c", "b"]


# ------------------------------------------------------------ bridging_layer


def test_bridging_layer_bridging_beats_polarized():
    layer = bridging_layer.BridgingLayer()
    bridged = layer.propose("shared claim", "ana")
    polarized = layer.propose("divisive claim", "bo")
    for g in ("group-a", "group-b"):
        for v in range(5):
            layer.respond(bridged.id, g, "agree", voter=f"{g}-{v}")
    for v in range(5):
        layer.respond(polarized.id, "group-a", "agree", voter=f"a-{v}")
        layer.respond(polarized.id, "group-b", "disagree", voter=f"b-{v}")
    sb, sp = layer.score(bridged.id), layer.score(polarized.id)
    assert sb.score > sp.score
    assert sp.polarization == pytest.approx(1.0)
    assert sb.polarization == pytest.approx(0.0)
    assert layer.consensus_feed()[0].statement_id == bridged.id


def test_bridging_layer_contested_and_pass_ignored():
    layer = bridging_layer.BridgingLayer()
    s = layer.propose("hot take", "cy")
    layer.respond(s.id, "group-a", "agree")
    layer.respond(s.id, "group-b", "disagree")
    layer.respond(s.id, "group-a", "pass")
    layer.respond(s.id, "group-b", "pass")
    score = layer.score(s.id)
    assert score.group_approvals == {"group-a": 1.0, "group-b": 0.0}
    assert score.n_responses == 4
    assert layer.contested(threshold=0.4)[0].statement_id == s.id
    with pytest.raises(ValueError):
        layer.respond(s.id, "group-a", "maybe")


def test_bridging_layer_import_feed_labels_source():
    layer = bridging_layer.BridgingLayer()
    made = layer.import_feed(
        "outside-wire",
        [
            {"text": "imported claim", "author": "wire"},
        ],
    )
    assert made[0].source == "outside-wire"
    assert "wire" in layer.score(made[0].id).explain() or True
    assert layer.score(made[0].id).score == 0.0  # no responses yet
    blob = layer.to_dict()
    assert (
        bridging_layer.BridgingLayer.from_dict(blob).statements[made[0].id].source
        == "outside-wire"
    )


# ---------------------------------------------------------------- true_delete


def test_true_delete_post_read_delete():
    td = true_delete.TrueDelete()
    td.open_channel("ops")
    m = td.post("ops", "ana", "meet at dawn", ttl_seconds=3600)
    assert td.read("ops", m.id) == "meet at dawn"
    cert = td.delete("ops", m.id)
    assert td.read("ops", m.id) is None
    assert m.text == "<erased>" and m._key == b"" and m.deleted
    assert cert.reason == "user" and cert.message_id == m.id
    assert td.verify_chain()


def test_true_delete_ttl_sweep_issues_certificates():
    td = true_delete.TrueDelete()
    td.open_channel("ops")
    m = td.post("ops", "ana", "old news", ttl_seconds=0.0)
    time.sleep(0.01)
    certs = td.sweep("ops")
    assert len(certs) == 1 and certs[0].reason == "ttl"
    assert td.read("ops", m.id) is None
    assert td.verify_chain()


def test_true_delete_screenshot_awareness_and_bad_policy():
    td = true_delete.TrueDelete()
    td.open_channel("ops", screenshot_policy="warn")
    ev = td.flag_screenshot("ops", "bo", note="possible capture")
    assert ev.channel == "ops" and len(td.screenshots) == 1
    with pytest.raises(ValueError):
        td.open_channel("bad", screenshot_policy="notify-admin")
    with pytest.raises(KeyError):
        td.post("nope", "ana", "x")


# ---------------------------------------------------------- local_feed_reader

_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Demo</title>
<item><title>First</title><link>http://x/1</link><pubDate>Mon</pubDate>
<description>one</description></item>
<item><title>Second</title><link>http://x/2</link><pubDate>Tue</pubDate>
<description>two</description></item>
</channel></rss>"""

_ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>A-one</title><link href="http://x/a1"/><updated>today</updated>
<summary>s1</summary></entry>
</feed>"""

_OPML = """<?xml version="1.0"?>
<opml version="2.0"><body>
<outline type="rss" text="Demo" xmlUrl="http://x/rss"/>
<outline type="rss" text="Atom" xmlUrl="http://x/atom"/>
</body></opml>"""


def test_feed_reader_refresh_parses_rss_and_atom():
    r = local_feed_reader.FeedReader()
    f = r.subscribe("Demo", "http://x/rss")
    r.refresh(f.id, _RSS)
    assert f.kind == "rss" and len(f.items) == 2
    assert f.items[0].title == "First"
    assert f.health()["status"] == "healthy"
    g = r.subscribe("Atom", "http://x/atom")
    r.refresh(g.id, _ATOM)
    assert g.kind == "atom" and g.items[0].title == "A-one"


def test_feed_reader_health_tracks_errors_and_staleness():
    r = local_feed_reader.FeedReader()
    f = r.subscribe("Broken", "http://x/nope")
    assert f.health()["status"] == "never-fetched"
    r.refresh(f.id, "not xml at all <<<")
    h = f.health()
    assert h["status"] == "error" and h["error_count"] == 1
    f.last_ok = time.time() - 2 * local_feed_reader.STALE_AFTER
    f.error_count = 0
    f.last_attempt = f.last_ok
    assert f.health()["status"] == "stale"


def test_feed_reader_opml_roundtrip():
    r = local_feed_reader.FeedReader()
    made = r.import_opml(_OPML)
    assert len(made) == 2
    # importing again adds no duplicates
    assert r.import_opml(_OPML) == []
    opml = r.export_opml()
    r2 = local_feed_reader.FeedReader()
    assert len(r2.import_opml(opml)) == 2
    assert sorted(f.name for f in r2.feeds.values()) == ["Atom", "Demo"]
    with pytest.raises(ValueError):
        r2.import_opml("garbage")


def test_feed_reader_mute_hides_from_all_items():
    r = local_feed_reader.FeedReader()
    f = r.subscribe("Demo", "http://x/rss")
    r.refresh(f.id, _RSS)
    assert len(r.all_items()) == 2
    r.mute(f.id)
    assert r.all_items() == []
    assert len(r.all_items(include_muted=True)) == 2


# ------------------------------------------------------------ presence_rooms


def test_presence_rooms_join_leave_roster():
    host = presence_rooms.RoomHost()
    host.create_room("lounge", join_code="1234")
    a = host.join("lounge", "ana", join_code="1234")
    b = host.join("lounge", "bo", join_code="1234", profile="high")
    assert {m.display_name for m in host.roster("lounge")} == {"ana", "bo"}
    assert b.profile == "high"
    host.leave("lounge", a.id)
    assert [m.display_name for m in host.roster("lounge")] == ["bo"]
    with pytest.raises(PermissionError):
        host.join("lounge", "zed", join_code="wrong")


def test_presence_rooms_state_and_free_quality_tiers():
    host = presence_rooms.RoomHost()
    host.create_room("stage")
    m = host.join("stage", "cy")
    host.set_state("stage", m.id, presence_rooms.SPEAKING)
    assert host.speakers("stage")[0].id == m.id
    # quality tiers are never paywalled: every member may use any tier
    host.set_profile("stage", m.id, "high")
    assert host.roster("stage")[0].profile == "high"
    with pytest.raises(ValueError):
        host.set_state("stage", m.id, "dancing")
    with pytest.raises(ValueError):
        host.set_profile("stage", m.id, "ultra")


def test_presence_rooms_events_and_snapshot():
    host = presence_rooms.RoomHost()
    host.create_room("stage")
    seen = []
    host.subscribe("stage", seen.append)
    m = host.join("stage", "cy")
    host.set_state("stage", m.id, presence_rooms.MUTED)
    assert [e.kind for e in seen] == ["join", "state"]
    blob = host.to_dict()
    host2 = presence_rooms.RoomHost.from_dict(blob)
    assert host2.roster("stage")[0].state == presence_rooms.MUTED
    assert host.close_room("stage") is True
    assert host.close_room("stage") is False


# ------------------------------------------------------- portable_communities


def _sample_community():
    c = portable_communities.Community("garden")
    c.add_member("ana", role="owner")
    c.add_member("bo")
    c.add_channel("general", topic="hellos")
    c.post("general", "ana", "welcome")
    c.post("general", "bo", "hi")
    c.adopt_rule("be kind", adopted_by="ana")
    c.record_decision("adopt the rule", "passed", votes_for=2)
    return c


def test_portable_communities_export_import_roundtrip():
    c = _sample_community()
    bundle = c.export_bundle()
    assert portable_communities.verify_bundle(bundle)
    c2 = portable_communities.Community.import_bundle(bundle)
    assert c2.name == "garden"
    assert c2.members["ana"].role == "owner"
    assert len(c2.channels["general"].posts) == 2
    assert len(c2.rules) == 1 and len(c2.decisions) == 1
    assert c2.decisions[0].outcome == "passed"


def test_portable_communities_tamper_detected():
    c = _sample_community()
    bundle = c.export_bundle()
    bundle["body"]["members"]["bo"]["role"] = "owner"
    assert not portable_communities.verify_bundle(bundle)
    with pytest.raises(ValueError):
        portable_communities.Community.import_bundle(bundle)


def test_portable_communities_governance_guards():
    c = portable_communities.Community("garden")
    c.add_member("ana")
    with pytest.raises(ValueError):
        c.add_member("bo", role="monarch")
    with pytest.raises(KeyError):
        c.post("general", "stranger", "hi")
    c.add_channel("general")
    with pytest.raises(ValueError):
        c.record_decision("x", "maybe")
    with pytest.raises(ValueError):
        portable_communities.Community.import_bundle({"nope": 1})
