"""Demo: one apprentice walks the curriculum (working title: crafts)."""

from __future__ import annotations

from .curriculum import ApprenticeRecord, Lesson, default_curriculum
from .gates import attempt
from .school import (
    ROTATION_ROLES,
    complete_lesson,
    complete_rotation,
    diagnose_failure,
    graduate,
    record_lesson_failure,
    run_exit_battery,
)


def main() -> None:
    stages = default_curriculum()
    record = ApprenticeRecord(agent_id="demo-apprentice")

    # Locked capability: receipted fault, task never runs.
    executed = []
    ok, fault = attempt(record, stages, "publish", lambda: executed.append("ran"))
    print("attempt publish (novice):", ok, fault)

    # Pass the novice entry lesson, pass exit battery -> journeyman.
    complete_lesson(
        record,
        stages,
        Lesson("L1-observe", "novice", "ambient_noise", "watch", "pass"),
        True,
    )
    run_exit_battery(record, stages, True)

    # A seeded failure: Sloyd diagnosis names the new variable first.
    lesson = Lesson(
        "L2-classify",
        "journeyman",
        "unseen_sender",
        "classify 10 messages",
        ">=8 correct",
    )
    entry = record_lesson_failure(record, lesson, "new_variable", "seeded")
    print("diagnosis:", diagnose_failure(record, lesson, entry))

    # Rotations in fixed order; graduate after the chef-d'oeuvre passes.
    run_exit_battery(record, stages, True)
    for role in ROTATION_ROLES:
        complete_rotation(record, role)
    verdict = graduate(
        record,
        stages,
        {"id": "piece-1", "sound": True},
        lambda piece: bool(piece["sound"]),
    )
    print("graduation:", verdict)
    print("record bytes:", len(record.to_canonical()))


if __name__ == "__main__":
    main()
