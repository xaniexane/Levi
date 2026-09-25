"""Small demo: compile a plan, fire it, replay it. WORKING TITLE."""

from levi.phase3.dataflow import PlanList, TestDoubleDispatch, execute, replay

dispatch = TestDoubleDispatch()
dispatch.register("fetch", lambda ins, outs: {outs[0]: "page-of-%s" % ins["url"]})
dispatch.register("summarize", lambda ins, outs: {outs[0]: "sum(%s)" % ins["page"]})
dispatch.register("store", lambda ins, outs: {outs[0]: True, outs[1]: ins["summary"]})

plan = PlanList()
plan.add("a-fetch", "fetch", ["url"], ["page"])
plan.add("b-summarize", "summarize", ["page"], ["summary"])
plan.add("c-store", "store", ["summary"], ["stored", "echo"])
graph = plan.build(dispatch.known_ops, external_inputs=["url"])

trace = execute(graph, {"url": "https://example.com"}, dispatch)
print("fire order:", trace.fire_order)
print("outputs:", trace.outputs)

again = replay(graph, trace, {"url": "https://example.com"}, dispatch)
print("replay identical:", again.fire_order == trace.fire_order)

try:
    bad = PlanList()
    bad.add("x", "fetch", ["y"], ["z"])
    bad.add("y", "fetch", ["z"], ["y"])  # cycle
    bad.build(dispatch.known_ops, external_inputs=["url"])
except Exception as exc:  # noqa: BLE001 - demo
    print("build rejected:", exc.receipt["reason"])
