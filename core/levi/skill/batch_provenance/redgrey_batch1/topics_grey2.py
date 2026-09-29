# Grey team topics — chunk 2: scoring (8) + observers/referees (8)

GREY_2 = [
dict(
slug="scoring-model-design",
title="Exercise Scoring Model Design",
description="Design the exercise scoring model: objectives, weights, and evidence standards.",
tags=["grey-team","scoring","design","exercise"],
risk="low", confirm=False,
purpose=("Scoring turns exercise activity into assessment: which objectives were met, how well, with "
"what evidence. This design produces the scoring model before execution — objectives, weights, "
"evidence standards — so scoring is measurement, not opinion."),
when=[
"During exercise planning, before execution.",
"For competitive exercises especially.",
"When trending scores across exercise iterations.",
],
prereq=[
"Exercise objectives from the scenario.",
"Stakeholder agreement on what 'good' looks like.",
],
procedure=[
"Decompose objectives into scorable elements: detection, response time, containment, reporting.",
"Assign weights reflecting exercise priorities; document the rationale.",
"Define evidence standards per element: what proof earns the points (log excerpts, timelines, artifacts).",
"Design the scoring rubric: full/partial/no-credit criteria with examples.",
"Build the score sheet (tooling or template) and test it against a walkthrough.",
"Publish the model to all teams before execution — no secret scoring.",
],
outputs=[
"Scoring model with weights and rationale.",
"Evidence standards per element.",
"Tested score sheet.",
],
pitfalls=[
"Secret scoring models — publish before execution.",
"Weights without rationale — document why detection outweighs speed (or vice versa).",
"No evidence standards — scoring becomes opinion.",
],
references=[
"Exercise-evaluation literature; CTF scoring models (public).",
],
exercise_note="The scoring model is the exercise's grading rubric — designed and published before anyone is graded.",
),
dict(
slug="objective-evidence-collection",
title="Objective Evidence Collection",
description="Collect scoring evidence during the exercise: logs, timelines, and artifacts.",
tags=["grey-team","scoring","evidence","collection"],
risk="low", confirm=False,
purpose=("Scores need evidence: the log line that proves detection, the timestamp that proves response "
"time. This collection runs during the exercise, capturing the evidence the scoring model demands — "
"before logs roll and memories fade."),
when=[
"During exercise execution.",
"Continuously, not after the fact.",
],
prereq=[
"Scoring model with evidence standards.",
"Logging pipeline verified.",
"Evidence-collection tooling/access.",
],
procedure=[
"Monitor the exercise against the scoring elements; capture evidence as events occur.",
"Timestamp everything against the synchronized range clock.",
"Collect artifacts: alert screenshots, ticket records, timeline entries, team communications.",
"Maintain the evidence log: element, evidence, timestamp, collector.",
"Protect evidence integrity: write-once storage, hashes for key artifacts.",
"Hand the evidence package to the scorers at exercise end.",
],
outputs=[
"Evidence package per scoring element.",
"Evidence log with timestamps.",
"Integrity verification (hashes).",
],
pitfalls=[
"Post-exercise evidence hunting — collect during, not after.",
"Undated evidence — timestamps against the range clock or it's not evidence.",
"No integrity protection — hash the key artifacts.",
],
references=[
"Digital-evidence handling literature.",
],
exercise_note="Evidence is perishable — collected during the exercise with timestamps, or it's reconstruction, not evidence.",
),
dict(
slug="detection-scoring",
title="Detection Scoring",
description="Score blue-team detections against the exercise's detection objectives.",
tags=["grey-team","scoring","detection","blue-team"],
risk="low", confirm=False,
purpose=("Detection is usually the highest-weighted exercise objective. This scoring evaluates each "
"expected detection: was it caught, how fast, with what fidelity — against the evidence, not "
"against claims."),
when=[
"After exercise execution, during evaluation.",
"Per detection objective in the scoring model.",
],
prereq=[
"Scoring model with detection elements.",
"Evidence package with detection artifacts.",
"Red-team ground truth (what actually happened, when).",
],
procedure=[
"For each red action, compare against blue-team detections: detected, missed, or false-positive.",
"Score detection latency: action time (red ground truth) to alert time (blue evidence).",
"Score fidelity: did the alert identify the right technique, host, and scope?",
"Penalize fairly: missed detections per the rubric, false positives per the noise standard.",
"Reconcile with the red team: confirm the ground truth before finalizing misses.",
"Publish detection scores with the evidence cited.",
],
outputs=[
"Detection scorecard per objective.",
"Latency measurements.",
"Reconciled ground truth.",
],
pitfalls=[
"Scoring detections without red-team ground truth — reconcile first.",
"Latency measured against unsynchronized clocks — the NTP setup matters here.",
"False-positive penalties without a noise standard — define it in the model.",
],
references=[
"Detection-engineering literature (public).",
],
exercise_note="Detection scoring is where the exercise's honesty lives — ground truth from red, evidence from blue, scored against the published rubric.",
),
dict(
slug="response-scoring",
title="Response Scoring",
description="Score blue-team response: containment, eradication, and recovery actions.",
tags=["grey-team","scoring","response","blue-team"],
risk="low", confirm=False,
purpose=("Detection without response is a weather report. This scoring evaluates what the blue team "
"did with their detections: triage quality, containment speed and correctness, eradication "
"completeness, and recovery — each against evidence."),
when=[
"After exercise execution, during evaluation.",
"For IR-validation exercises especially.",
],
prereq=[
"Scoring model with response elements.",
"Evidence: tickets, comms, action logs, containment records.",
],
procedure=[
"Score triage: was the alert correctly prioritized and assigned? (Evidence: ticket/SOC records.)",
"Score containment: speed (detection to isolation) and correctness (right scope, no collateral).",
"Score eradication: was the red presence actually removed? (Verify with the red team.)",
"Score recovery: systems restored, verified clean, returned to service per the runbook.",
"Score communications: notifications made, stakeholders informed, per the comms plan.",
"Publish response scores with evidence and the red-team's verification of eradication.",
],
outputs=[
"Response scorecard per phase.",
"Containment/eradiation verification.",
"Communications assessment.",
],
pitfalls=[
"Eradication scored without red-team verification — confirm the removal.",
"Speed scored without correctness — fast wrong containment is a penalty, not a win.",
],
references=[
"Incident-response literature; NIST SP 800-61.",
],
exercise_note="Response scoring measures what happened after the alert — the part of the exercise that actually protects the organization.",
),
dict(
slug="red-team-effectiveness-scoring",
title="Red Team Effectiveness Scoring",
description="Score red-team effectiveness: objective achievement and tradecraft quality.",
tags=["grey-team","scoring","red-team","effectiveness"],
risk="low", confirm=False,
purpose=("The red team gets scored too: did they achieve their objectives, with what tradecraft, "
"and what did their path reveal about the defenses? This scoring keeps red honest and extracts "
"the defensive lessons."),
when=[
"After exercise execution.",
"For red-team capability assessment.",
],
prereq=[
"Red-team objectives from the scenario.",
"Red-team activity logs (their own reporting).",
"Blue-team detection results for comparison.",
],
procedure=[
"Score objective achievement: which red objectives were met, with evidence.",
"Score tradecraft: stealth (detections per action), efficiency, and ROE compliance.",
"Score the path: which defensive layers did each attack path defeat, and where did it stop?",
"Evaluate ROE compliance: any boundary crossings are scoring penalties and incident reports.",
"Compare red claims against blue-team evidence and grey-team observations; reconcile.",
"Publish red scores with the defensive lessons each path produced.",
],
outputs=[
"Red-team scorecard per objective.",
"Tradecraft assessment.",
"Defensive-layer defeat map.",
"ROE-compliance record.",
],
pitfalls=[
"Scoring red on stealth alone — objective achievement and lessons matter more.",
"Unreconciled red claims — verify against blue evidence.",
"ROE violations scored quietly — they're incidents, reported as such.",
],
references=[
"Red-team operations literature (public).",
],
exercise_note="Red-team scoring serves the defense — every red point is a defensive lesson documented.",
),
dict(
slug="score-adjudication",
title="Score Adjudication Process",
description="Adjudicate scoring disputes fairly with evidence and the published rubric.",
tags=["grey-team","scoring","adjudication","fairness"],
risk="low", confirm=False,
purpose=("Teams dispute scores — that's healthy, if the adjudication is fair. This process handles "
"disputes against the published rubric and the evidence, with written rulings, so scoring ends in "
"agreement (or documented disagreement), not resentment."),
when=[
"After scores are published, during the review window.",
"Whenever a team challenges a score.",
],
prereq=[
"Published scoring model and rubric.",
"Evidence packages.",
"Adjudication authority designated (exercise director or panel).",
],
procedure=[
"Open the dispute window with a deadline; collect challenges in writing with counter-evidence.",
"Adjudicate each dispute against the rubric and the evidence — not against opinions.",
"Issue written rulings: upheld, adjusted, or denied, with reasoning cited.",
"Adjust scores where the evidence supports it; document every change.",
"Close the window and publish final scores with the adjudication record.",
"Feed systemic disputes back into the scoring-model design for next time.",
],
outputs=[
"Adjudication rulings with reasoning.",
"Final scores with change log.",
"Scoring-model improvement notes.",
],
pitfalls=[
"Adjudication without the rubric — the rubric is the law.",
"Open-ended dispute windows — deadline and close.",
"Unwritten rulings — write them, or the dispute never ends.",
],
references=[
"Dispute-resolution literature; competition judging practices.",
],
exercise_note="Adjudication is where scoring earns trust — fair process, written rulings, and the rubric as the only authority.",
),
dict(
slug="score-trending",
title="Exercise Score Trending",
description="Trend exercise scores across iterations to measure program improvement.",
tags=["grey-team","scoring","trending","metrics"],
risk="low", confirm=False,
purpose=("One exercise is a snapshot; a program is a trend. This trending compares scores across "
"exercise iterations — detection rates over time, response-time curves — to prove the security "
"program is improving (or to show where it isn't)."),
when=[
"Across exercise iterations in a program.",
"For security-program metrics reporting.",
],
prereq=[
"Comparable scoring models across iterations (normalize where models changed).",
"Archived scores and evidence summaries.",
],
procedure=[
"Normalize scores across iterations for model changes; document the normalization.",
"Trend the key metrics: detection rate, mean time to detect/respond, objective achievement.",
"Correlate trends with program changes: new tooling, training, headcount.",
"Identify plateaus and regressions; investigate the causes.",
"Report the trend to leadership with the story behind the numbers.",
"Feed the findings into the next exercise's objectives.",
],
outputs=[
"Trend report with normalized metrics.",
"Correlation analysis with program changes.",
"Next-exercise objective recommendations.",
],
pitfalls=[
"Trending across incomparable models without normalization — document the adjustments.",
"Cherry-picked metrics — trend the full scorecard.",
"Trends without the story — numbers need the program context.",
],
references=[
"Security-metrics literature.",
],
exercise_note="Trending turns exercises into a program — the proof that the work compounds instead of repeating.",
),
dict(
slug="after-action-scoring-review",
title="After-Action Scoring Review",
description="Review the scoring process itself in the after-action: what the model missed.",
tags=["grey-team","scoring","after-action","improvement"],
risk="low", confirm=False,
purpose=("The scoring model is also graded: did it measure what mattered? This after-action review "
"evaluates the scoring process — missed behaviors, perverse incentives, rubric gaps — and improves "
"the model for next time."),
when=[
"During the after-action review.",
"After adjudication closes.",
],
prereq=[
"Final scores and adjudication record.",
"Participant feedback on the scoring.",
],
procedure=[
"Review each scoring element: did it discriminate good from bad performance?",
"Identify behaviors the model missed (good or bad) that should be scored next time.",
"Check for perverse incentives: did the model reward gaming over real performance?",
"Collect participant feedback on fairness and clarity.",
"Publish the scoring after-action with concrete model changes.",
"Version the scoring model for the next exercise.",
],
outputs=[
"Scoring after-action report.",
"Model change list.",
"Versioned scoring model.",
],
pitfalls=[
"Skipping the model's own review — the rubric rots without it.",
"Defensive scoring-team posture — the review is blameless.",
],
references=[
"After-action review literature.",
],
exercise_note="The scoring model is a living instrument — reviewed and versioned after every exercise, or it measures yesterday's priorities.",
),
dict(
slug="observer-tasking",
title="Observer Tasking and Placement",
description="Task and place exercise observers for coverage without interference.",
tags=["grey-team","observers","tasking","exercise"],
risk="low", confirm=False,
purpose=("Observers watch, record, and learn — without interfering. This tasking places observers "
"where the exercise's key moments happen, with clear observation objectives and non-interference "
"rules."),
when=[
"Before exercise execution.",
"When hosting VIP, leadership, or training observers.",
],
prereq=[
"Observer roster with clearances and objectives.",
"Exercise timeline with key moments identified.",
],
procedure=[
"Assign observers to teams/locations per their objectives and the coverage plan.",
"Brief the non-interference rules: observe, record, ask later — never direct, hint, or interrupt.",
"Provide observation guides: what to watch for, what to record, how to timestamp.",
"Establish the observer net (separate from team and control nets).",
"Schedule observer rotations for long exercises.",
"Collect observer notes at exercise end for the after-action.",
],
outputs=[
"Observer placement plan.",
"Non-interference briefing record.",
"Observer notes package.",
],
pitfalls=[
"Observers directing the exercise — non-interference is the rule, briefed and enforced.",
"Observers on the wrong net — separate observer communications.",
"Uncollected observer notes — collect them before everyone disperses.",
],
references=[
"Exercise-observation literature.",
],
exercise_note="Observers are the exercise's witnesses — placed deliberately, briefed on silence, and debriefed before they leave.",
),
dict(
slug="referee-authority-design",
title="Referee Authority and Jurisdiction Design",
description="Design referee authority: what referees can rule on, and how rulings bind.",
tags=["grey-team","referees","authority","governance"],
risk="low", confirm=False,
purpose=("Referees adjudicate the exercise in real time: was that action in bounds, does that "
"detection count, is the scenario still fair? This design defines their authority, jurisdiction, "
"and how rulings bind the teams — before the first dispute."),
when=[
"During exercise planning.",
"For competitive exercises especially.",
],
prereq=[
"Exercise rules and scoring model.",
"Referee roster with exercise credibility.",
],
procedure=[
"Define referee jurisdiction: ROE interpretation, scoring disputes in real time, fairness calls, safety stops.",
"Define ruling authority: which rulings bind immediately, which are appealable, and to whom.",
"Establish the ruling process: how to call a referee, response-time expectations, documentation.",
"Brief all teams on referee authority before execution — no surprises mid-exercise.",
"Log every ruling with timestamp and reasoning.",
"Review rulings in the after-action for consistency.",
],
outputs=[
"Referee charter with jurisdiction and authority.",
"Ruling log.",
"After-action consistency review.",
],
pitfalls=[
"Undefined authority — referees nobody listens to are decorations.",
"Unlogged rulings — log every one.",
"Mid-exercise authority invention — charter it before, not during.",
],
references=[
"Competition-officiating literature; exercise doctrine.",
],
exercise_note="Referee authority is the exercise's rule of law — chartered before execution, or disputes become arguments.",
),
dict(
slug="real-time-adjudication",
title="Real-Time Adjudication",
description="Adjudicate exercise events in real time: fairness calls and boundary rulings.",
tags=["grey-team","referees","adjudication","exercise"],
risk="low", confirm=False,
purpose=("Exercises need calls in the moment: is this technique in bounds, did that detection happen "
"before the deadline, is the red team still in scope? This is the real-time adjudication function — "
"fast, fair, and documented."),
when=[
"During exercise execution.",
"Whenever a boundary or fairness question arises.",
],
prereq=[
"Referee charter.",
"Referee access to team nets and the scenario.",
],
procedure=[
"Receive the adjudication request: who, what, when, what's at stake.",
"Rule against the ROE, the scenario, and the charter — quickly; the exercise doesn't pause for deliberation.",
"Communicate the ruling to affected teams immediately and log it.",
"For safety issues, rule first and document after — safety outranks procedure.",
"Track ruling patterns: repeated disputes about the same rule signal a charter gap.",
"Hand the ruling log to the after-action.",
],
outputs=[
"Real-time ruling log.",
"Charter-gap notes.",
"Safety-stop record (if any).",
],
pitfalls=[
"Slow adjudication stalling the exercise — decide fast, document after.",
"Safety questions treated as normal disputes — safety rules first.",
"Inconsistent rulings across referees — one charter, calibrated referees.",
],
references=[
"Officiating literature.",
],
exercise_note="Real-time adjudication keeps the exercise fair at speed — fast rulings, logged always, safety first.",
),
dict(
slug="fairness-monitoring",
title="Exercise Fairness Monitoring",
description="Monitor exercise fairness: information asymmetry, scenario balance, and team welfare.",
tags=["grey-team","referees","fairness","monitoring"],
risk="low", confirm=False,
purpose=("Exercises must be fair to be useful: teams need the information the scenario promises, the "
"scenario must be winnable, and nobody should be set up to fail. This monitoring watches fairness "
"continuously and corrects drift."),
when=[
"Throughout exercise execution.",
"Especially in competitive and assessment exercises.",
],
prereq=[
"Fairness criteria from the scenario design.",
"Monitoring feeds (team status, scenario progress).",
],
procedure=[
"Monitor information flows: is each team getting what the scenario promised, nothing more or less?",
"Track scenario balance: are objectives achievable, or has the scenario drifted unwinnable?",
"Watch for unintended advantages: tooling gaps, access mistakes, leaked information.",
"Correct drift in real time: re-balance injects, fix access, re-brief as needed — logged as referee actions.",
"Monitor team welfare: fatigue, frustration, safety — fairness includes people.",
"Report fairness status in the after-action.",
],
outputs=[
"Fairness-monitoring log.",
"Corrective actions with rationale.",
"After-action fairness assessment.",
],
pitfalls=[
"Fairness as an afterthought — monitor from the start.",
"Correcting without logging — every intervention is a referee action, recorded.",
"Confusing fairness with easiness — fair means winnable and honest, not easy.",
],
references=[
"Exercise-design literature.",
],
exercise_note="Fairness is what makes exercise results meaningful — monitored continuously, corrected openly, reported honestly.",
),
dict(
slug="observer-debrief",
title="Observer Debrief Process",
description="Debrief observers systematically to capture observations for the after-action.",
tags=["grey-team","observers","debrief","after-action"],
risk="low", confirm=False,
purpose=("Observers see things participants miss — but only if someone asks. This debrief captures "
"observer notes systematically before they disperse, feeding the after-action with the outside view.",
),
when=[
"Immediately after exercise execution, before observers depart.",
],
prereq=[
"Observer notes package.",
"Debrief facilitator and structured format.",
],
procedure=[
"Convene observers promptly — same day, before travel.",
"Walk the structured debrief: key moments, surprises, fairness notes, process observations.",
"Capture per-observer highlights and the consensus view separately.",
"Collect all notes, recordings, and artifacts into the package.",
"Identify observations needing follow-up (disputed facts, safety notes).",
"Feed the debrief output into the after-action review.",
],
outputs=[
"Observer debrief record.",
"Consensus and dissenting observations.",
"Follow-up item list.",
],
pitfalls=[
"Delayed debriefs — memories fade and observers leave.",
"Unstructured debriefs — structure it or lose the signal.",
"Observer input filed and forgotten — feed it to the after-action.",
],
references=[
"After-action review literature.",
],
exercise_note="The observer debrief is the exercise's outside view — captured same-day, structured, and fed forward.",
),
dict(
slug="vip-visitor-management",
title="VIP and Visitor Management",
description="Manage VIP and visitor presence without disrupting the exercise.",
tags=["grey-team","observers","vip","visitors"],
risk="low", confirm=False,
purpose=("Leadership visits build support for the exercise program — if they don't disrupt it. This "
"management plans VIP presence: what they see, when, with who explaining, and the boundaries that "
"keep the exercise running."),
when=[
"When leadership or external visitors attend.",
"For exercises with stakeholder-visibility goals.",
],
prereq=[
"Visitor roster with clearances.",
"Exercise timeline with good visit windows.",
],
procedure=[
"Schedule visits around key moments, not during critical team work.",
"Assign escorts: who guides, who explains, who keeps visitors out of team spaces.",
"Brief visitors: non-interference, what they may photograph/ask, classification boundaries.",
"Prepare the visit narrative: what the exercise is proving, what they're seeing.",
"Collect visitor feedback — leadership impressions matter for program support.",
"Log the visit for the after-action record.",
],
outputs=[
"Visit schedule with escorts.",
"Visitor briefing record.",
"Visitor feedback.",
],
pitfalls=[
"Unescorted visitors in team spaces — escort always.",
"Visits during the hardest exercise moments — schedule around them.",
"No narrative — visitors who don't understand what they're seeing don't advocate for the program.",
],
references=[
"Protocol and liaison literature.",
],
exercise_note="VIP visits are the program's advocacy engine — managed well, they convert observers into supporters.",
),
dict(
slug="referee-training",
title="Referee Training and Calibration",
description="Train and calibrate referees before the exercise for consistent rulings.",
tags=["grey-team","referees","training","calibration"],
risk="low", confirm=False,
purpose=("Referees rule consistently only if they're calibrated: same charter, same scenario "
"understanding, same ruling philosophy. This training gets them there before execution."),
when=[
"Before exercise execution, after the charter is published.",
],
prereq=[
"Referee charter and scenario.",
"Ruling scenarios for calibration exercises.",
],
procedure=[
"Brief referees on the charter, scenario, and scoring model.",
"Run calibration scenarios: sample disputes, each referee rules, compare and discuss.",
"Align on philosophy: letter vs. spirit of the rules, safety primacy, documentation standards.",
"Assign referee coverage: who watches what, handoff procedures.",
"Establish the referee net and ruling-log tooling.",
"Record calibration completion; note dissent for the charter record.",
],
outputs=[
"Calibration exercise results.",
"Ruling-philosophy alignment notes.",
"Coverage assignments.",
],
pitfalls=[
"Uncalibrated referees — inconsistent rulings destroy trust.",
"Skipping the philosophy alignment — the hard calls need shared principles.",
"No coverage plan — gaps in referee presence.",
],
references=[
"Officiating-training literature.",
],
exercise_note="Calibrated referees are the exercise's judiciary — trained together, ruling alike, before the first dispute.",
),
dict(
slug="exercise-safety-monitoring",
title="Exercise Safety Monitoring",
description="Monitor exercise safety: personnel, systems, and scope compliance in real time.",
tags=["grey-team","referees","safety","monitoring"],
risk="moderate", confirm=True,
blue_kw=["safety","monitoring","exercise"],
purpose=("Exercises are safe by design and by monitoring. This function watches safety continuously: "
"personnel welfare, system impacts, scope compliance — with the authority to pause or stop. "
"Marked MODERATE because safety monitoring carries stop authority over live exercise activity."),
when=[
"Throughout exercise execution.",
"Continuously, not periodically.",
],
prereq=[
"Safety criteria and stop thresholds from the ROE.",
"Monitoring feeds: range health, team status, scope-compliance watch.",
"Stop authority vested and communicated.",
],
procedure=[
"Monitor the safety feeds: system health, participant welfare, ROE-compliance indicators.",
"Watch for scope drift: red activity approaching boundaries, blue actions with production impact.",
"Enforce thresholds: pause on warning, stop on breach — no deliberation for safety stops.",
"Log every safety action with timestamp and rationale.",
"Brief the exercise director on safety status at each sync.",
"After any stop, lead the safety review before resuming.",
],
outputs=[
"Safety-monitoring log.",
"Pause/stop records with rationale.",
"Safety-review findings.",
],
pitfalls=[
"Monitoring without stop authority — authority must be real and communicated.",
"Delayed stops for deliberation — safety stops are immediate.",
"No post-stop review — every stop teaches something.",
],
references=[
"Safety-management literature; exercise doctrine.",
],
exercise_note="Safety monitoring is the exercise's circuit breaker — watching always, empowered to stop, and never overruled on safety.",
),
]
