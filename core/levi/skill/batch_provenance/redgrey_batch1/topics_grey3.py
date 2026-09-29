# Grey team topics — chunk 3: resets (7) + snapshots (7)

GREY_3 = [
dict(
slug="range-reset-procedure",
title="Full Range Reset Procedure",
description="Reset the entire exercise range to its pristine snapshot between iterations.",
tags=["grey-team","resets","range","hygiene"],
risk="high", confirm=True,
blue_kw=["reset","range","snapshot"],
purpose=("Between exercise iterations the range must return to pristine: red artifacts gone, blue "
"changes reverted, logs archived. This procedure resets the full range to its snapshot — "
"destructive by design, which is why it's HIGH risk with confirmation required."),
when=[
"Between exercise iterations.",
"After destructive exercises.",
"Before handing the range to the next team.",
],
prereq=[
"Pristine snapshot verified restorable.",
"Exercise data archived (logs, evidence, artifacts).",
"Explicit reset authorization with the scope confirmed.",
"All teams notified and off the range.",
],
procedure=[
"Confirm authorization and scope: which segments reset, what is preserved (archived evidence).",
"Verify the pristine snapshot integrity before touching anything.",
"Archive any unarchived exercise data — reset destroys, archiving preserves.",
"Execute the reset: restore snapshots per the runbook order (network, identity, endpoints, services).",
"Verify the reset: pristine-state checks (hashes, service states, account lists) against the baseline.",
"Re-verify logging pipeline health post-reset.",
"Sign off the range-clean state with the exercise director.",
],
outputs=[
"Reset execution log.",
"Pristine-state verification results.",
"Range-clean sign-off.",
],
pitfalls=[
"Resetting before archiving — exercise data lost is an unrecoverable failure.",
"Unverified snapshots — verify restorability before you need it.",
"Partial resets leaving red artifacts — verify the full pristine state.",
],
references=[
"Range-operations literature.",
],
exercise_note="The full reset is the range's rebirth — destructive, verified, and never executed without confirmed authorization.",
),
dict(
slug="endpoint-reimage-reset",
title="Endpoint Reimage Reset",
description="Reimage exercise endpoints to gold images between phases.",
tags=["grey-team","resets","endpoints","reimage"],
risk="moderate", confirm=True,
blue_kw=["reimage","endpoints","reset"],
purpose=("Endpoints accumulate exercise artifacts fast — malware, persistence, config drift. This "
"reimage reset returns endpoints to gold images between phases: fast, complete, and the standard "
"hygiene between red and blue turns."),
when=[
"Between exercise phases.",
"After endpoint-compromise scenarios.",
"When endpoint state is suspect.",
],
prereq=[
"Gold images current and verified.",
"Endpoint data to preserve identified (usually none — endpoints are cattle).",
"Reset authorization for the endpoint set.",
],
procedure=[
"Confirm the endpoint set and the gold-image version.",
"Capture any required state (usually just the inventory — endpoints hold no exercise record).",
"Reimage from gold: PXE, template redeploy, or cloud re-provision per the platform.",
"Re-verify post-image: domain join, EDR check-in, logging flow, baseline snapshot.",
"Return endpoints to the exercise pool with the health checklist.",
"Log the reimage batch with timestamps.",
],
outputs=[
"Reimage batch log.",
"Post-image health verification.",
"Returned-to-pool inventory.",
],
pitfalls=[
"Reimaging the wrong endpoints — confirm the set, especially with similar hostnames.",
"Stale gold images — the image must include current agents and patches for the scenario.",
"Skipping post-image verification — a reimaged endpoint with no logging is a blind host.",
],
references=[
"Endpoint-management literature.",
],
exercise_note="Endpoints are cattle in the exercise — reimaged between phases without sentiment, verified before return.",
),
dict(
slug="ad-reset-procedure",
title="Active Directory Reset Procedure",
description="Reset the lab AD forest to its baseline between exercise iterations.",
tags=["grey-team","resets","active-directory","forest"],
risk="high", confirm=True,
blue_kw=["active-directory","reset","forest"],
purpose=("AD accumulates the most persistent exercise artifacts: backdoor accounts, Golden Tickets, "
"modified ACLs, replication metadata. This procedure resets the lab forest to its baseline — "
"authoritative restore or rebuild — between iterations."),
when=[
"Between AD-focused exercise iterations.",
"After domain-compromise scenarios.",
"When AD state can't be trusted.",
],
prereq=[
"Baseline DC snapshots or rebuild scripts verified.",
"Exercise data archived.",
"Explicit reset authorization.",
"All teams off the range.",
],
procedure=[
"Confirm authorization and the reset method (snapshot restore vs. authoritative rebuild).",
"Archive AD exercise data: event logs, replication metadata of interest, the attack timeline.",
"Execute the reset: restore DC snapshots in the correct order or rebuild from scripts.",
"Verify the reset: account inventory vs. baseline, ACL spot-checks, replication health, no residual exercise artifacts.",
"Re-verify auditing and log forwarding post-reset.",
"Sign off the clean forest with the exercise director.",
],
outputs=[
"AD reset execution log.",
"Baseline-verification results.",
"Clean-forest sign-off.",
],
pitfalls=[
"Resetting DCs out of order — replication will punish you.",
"Assuming the rebuild scripts still work — test them before the exercise, not during reset.",
"Residual exercise accounts — verify the account inventory against baseline.",
],
references=[
"Microsoft AD DS recovery documentation.",
],
exercise_note="The AD reset is the forest's clean slate — verified account by account, because AD remembers everything.",
),
dict(
slug="network-reset-procedure",
title="Exercise Network Reset Procedure",
description="Reset exercise network devices and rulesets to the as-built baseline.",
tags=["grey-team","resets","network","firewalls"],
risk="moderate", confirm=True,
blue_kw=["network","reset","firewalls"],
purpose=("Firewalls accumulate exercise rules, routes get modified, taps get moved. This procedure "
"resets the exercise network to its as-built baseline between iterations — rulesets, routes, and "
"monitoring taps."),
when=[
"Between network-focused exercise iterations.",
"After firewall-rule exercises.",
"When network state is suspect.",
],
prereq=[
"As-built network configuration archived.",
"Reset authorization.",
"Exercise traffic stopped.",
],
procedure=[
"Confirm authorization and the device set.",
"Archive the exercised configuration (the rule changes are exercise data).",
"Restore as-built configs: firewall rulesets, routes, NAT, tap/SPAN assignments.",
"Verify the restore: path tests per the as-built test plan, tap traffic flowing.",
"Re-verify monitoring: NDR and SIEM receiving network telemetry.",
"Sign off the clean network.",
],
outputs=[
"Network reset log.",
"As-built verification (path tests).",
"Monitoring re-verification.",
],
pitfalls=[
"Restoring configs to the wrong devices — verify device identity.",
"Lost tap/SPAN assignments — monitoring goes dark silently.",
"No path tests after restore — verify the network actually works.",
],
references=[
"Network-operations literature.",
],
exercise_note="The network reset restores the exercise's physics — verified path by path, because the next exercise depends on it.",
),
dict(
slug="credential-rotation-reset",
title="Exercise Credential Rotation Reset",
description="Rotate all exercise credentials between iterations to prevent cross-contamination.",
tags=["grey-team","resets","credentials","rotation"],
risk="moderate", confirm=True,
blue_kw=["credentials","rotation","reset"],
purpose=("Exercise credentials leak across iterations: red learns them, participants remember them, "
"notes preserve them. This rotation resets every exercise credential between iterations — accounts, "
"service principals, API keys, canary secrets — so each iteration starts clean."),
when=[
"Between exercise iterations.",
"After any suspected credential exposure.",
"Before a new team uses the range.",
],
prereq=[
"Credential inventory for the range (every account, key, secret).",
"Rotation tooling/scripts.",
"Reset authorization.",
],
procedure=[
"Inventory every exercise credential: user accounts, service accounts, API keys, certificates, canary secrets.",
"Rotate all of them: new passwords, new keys, reissued certificates — per the inventory, no exceptions.",
"Update the credential vault/store the teams use; revoke the old material.",
"Verify the rotation: sample-authenticate with new credentials, confirm old ones fail.",
"Brief incoming teams on the new credential set.",
"Log the rotation with timestamps.",
],
outputs=[
"Credential inventory with rotation status.",
"Old-credential invalidation verification.",
"Rotation log.",
],
pitfalls=[
"Missed credentials — the inventory must be complete, or the rotation is theater.",
"Old credentials still valid somewhere — verify invalidation, don't assume.",
"Credentials shared outside the vault — rotate and re-brief the handling rules.",
],
references=[
"Credential-management literature.",
],
exercise_note="Credential rotation is the iteration boundary — every secret fresh, every old secret dead, verified.",
),
dict(
slug="log-archive-and-purge",
title="Exercise Log Archive and Purge",
description="Archive exercise logs for analysis, then purge the pipeline for the next iteration.",
tags=["grey-team","resets","logs","archive"],
risk="moderate", confirm=True,
blue_kw=["logs","archive","purge","reset"],
purpose=("Exercise logs are evidence and analysis material — but the pipeline must start clean each "
"iteration. This procedure archives the logs immutably, verifies the archive, then purges the "
"live pipeline."),
when=[
"Between exercise iterations, after the analysis window.",
"Before the next iteration's logging verification.",
],
prereq=[
"Analysis complete or explicitly deferred with the data retained.",
"Archive storage with integrity verification.",
"Reset authorization.",
],
procedure=[
"Confirm the analysis window is closed and stakeholders agree to archival.",
"Export the exercise indices: full fidelity, with hashes per export.",
"Verify the archive: spot-restore and integrity-check before purging anything.",
"Purge the live pipeline: indices, buffers, forwarder queues — per the retention policy.",
"Verify the purge: pipeline empty, ready for the next iteration's canary verification.",
"Log the archive location, hashes, and purge completion.",
],
outputs=[
"Archive manifest with hashes.",
"Spot-restore verification.",
"Purge-completion log.",
],
pitfalls=[
"Purging before archive verification — the archive must be proven before the source dies.",
"Incomplete exports — verify index completeness, not just job success.",
"Retention-policy violations — follow the policy, document exceptions.",
],
references=[
"NIST SP 800-92 (log management).",
],
exercise_note="Logs are archived as evidence and purged as hygiene — verified in that order, always.",
),
dict(
slug="partial-reset-targeted",
title="Targeted Partial Reset",
description="Reset specific range components without a full-range reset.",
tags=["grey-team","resets","targeted","surgical"],
risk="moderate", confirm=True,
blue_kw=["reset","targeted","partial"],
purpose=("Sometimes only one component needs resetting: a compromised server, a polluted AD OU, a "
"misconfigured firewall. This procedure resets surgically — the named components only — without "
"disturbing the rest of the running exercise."),
when=[
"Mid-exercise, when one component is unrecoverable but the exercise continues.",
"To fix a broken scenario element without restarting.",
],
prereq=[
"Component-level snapshots or rebuild procedures.",
"White-cell approval (mid-exercise changes need control authority).",
"Reset authorization with the component scope explicit.",
],
procedure=[
"Get white-cell approval: confirm the exercise can continue around the reset.",
"Isolate the component: stop its exercise traffic, notify affected teams.",
"Reset the component from its snapshot or rebuild procedure.",
"Verify the component: health, logging, scenario functionality.",
"Reintegrate: resume traffic, confirm the exercise timeline accounts for the gap.",
"Log the partial reset with the white-cell approval reference.",
],
outputs=[
"Partial-reset log with approval reference.",
"Component health verification.",
"Reintegration confirmation.",
],
pitfalls=[
"Mid-exercise resets without white-cell approval — control authority, always.",
"Unannounced component outages confusing teams — notify before isolating.",
"Reintegration failures — verify the component works in the live exercise, not just alone.",
],
references=[
"Range-operations literature.",
],
exercise_note="The partial reset is surgery during the operation — precise, approved, and verified before the patient wakes.",
),
dict(
slug="snapshot-strategy-design",
title="Exercise Snapshot Strategy Design",
description="Design the snapshot strategy: what gets snapshotted, when, and how long it's kept.",
tags=["grey-team","snapshots","strategy","design"],
risk="low", confirm=False,
purpose=("Snapshots are the range's time machine — but only if the strategy covers the right "
"components at the right moments with sane retention. This design defines the snapshot strategy "
"before the exercise needs it."),
when=[
"During exercise planning.",
"For range programs (persistent strategy across exercises).",
],
prereq=[
"Range component inventory.",
"Storage capacity for snapshots.",
"Retention policy.",
],
procedure=[
"Inventory snapshot-capable components: VMs, DCs, network devices, cloud resources.",
"Define snapshot points: pristine baseline, pre-phase, pre-destructive-test, on-demand.",
"Define naming and metadata: exercise codename, timestamp, purpose, creator.",
"Define retention: how long snapshots live, when they're deleted, who approves deletion.",
"Define verification: snapshot integrity checks and periodic restore tests.",
"Publish the strategy; brief the grey team.",
],
outputs=[
"Snapshot strategy document.",
"Snapshot-point schedule.",
"Retention and verification policy.",
],
pitfalls=[
"No strategy — snapshots taken ad hoc, named 'final-final-2', kept forever.",
"Unverified snapshots — a snapshot that doesn't restore is a hope, not a backup.",
"No retention — snapshot sprawl eats the storage.",
],
references=[
"Backup and recovery literature.",
],
exercise_note="The snapshot strategy is the range's memory policy — designed before the exercise, or snapshots become clutter.",
),
dict(
slug="pristine-baseline-capture",
title="Pristine Baseline Snapshot Capture",
description="Capture the pristine baseline snapshot of the full range before exercise traffic.",
tags=["grey-team","snapshots","baseline","capture"],
risk="low", confirm=False,
purpose=("The pristine baseline is the ground truth every reset returns to. This capture snapshots "
"the full range — every component, in order — after provisioning and validation, before any "
"exercise traffic, and verifies each snapshot restores."),
when=[
"After range provisioning and validation.",
"Before any exercise traffic.",
"After scenario validation (the baseline includes the validated scenario).",
],
prereq=[
"Range fully provisioned and validated.",
"Logging pipeline verified.",
"Snapshot strategy published.",
],
procedure=[
"Quiesce the range: stop provisioning traffic, confirm steady state.",
"Capture snapshots in dependency order: storage/network, identity, endpoints, services — per the runbook.",
"Record metadata: exercise codename, timestamp, component versions, capture operator.",
"Verify each snapshot: integrity check plus a test restore of at least one component per tier.",
"Document the baseline manifest: what was captured, where it lives, how to restore.",
"Seal the baseline: mark read-only, restrict modification access.",
],
outputs=[
"Baseline snapshot manifest.",
"Per-component verification results.",
"Sealed baseline reference.",
],
pitfalls=[
"Capturing before validation completes — the baseline must be the validated state.",
"Unverified snapshots — test-restore before sealing.",
"Unsealed baselines modified later — seal it.",
],
references=[
"Backup verification literature.",
],
exercise_note="The pristine baseline is the range's origin point — captured carefully, verified by restore, sealed against drift.",
),
dict(
slug="pre-phase-snapshots",
title="Pre-Phase Snapshot Capture",
description="Capture snapshots before each exercise phase for phase-level rollback.",
tags=["grey-team","snapshots","phases","rollback"],
risk="low", confirm=False,
purpose=("Phases go wrong: a phase's destruction breaks the next phase's setup. Pre-phase snapshots "
"give the grey team phase-level rollback — restore the phase boundary without losing the whole "
"exercise."),
when=[
"Before each exercise phase.",
"Before destructive phases especially.",
],
prereq=[
"Snapshot strategy with phase points defined.",
"Phase boundary identified (exercise paused or quiesced).",
],
procedure=[
"At the phase boundary, quiesce exercise traffic.",
"Capture the phase snapshots per the component list — fast, automated, timestamped.",
"Verify capture completion per component (don't assume the job finished).",
"Record the phase-snapshot manifest with the exercise timeline position.",
"Resume the exercise; keep the snapshots until the phase's analysis is done.",
"Delete per the retention policy after the analysis window.",
],
outputs=[
"Phase-snapshot manifest.",
"Capture-verification per component.",
"Retention/deletion log.",
],
pitfalls=[
"Snapshotting a live firefight — quiesce first or capture garbage.",
"Assuming the snapshot job finished — verify per component.",
"Deleting before analysis — retention follows the analysis window.",
],
references=[
"Range-operations literature.",
],
exercise_note="Pre-phase snapshots are the exercise's save points — quick, verified, and the reason a bad phase doesn't end the exercise.",
),
dict(
slug="snapshot-integrity-verification",
title="Snapshot Integrity Verification",
description="Verify snapshot integrity and restorability on a schedule.",
tags=["grey-team","snapshots","integrity","verification"],
risk="low", confirm=False,
purpose=("Snapshots rot: storage corrupts, formats age, dependencies break. This verification "
"proves — on a schedule, not on hope — that the snapshots the range depends on actually restore.",
),
when=[
"On the strategy's verification schedule.",
"Before any planned reset that depends on the snapshots.",
"After storage changes.",
],
prereq=[
"Snapshot manifest with locations.",
"Isolated verification environment (never verify by restoring over the live range).",
],
procedure=[
"Select snapshots per the verification schedule (rotate coverage so everything gets tested).",
"Integrity-check: hashes, format validity, dependency completeness.",
"Test-restore into the isolated environment; verify the restored component boots and functions.",
"Record results per snapshot: verified, degraded, or failed.",
"For failures: re-capture from the live range (if the live state is good) or escalate.",
"Report verification status to the exercise director.",
],
outputs=[
"Verification report per snapshot.",
"Failure/remediation log.",
"Coverage rotation record.",
],
pitfalls=[
"Verifying by restoring over production — isolated environment, always.",
"Hash-checks without test restores — integrity isn't restorability.",
"100% verification every time — rotate coverage, it's sustainable.",
],
references=[
"Backup verification literature.",
],
exercise_note="Snapshot verification is the range's honesty check — proven by restore, on a schedule, before they're needed.",
),
dict(
slug="snapshot-restore-drill",
title="Snapshot Restore Drill",
description="Drill snapshot restores under time pressure to validate recovery procedures.",
tags=["grey-team","snapshots","restore","drill"],
risk="low", confirm=False,
purpose=("Restore procedures work on paper until they're timed. This drill restores range components "
"from snapshots under time pressure — validating the runbook, the tooling, and the grey team's "
"speed when an exercise depends on it."),
when=[
"Periodically, per the range program.",
"Before high-stakes exercises.",
"After restore-procedure changes.",
],
prereq=[
"Verified snapshots to restore from.",
"Isolated drill environment.",
"Restore runbook.",
],
procedure=[
"Declare the drill: the scenario (which components 'failed').",
"Execute the restore runbook under time: start the clock at declaration.",
"Time each stage: snapshot selection, restore execution, verification, handover.",
"Record deviations: runbook steps that didn't work, tooling gaps, slow stages.",
"Verify the restored components fully before stopping the clock.",
"Deliver the drill report with runbook fixes.",
],
outputs=[
"Restore drill timeline.",
"Runbook deviation list.",
"Runbook fixes.",
],
pitfalls=[
"Drilling against the live range — isolated environment.",
"Stopping the clock at 'restore initiated' — the clock stops at verified working.",
"Skipping the drill because 'we verified the snapshots' — verification isn't speed.",
],
references=[
"Disaster-recovery drill literature.",
],
exercise_note="The restore drill times the truth — how fast the range actually comes back when the exercise is waiting.",
),
dict(
slug="snapshot-lifecycle-cleanup",
title="Snapshot Lifecycle Cleanup",
description="Clean up expired snapshots per the retention policy with verification.",
tags=["grey-team","snapshots","lifecycle","cleanup"],
risk="moderate", confirm=True,
blue_kw=["snapshots","cleanup","retention"],
purpose=("Snapshots accumulate: every phase, every iteration, every 'just in case'. This cleanup "
"enforces the retention policy — deleting expired snapshots after verifying nothing depends on "
"them. MODERATE because deletion is irreversible."),
when=[
"Per the retention schedule.",
"When snapshot storage approaches capacity.",
],
prereq=[
"Retention policy with expiry rules.",
"Snapshot manifest with creation dates and purposes.",
"Deletion authorization.",
],
procedure=[
"List snapshots past retention: expired per the policy.",
"Verify no dependency: no planned reset, no pending analysis, no linked clones.",
"Confirm deletion authorization for the expired set.",
"Delete per the platform's safe procedure; verify deletion and storage reclamation.",
"Log every deletion: what, when, why, who authorized.",
"Report storage status post-cleanup.",
],
outputs=[
"Expired-snapshot list with dependency checks.",
"Deletion log with authorizations.",
"Post-cleanup storage report.",
],
pitfalls=[
"Deleting snapshots with pending analysis — check the analysis window.",
"Breaking linked clones — verify dependencies first.",
"Deleting without authorization — the policy plus explicit approval.",
],
references=[
"Data-lifecycle literature.",
],
exercise_note="Snapshot cleanup is retention policy with teeth — verified dependencies, authorized deletions, logged everything.",
),
dict(
slug="offsite-snapshot-replication",
title="Offsite Snapshot Replication",
description="Replicate critical snapshots offsite for range-program resilience.",
tags=["grey-team","snapshots","replication","offsite"],
risk="low", confirm=False,
purpose=("The range program's baselines are valuable: rebuilt scenarios, validated configurations. "
"This replication copies critical snapshots offsite — so a site failure doesn't erase the program's "
"foundation."),
when=[
"For persistent range programs.",
"After major baseline updates.",
"Per the replication schedule.",
],
prereq=[
"Offsite storage with adequate capacity and security.",
"Critical-snapshot list (baselines, gold images).",
"Encryption for snapshots in transit and at rest.",
],
procedure=[
"Identify the critical snapshots: pristine baselines, gold images, validated scenario states.",
"Replicate encrypted copies offsite per the schedule.",
"Verify the replicas: integrity checks and periodic test restores.",
"Document the replica inventory with locations and verification status.",
"Define the repatriation procedure: how snapshots come back if the primary site fails.",
"Report replication status to the program lead.",
],
outputs=[
"Replica inventory with verification status.",
"Repatriation procedure.",
"Replication status report.",
],
pitfalls=[
"Unencrypted snapshots offsite — encrypt in transit and at rest.",
"Unverified replicas — a replica that doesn't restore is a false comfort.",
"No repatriation procedure — replication without a return path is half a plan.",
],
references=[
"Backup replication literature.",
],
exercise_note="Offsite replication protects the program's foundation — encrypted, verified, and returnable.",
),
]
