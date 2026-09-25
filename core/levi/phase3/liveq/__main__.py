"""Small demo: live query, typed port, boundary flush. WORKING TITLE."""

from levi.phase3.liveq import LiveQHub

hub = LiveQHub()
seen = []
hub.register_query({"key": "target"}, lambda qid, facts: seen.extend(facts))

hub.create_port("mind-link", {"kind": str, "body": str}, owner="mind-a")
hub.send("mind-link", {"kind": "ping", "body": "hello"})

try:
    hub.send("mind-link", {"kind": "ping"})  # malformed
except Exception as exc:  # noqa: BLE001 - demo
    print("schema fault ->", exc.receipt["reason"])

hub.view.write_fact("target", "sector-7")
hub.view.write_fact("other", "noise")
report = hub.boundary_flush()
print("flush:", {k: report[k] for k in ("messages_delivered", "queries_updated")})
print("query saw:", [(f["key"], f["value"]) for f in seen])
print("port inbox:", hub._ports["mind-link"].inbox[0]["payload"])
