"""Small demo: compose a namespace, operate through it. WORKING TITLE."""

from levi.phase3.plan9 import (
    DirectDispatch,
    audit_log,
    clear_audit_log,
    compose_namespace,
    operate,
)

clear_audit_log()
dispatch = DirectDispatch()
dispatch.register("read", lambda target, args: {"target": target, "v": 1})
dispatch.register("write", lambda target, args: {"wrote": args})
dispatch.register("list", lambda target, args: ["a", "b"])
dispatch.register("run", lambda target, args: "ran %s" % target)
dispatch.register("watch", lambda target, args: "watching")

ns, receipt = compose_namespace(
    "task-1",
    [
        {"mount": "/tools", "prefix": "/tools", "verbs": ["run", "read"]},
        {"mount": "/mem", "prefix": "/memory", "verbs": ["read", "write"], "budget": 2},
    ],
)
print("composed:", receipt["grants"])

print(operate(ns, "run", "/tools/calc", {"x": 1}, dispatch).value)
print(operate(ns, "write", "/mem/notes", "hello", dispatch).value)

try:
    operate(ns, "write", "/tools/calc", {}, dispatch)
except Exception as exc:  # noqa: BLE001 - demo
    print("denied verb ->", exc.receipt["reason"])

ns.close()
try:
    operate(ns, "read", "/tools/calc", None, dispatch)
except Exception as exc:  # noqa: BLE001 - demo
    print("after close ->", exc.receipt["reason"])

print("audit entries:", len(audit_log()))
