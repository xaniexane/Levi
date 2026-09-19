"""Wave 34 — sovereign-mail: tests for the seven local mail mechanisms."""

import pytest

from levi.revival import builtin_mail, stationery, mbox_storage
from levi.revival import mail_filters, bayes_spamwatch, phish_flagging, mail_search


# ---------------------------------------------------------------------------
# builtin_mail
# ---------------------------------------------------------------------------


def test_builtin_mail_compose_queue_send_cycle():
    client = builtin_mail.BuiltinMail()
    client.add_account("personal", "chauncey@example.com")
    msg = client.compose("personal", ["friend@example.com"], "Hi", "hello there")
    assert client.list("personal", "drafts")[0].uid == msg.uid
    client.queue_send("personal", msg.uid)
    assert client.list("personal", "outbox")
    sent = client.send_queued("personal")
    assert len(sent) == 1
    assert "delivered-locally" in sent[0].flags
    assert client.list("personal", "outbox") == []
    assert client.list("personal", "sent")[0].uid == msg.uid


def test_builtin_mail_delete_and_expunge():
    client = builtin_mail.BuiltinMail()
    client.add_account("work", "c@example.com")
    msg = client.compose("work", ["x@example.com"], "S", "B")
    client.delete("work", msg.uid)
    assert client.list("work", "trash")
    assert client.expunge("work", "trash") == 1
    assert client.find("work", msg.uid) is None


def test_builtin_mail_duplicate_account_rejected():
    client = builtin_mail.BuiltinMail()
    client.add_account("a", "a@example.com")
    with pytest.raises(ValueError):
        client.add_account("a", "a2@example.com")


def test_builtin_mail_receive_and_folders():
    client = builtin_mail.BuiltinMail()
    client.add_account("a", "a@example.com")
    client.add_folder("a", "receipts")
    msg = builtin_mail.MailMessage(
        uid="u1",
        account="a",
        from_addr="shop@example.com",
        to_addrs=["a@example.com"],
        subject="Order",
        body="shipped",
        date=1,
    )
    client.receive("a", msg)
    assert client.list("a", "inbox")[0].uid == "u1"
    client.move("a", "u1", "receipts")
    assert client.list("a", "receipts")[0].uid == "u1"
    assert client.folders("a")[:5] == ["inbox", "drafts", "outbox", "sent", "trash"]


# ---------------------------------------------------------------------------
# stationery
# ---------------------------------------------------------------------------


def test_stationery_render_fills_placeholders():
    drawer = stationery.StationeryDrawer()
    drawer.add("thanks", "Thanks, {name}!", "Hi {name},\nGot it on {date}.")
    out = drawer.render("thanks", {"name": "Jo", "date": "today"})
    assert out == {"subject": "Thanks, Jo!", "body": "Hi Jo,\nGot it on today."}


def test_stationery_render_refuses_missing_or_extra():
    drawer = stationery.StationeryDrawer()
    drawer.add("thanks", "Hi {name}", "body {name}")
    with pytest.raises(KeyError):
        drawer.render("thanks", {})
    with pytest.raises(KeyError):
        drawer.render("thanks", {"name": "Jo", "typo": "x"})


def test_stationery_rename_and_names():
    drawer = stationery.StationeryDrawer()
    drawer.add("b", "s", "body")
    drawer.add("a", "s", "body")
    drawer.rename("b", "c")
    assert drawer.names() == ["a", "c"]
    with pytest.raises(ValueError):
        drawer.add("a", "s", "body")


def test_stationery_compose_with_client():
    drawer = stationery.StationeryDrawer()
    drawer.add("ooo", "Out: {until}", "Back {until}.")
    client = builtin_mail.BuiltinMail()
    client.add_account("a", "a@example.com")
    draft = drawer.compose_with(
        client, "a", "ooo", ["b@example.com"], {"until": "Friday"}
    )
    assert draft.subject == "Out: Friday"
    assert draft.body == "Back Friday."


# ---------------------------------------------------------------------------
# mbox_storage
# ---------------------------------------------------------------------------


def _tmp_mbox(tmp_path):
    return mbox_storage.MboxArchive(str(tmp_path / "mail.mbx"))


def test_mbox_append_and_read_roundtrip(tmp_path):
    arc = _tmp_mbox(tmp_path)
    arc.append("a@example.com", ["b@example.com"], "Hello", "line one\nline two")
    msgs = arc.read_all()
    assert len(msgs) == 1
    assert msgs[0]["Subject"] == "Hello"
    assert "line two" in msgs[0].get_payload()


def test_mbox_from_line_escaped_in_body(tmp_path):
    arc = _tmp_mbox(tmp_path)
    arc.append("a@example.com", ["b@example.com"], "S", "From x wrote:\n> already")
    arc.append("c@example.com", ["d@example.com"], "S2", "second")
    assert arc.count() == 2  # the escaped line must not split a message
    msgs = arc.read_all()
    assert msgs[0]["Subject"] == "S"
    assert "From x wrote:" in msgs[0].get_payload()
    assert msgs[1]["Subject"] == "S2"


def test_mbox_get_and_compact(tmp_path):
    arc = _tmp_mbox(tmp_path)
    arc.append("a@example.com", ["b@example.com"], "One", "b1")
    arc.append("a@example.com", ["b@example.com"], "Two", "b2")
    assert arc.get(1)["Subject"] == "Two"
    with pytest.raises(IndexError):
        arc.get(7)
    assert arc.compact() == 2


# ---------------------------------------------------------------------------
# mail_filters
# ---------------------------------------------------------------------------


def _msg(**kw):
    base = {
        "from": "newsletter@example.com",
        "to": "me@example.com",
        "subject": "Sale ends soon",
        "body": "50% off everything",
    }
    base.update(kw)
    return base


def test_filters_move_and_stop_after():
    engine = mail_filters.FilterEngine()
    engine.add(
        mail_filters.MailFilter(
            name="newsletters",
            conditions=[mail_filters.Condition("from", "contains", "newsletter")],
            actions=[mail_filters.Action("move_to", "news")],
        )
    )
    engine.add(
        mail_filters.MailFilter(
            name="sales",
            conditions=[mail_filters.Condition("subject", "contains", "sale")],
            actions=[mail_filters.Action("flag")],
            stop_after=False,
        )
    )
    report = engine.run(_msg())
    assert report[0]["filter"] == "newsletters"
    assert len(report) == 1  # stop_after halted the second filter


def test_filters_any_match_and_regex():
    engine = mail_filters.FilterEngine()
    engine.add(
        mail_filters.MailFilter(
            name="urgent",
            conditions=[
                mail_filters.Condition("subject", "regex", r"(?i)urgent|asap"),
                mail_filters.Condition("from", "is", "boss@example.com"),
            ],
            actions=[mail_filters.Action("flag")],
            match_all=False,
        )
    )
    assert engine.run(_msg(subject="URGENT: read this"))
    assert not engine.run(_msg())


def test_filters_apply_to_client_moves_message():
    client = builtin_mail.BuiltinMail()
    client.add_account("a", "a@example.com")
    client.add_folder("a", "news")
    msg = client.compose("a", ["x@y.z"], "Sale", "body")
    client.receive(
        "a",
        builtin_mail.MailMessage(
            uid=msg.uid,
            account="a",
            from_addr="newsletter@example.com",
            to_addrs=["a@example.com"],
            subject="Sale",
            body="off",
            date=1,
        ),
    )
    engine = mail_filters.FilterEngine()
    engine.add(
        mail_filters.MailFilter(
            name="news",
            conditions=[mail_filters.Condition("from", "contains", "newsletter")],
            actions=[mail_filters.Action("move_to", "news")],
        )
    )
    report = engine.apply_to_client(client, "a", msg.uid)
    assert report[0]["actions"][0] == {"kind": "move_to", "argument": "news"}
    assert client.list("a", "news")[0].uid == msg.uid


def test_filters_bad_definitions_rejected():
    with pytest.raises(ValueError):
        mail_filters.Condition("bogus", "contains", "x")
    with pytest.raises(ValueError):
        mail_filters.Action("teleport", "mars")


# ---------------------------------------------------------------------------
# bayes_spamwatch
# ---------------------------------------------------------------------------


_SPAM = [
    "WINNER claim your free prize money now click here",
    "cheap meds buy now free shipping limited offer",
    "you inherited millions wire transfer needed urgent",
]
_HAM = [
    "meeting notes from yesterday's standup attached",
    "can you review the draft proposal by friday",
    "lunch tomorrow at the usual place sounds good",
]


def _trained():
    watch = bayes_spamwatch.SpamWatch()
    for text in _SPAM:
        watch.learn(text, True)
    for text in _HAM:
        watch.learn(text, False)
    return watch


def test_spamwatch_scores_trained_spam_and_ham():
    watch = _trained()
    label, prob = watch.score("free prize claim your money now")
    assert label == "spam" and prob > 0.9
    label, prob = watch.score("review the draft proposal by friday")
    assert label == "ham" and prob < 0.1


def test_spamwatch_undecided_on_unknown():
    watch = bayes_spamwatch.SpamWatch()
    assert watch.score("hello world") == ("undecided", 0.5)
    watch.learn("hello world", True)
    label, _ = watch.score("totally unrelated zebra quantum")
    assert label == "undecided"  # too few known words to judge


def test_spamwatch_unlearn_and_export_roundtrip():
    watch = _trained()
    before = watch.vocabulary_size()
    watch.unlearn(_SPAM[0], True)
    assert watch.vocabulary_size() <= before
    snap = watch.export()
    fresh = bayes_spamwatch.SpamWatch()
    fresh.load(snap)
    assert fresh.training_counts() == watch.training_counts()
    assert fresh.most_spammy(3)[0][1] >= fresh.most_spammy(3)[-1][1]


# ---------------------------------------------------------------------------
# phish_flagging
# ---------------------------------------------------------------------------


def test_phish_display_mismatch_flagged():
    insp = phish_flagging.PhishInspector()
    report = insp.inspect(
        '<a href="http://evil.example/x">https://mybank.example/login</a>'
    )
    assert report.suspicious
    assert any(f.rule == "display_mismatch" for f in report.flags)


def test_phish_ip_punycode_tld_flags():
    insp = phish_flagging.PhishInspector()
    report = insp.inspect(
        "visit http://192.168.0.5/login or http://xn--bnk-9db.example "
        "or https://secure-login.example.zip/verify"
    )
    rules = {f.rule for f in report.flags}
    assert {"ip_host", "punycode", "suspicious_tld"} <= rules


def test_phish_clean_link_no_flags_but_not_declared_safe():
    insp = phish_flagging.PhishInspector()
    report = insp.inspect("see https://example.com/about for details")
    assert report.links == ["https://example.com/about"]
    assert not report.suspicious
    # absence of flags is not a safety verdict — the report says nothing more
    assert report.flags_for("https://example.com/about") == []


def test_phish_message_level_inspection():
    insp = phish_flagging.PhishInspector()
    report = insp.flag_message(
        "account notice",
        'please verify at <a href="http://evil.example">https://secure.example.com</a>',
    )
    assert report.suspicious


# ---------------------------------------------------------------------------
# mail_search
# ---------------------------------------------------------------------------


def _indexed():
    idx = mail_search.MailIndex()
    idx.add(
        {
            "id": "m1",
            "from": "alice@example.com",
            "to": "me@example.com",
            "subject": "project phoenix update",
            "body": "the phoenix launch is on track for friday",
        }
    )
    idx.add(
        {
            "id": "m2",
            "from": "bob@example.com",
            "to": "me@example.com",
            "subject": "lunch plans",
            "body": "phoenix friday lunch at noon",
        }
    )
    idx.add(
        {
            "id": "m3",
            "from": "carol@example.com",
            "to": "me@example.com",
            "subject": "weekly report",
            "body": "numbers are up",
        }
    )
    return idx


def test_search_and_terms():
    idx = _indexed()
    hits = idx.search("phoenix friday")
    assert {h.doc_id for h in hits} == {"m1", "m2"}


def test_search_field_restriction_and_phrase():
    idx = _indexed()
    assert [h.doc_id for h in idx.search("from:alice")] == ["m1"]
    assert [h.doc_id for h in idx.search('"phoenix launch"')] == ["m1"]
    assert idx.search('"launch phoenix"') == []


def test_search_ranking_and_limit():
    idx = _indexed()
    hits = idx.search("phoenix")
    # m1 mentions phoenix twice (subject + body), m2 once
    assert hits[0].doc_id == "m1"
    assert idx.search("phoenix", limit=1) == [hits[0]]


def test_search_remove():
    idx = _indexed()
    assert idx.remove("m1")
    assert not idx.search("from:alice")
    assert idx.document_count() == 2
    assert not idx.remove("m1")
