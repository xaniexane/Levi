"""python -m levi.copper — demo: a supervision recovery score on a fake clock."""

from . import FakeClock, Score, run


def main() -> None:
    healthy = {"ok": False}

    def restart() -> str:
        healthy["ok"] = True
        return "restarted"

    score = (Score("service-recovery-demo")
             .skip_if("already-healthy", lambda: healthy["ok"])
             .wait_ms(2_000)
             .exec("restart-service", restart)
             .wait_until("healthy", lambda: healthy["ok"],
                         timeout_ms=30_000, poll_ms=500))
    clock = FakeClock()
    receipt = run(score, clock=clock)
    print(f"score: {receipt.score_name}")
    print(f"completed: {receipt.completed}  stop: {receipt.stop_reason!r}")
    print(f"simulated time elapsed: {clock.now_ms()}ms")
    for e in receipt.events:
        print(f"  t={e['at_ms']:>6}ms  {e['op']:<10} {e['name']}")


if __name__ == "__main__":
    main()
