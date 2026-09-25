"""Small demo: post work, take work, bounded waits, eval. WORKING TITLE."""

from levi.phase3.linda import LocalSpace, PendingTicket

space = LocalSpace()
space.declare_tag("task", 2)
space.declare_tag("result", 2)

space.post_tuple("task", "scan", "sector-7")
space.post_tuple("task", "scan", "sector-9")

taken = space.take_tuple(("task", "?job", "?sector"))
print("took:", taken["tag"], taken["fields"])

print("read:", space.read_tuple(("task", "?j", "?s"))["fields"])

# No match -> parked until the boundary, then a receipted fault.
ticket = space.take_tuple(("task", "purge", "?s"))
print("parked:", isinstance(ticket, PendingTicket))
space.boundary()
try:
    ticket.result()
except Exception as exc:  # noqa: BLE001 - demo
    print("boundary fault receipt:", exc.receipt["reason"])

# eval: the task's result becomes a tuple at the next boundary.
space.eval(lambda: ["scan", "done"], "result", task_id="worker-1")
space.boundary()
print("eval result:", space.read_tuple(("result", "?j", "?s"))["fields"])
print("receipts:", len(space.receipts()))
