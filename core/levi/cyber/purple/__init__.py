"""Purple-team adversary-emulation exercise framework.

SI red emulates adversaries against Chauncey's OWN systems — authorized
targets only — to harden them. Real red-team craft feeding defense,
inside the blue-team law. Unauthorized red-teaming is just hacking; this
framework refuses to run without authorization, by construction.

INVARIANTS (law-guard-prove; each has a property test in
tests/test_purple_team.py):
  I1. Default-deny: without a valid Authorization, zero phases execute.
  I2. Exact binding: authorization names one target_id and a set of
      scenario_ids; any other target or scenario is denied.
  I3. Window binding: the run must start inside [not_before, not_after].
  I4. Keeper-only: only the keeper (Chauncey) can authorize.
  I5. Non-destructive by construction: emulation synthesizes telemetry
      artifacts inside one exercise sandbox directory. No subprocess, no
      sockets, no writes outside the sandbox, no real credentials, no
      real data touched. "Exfiltration" phases write a fake exfil
      manifest — bytes never leave the machine.
  I6. Kill-switch honored: checked before every phase; a kill aborts the
      run, records KILLED, and no further artifacts are written.
  I7. Every attempt receipted: allowed, denied, killed, completed — each
      appends exactly one hash-chained receipt, even denials.
  I8. Closed loop: every emulated technique yields >= 1 Finding, and
      every Finding.playbook_id exists in the cyber playbook manifest
      (fail closed on unknown ids).
  I9. No offensive tradecraft in the framework: scenarios carry telemetry
      synthesis specs and detection rules only. No exploit code, no
      payloads, no step-by-step attack instructions — enforced by test.
"""

from core.levi.cyber.purple.authorize import (
    Authorization,
    AuthorizationDenied,
    AuthorizationStore,
    check,
)
from core.levi.cyber.purple.exercise import (
    ExerciseResult,
    KillSwitch,
    run_exercise,
)
from core.levi.cyber.purple.findings import (
    Finding,
    build_finding,
    build_findings,
    load_playbook_ids,
    load_playbook_index,
)
from core.levi.cyber.purple.receipts import Receipt, ReceiptLog
from core.levi.cyber.purple.sandbox import Sandbox, SandboxEscape
from core.levi.cyber.purple.scenarios import (
    EmulatedTechnique,
    Scenario,
    builtin_scenarios,
)

__all__ = [
    "Authorization",
    "AuthorizationDenied",
    "AuthorizationStore",
    "EmulatedTechnique",
    "ExerciseResult",
    "Finding",
    "KillSwitch",
    "Receipt",
    "ReceiptLog",
    "Sandbox",
    "SandboxEscape",
    "Scenario",
    "build_finding",
    "build_findings",
    "builtin_scenarios",
    "check",
    "load_playbook_ids",
    "load_playbook_index",
    "run_exercise",
]
