#!/usr/bin/env python3
"""Seed script: ingest 16 archive records from the KAI-9000 spec pack.

Pack (read-only input): /tmp/kc1/MUSE_KAI9000_CATALOGUE/
  (README.md, catalogue.json, SOURCES.md, HOWTO_USE_ALL.md)
Provenance zips: ~/workspace/user/files/MUSE_KAI9000_CATALOGUE.zip and
  MUSE_KAI9000_CATALOGUE-2.zip

All record text is written in the researcher's own words (ideas only;
no pack text copied verbatim). Per LEVI's identity rule, the pack is
treated strictly as a labeled KAI-9000 *reference*, never as a LEVI
source or feature.

Idempotent: ArchiveStore.add_many skips ids already present.
Usage:  python3 seed.py [--verify]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core"))

from levi.archive.record import ArchiveRecord, Provenance, make_id  # noqa: E402
from levi.archive.store import ArchiveStore  # noqa: E402

TAG = "k9000"
ERA = "2026"
PROV = Provenance(
    found_date="2026-09-15",
    research_slug="kai9000-spec-pack",
    notes=(
        "Read-only input: the four pack files at /tmp/kc1/MUSE_KAI9000_CATALOGUE/ "
        "(README.md, catalogue.json, SOURCES.md, HOWTO_USE_ALL.md), unpacked from "
        "Chauncey-uploaded ~/workspace/user/files/MUSE_KAI9000_CATALOGUE.zip and "
        "~/workspace/user/files/MUSE_KAI9000_CATALOGUE-2.zip (identical except "
        "zip1 adds the HOWTO). The pack is treated as labeled KAI-9000 REFERENCE "
        "material only, never as a LEVI source. All record text is paraphrased "
        "in the researcher's own words; no pack text was copied verbatim. "
        "Status badges are heuristic: the pack is a design spec, not a shipped "
        "product, so claims are design claims, not measured outcomes."
    ),
)

# (title, kind, summary, mechanism, decline, revival_recipe, levi_application)
RECORDS = [
    (
        "Graded heartbeat signaling",
        "technique",
        "A four-grade ladder for background agent output: the pulse may be fully "
        "silent, a one-line chrome nudge, a tagged card, or an escalate that "
        "requires a tap. Most pulses should end in silence.",
        "Every scheduled pulse resolves to exactly one grade. SILENT means the "
        "user sees nothing at all; NUDGE is a single line outside chat; CARD is "
        "a tagged, dismissible card; ESCALATE is a card that cannot be ignored "
        "and demands a tap. The grade is chosen by evidence, not by the mood "
        "of the run.",
        "The pack is a living spec with no canonical implementation; the "
        "inspiration projects it cites (Kai, Pulse, soul-agent, muse-brain) "
        "mostly died by the two failure modes this ladder targets: spammy "
        "heartbeats or mute-forever loops.",
        "Adopt the grade ladder as the output contract for every background "
        "loop: each tick returns a grade, and grades below a user-set "
        "threshold are swallowed locally.",
        "LEVI's heartbeat/daemon scheduler can emit SILENT/NUDGE/CARD/ESCALATE "
        "grades from its cron layer so quiet periods produce literally zero "
        "chat bubbles while missed commitments still punch through.",
    ),
    (
        "Evidence-gated instincts",
        "technique",
        "An instinct is a small formal spec: fires_on an observable signal, "
        "a cooldown, a maximum grade, and an action. No fire without evidence.",
        "Each instinct names a concrete trigger (an overdue lock, an empty "
        "work block, a detected repetition pattern), a cooldown window, and a "
        "grade ceiling. Score-free: there is no curiosity or drive meter to "
        "tune, so a trigger either matches or it does not.",
        "Drive-score systems get gimmicky — once the number is the target, the "
        "instinct fires on vibes. The spec explicitly replaces scores with "
        "boolean evidence checks.",
        "Represent every autonomous LEVI reflex as a fires_on/cooldown/max_grade "
        "spec so a reflex can be audited, disabled, or rate-limited without "
        "touching prose prompts.",
        "LEVI's daemon rules engine can store instincts as plain data "
        "structures (signal predicate + cooldown + grade cap) evaluated on "
        "each tick, replacing any fuzzy 'is this important?' scoring.",
    ),
    (
        "Focus mute with named exceptions",
        "technique",
        "A global quiet rule: in focus mode only two named actors may speak, "
        "everything else is queued, not delivered, and auto-invocation stops.",
        "A single mute flag re-routes all outbound agent speech into a queue. "
        "Exceptions are named explicitly (in the pack: the commitment watcher "
        "and the focus guard). No other subsystem may self-promote during "
        "mute; a global quiet command has identical semantics to focus mode.",
        "Notification fatigue is the top killer of ambient agents: when every "
        "subsystem can ping, users silence everything and miss the one signal "
        "that mattered.",
        "Make every LEVI background source route through one speech gate with "
        "a named-exception list; the user sees one mute switch, not per-bot "
        "toggles.",
        "LEVI can add a focus flag to its daemon turn pipeline so heartbeat, "
        "scheduler, and skill suggestions all check one gate before emitting, "
        "with only the commitment watcher allowed to break it.",
    ),
    (
        "Active-hours gate with overnight escalation rule",
        "technique",
        "Pulses are only fully awake inside a user-set window (the spec's "
        "default is 08:00-22:00 local). Outside it, only the commitment "
        "watcher's escalations may speak.",
        "Time-of-day is a hard gate on output grades: quiet hours demote every "
        "grade to silent except escalate-grade commitment misses. The window "
        "is user-configurable and stored in portable state.",
        "Nighttime agent chatter is pure loss: the user is asleep, the context "
        "is gone, and the card waits stale until morning. One process waking "
        "the user twice at 3am ends the whole experiment.",
        "Gate LEVI's scheduled work by local time of day with an explicit "
        "overnight policy: defer everything, speak only on escalations.",
        "LEVI's cron/heartbeat layer can read active hours from its state file "
        "and drop non-escalate output overnight, resurfacing it as a morning "
        "summary card.",
    ),
    (
        "Memory write gates against auto-vacuum sludge",
        "method",
        "Memory is never written by background auto-extraction. Writes pass "
        "through named gates only: explicit user capture, a review lesson, or "
        "an archivist promotion.",
        "All writes are event-triggered and auditable: the user said remember, "
        "locked a commitment, or promoted a fact; the evening review distilled "
        "a lesson; or the archivist daemon promoted a repeated observation. "
        "Small talk produces zero memory growth by construction.",
        "Always-on memory extraction (the Mem0 pattern the spec names) "
        "accumulates sludge: thousands of low-value facts that poison recall "
        "and make the store untrustworthy.",
        "Restrict LEVI's memory_write tool to a whitelist of call contexts "
        "(explicit capture, review distillation, archivist promotion) and "
        "reject writes from ordinary chat turns.",
        "LEVI's memory subsystem can log a provenance tag on every write; a "
        "periodic hygiene pass drops entries whose provenance is not one of "
        "the sanctioned gates.",
    ),
    (
        "Three-reinforcement promotion rule",
        "technique",
        "A fact may enter the always-loaded core memory block only after it "
        "has been reinforced three times, or via one explicit promotion.",
        "The core block (the part always in the prompt) is the most expensive "
        "real estate in the system. Promotion needs either three independent "
        "observations or an explicit user command, which creates scarcity and "
        "keeps the block trustworthy.",
        "Letting any single session write directly to core makes the prompt "
        "drift within days; the block fills with context that was relevant "
        "once and rots into noise.",
        "Apply the rule to LEVI's own core block: repeated observations "
        "accumulate evidence counts and promote only at three; single "
        "observations stay in recall until corroborated.",
        "LEVI's memory consolidation pass can count reinforcements per fact "
        "and promote at threshold, giving the user a visible reason ('seen "
        "3x') whenever core changes.",
    ),
    (
        "Capped five-agent delegation fleet",
        "method",
        "Instead of a swarm, exactly five specialist roles spin up for a "
        "locked fat task, produce one folded report, then die. No standing "
        "army.",
        "The roles are fixed: one defines interfaces, one builds the smallest "
        "working slice, one attacks weaknesses, one guards scope, one writes "
        "the digest. They share a single task lock, return one report, and "
        "are terminated — bloat is structurally impossible.",
        "Multi-agent swarms (the spec cites a 670-agent example) collapse "
        "under coordination overhead and conflicting instructions; more "
        "agents is usually more chaos, not more output.",
        "Cap LEVI's parallel delegation at five fixed roles with a mandatory "
        "fold step; refuse to spawn beyond the cap and summarize instead of "
        "multiplying threads.",
        "LEVI's subagent orchestration can use a fleet template with five "
        "named lanes and a merge contract, giving heavy tasks parallelism "
        "with a bounded blast radius.",
    ),
    (
        "Swappable soul masks under fixed laws",
        "technique",
        "The persona is a mask that swaps without changing the laws. Six "
        "named masks cover daily operation, crunch weeks, structural work, "
        "accountability, deep work, and ruthless plan review.",
        "Identity is split into immutable laws (lead with the useful thing, "
        "name drift, quote commitments) and a swappable voice layer. Switching "
        "masks changes tone and directness; the laws and obligations stay "
        "identical, so the user cannot lose the operator by changing the mood.",
        "Monolithic personalities conflate tone with policy: when the user "
        "asks for a softer assistant they accidentally relax the standards "
        "too.",
        "Separate LEVI's persona lenses (already a standing design) from its "
        "binding laws so a voice change can never downgrade obligations like "
        "honesty or human-in-the-loop for side effects.",
        "LEVI's existing persona system can document which rules live in the "
        "mask layer versus the law layer, so future personas inherit the "
        "binding rules automatically.",
    ),
    (
        "Three-tier memory in file-portable form",
        "method",
        "Memory is split into three tiers — always-loaded core, searchable "
        "recall, searchable archival — stored as plain portable files with no "
        "required server.",
        "Core holds the current commitments and standards and rides every "
        "prompt; recall holds recent digests and daemon logs; archival holds "
        "old facts and matured patterns. The whole thing is files (the spec "
        "shows core.json, recall.jsonl, archival.jsonl), so the memory can be "
        "backed up, diffed, and moved without a database.",
        "Heavy memory servers (the spec names Letta/MemGPT) are powerful but "
        "impose an always-on runtime; when the server dies, the memory is "
        "effectively gone.",
        "Keep LEVI's memory store as versioned plain files under ~/.levi so "
        "backup, audit, and migration need nothing but the filesystem.",
        "LEVI's memory already lives in files; this pattern documents the "
        "tier discipline (core/recall/archival with promotion rules) as the "
        "governed way to grow it.",
    ),
    (
        "Named daemon archetypes with owns-wake-visible contract",
        "method",
        "Background responsibilities are packaged as named daemons, each with "
        "a stated domain it owns, a wake schedule, and a visibility rule for "
        "when it may surface.",
        "Each daemon is a one-domain process: the commitment daemon owns "
        "locks, the focus daemon owns deep-work integrity, the digest daemon "
        "owns session summaries, the hygiene daemon owns memory cleanup, and "
        "so on. 'Owns / wake / visible' is the whole contract — no daemon may "
        "leak into another's domain.",
        "Cron scripts without owners rot into overlapping jobs that all "
        "message the user; nobody can say which one is responsible when a "
        "reminder misfires.",
        "Model LEVI's scheduled work as named daemons with explicit domains "
        "and visibility rules so each background job has exactly one owner.",
        "LEVI's heartbeat and scheduler definitions can be rewritten as a "
        "daemon table (name, owns, wake, visible) that the cron layer reads "
        "directly, making behavior auditable from one file.",
    ),
    (
        "Silent-unless-signal heartbeat",
        "technique",
        "The pulse's healthy state is total silence: when there is nothing "
        "worth surfacing, the tick resolves to an internal OK and the user "
        "sees nothing.",
        "Each tick computes its result first and renders output only if a "
        "signal crossed a threshold. Quiet is not an error and not a missing "
        "feature — it is the proof the system is working. The user learns "
        "that a message always means something.",
        "Agents that chatter on every tick train the user to ignore them; the "
        "moment they go silent, the user assumes breakage instead of health.",
        "Default LEVI's background ticks to silent success and only emit when "
        "a threshold is crossed, so every visible message carries information.",
        "LEVI's cron job runs can log internally and stay silent on success, "
        "surfacing only graded exceptions — the growth-loop journal already "
        "follows this pattern.",
    ),
    (
        "Command versus instinct split rule",
        "technique",
        "Anything the user can trigger by command must not also auto-trigger "
        "as an instinct, and vice versa. Never both for the same job.",
        "The split is a naming and routing discipline: commands are explicit "
        "user invocations, instincts are evidence-fired automations. Assigning "
        "one job to both paths guarantees double execution or conflicting "
        "output; the rule forbids the overlap at design time.",
        "Duplicate firing is the most embarrassing automation bug: the user "
        "types the command and the daemon fires anyway, producing two "
        "answers and zero trust.",
        "Maintain a registry mapping each LEVI capability to exactly one of "
        "'command' or 'instinct'; CI can flag any capability claimed by both.",
        "LEVI's skill/daemon catalogs can carry a fires field (manual vs a "
        "signal predicate) so the loader refuses to register the same job on "
        "both paths.",
    ),
    (
        "One-tap prompt chips",
        "technique",
        "Small labeled buttons that inject a fixed prompt fragment: a few "
        "words on screen, a full instruction underneath.",
        "Each chip pairs a human-readable label with a canned injection "
        "(triage this, name the avoidance, define the minimum shippable). One "
        "tap delivers a structured instruction the user would not have typed "
        "in full — the friction of phrasing the request drops to zero.",
        "Good prompting dies in the blank text box: users know they want "
        "help but do not want to compose the instruction each time.",
        "Expose LEVI's highest-value prompt patterns as named chips in the "
        "chat UI so one tap invokes a full structured instruction.",
        "LEVI's web/Android clients can render a chip bar bound to named "
        "prompt templates stored locally, keeping the mechanism fully "
        "offline.",
    ),
    (
        "Global quiet and loud daemon control",
        "technique",
        "One user command silences every background actor except the named "
        "exceptions; one command restores full volume. It is sacred: nothing "
        "may override it.",
        "Quiet is a master flag read by every daemon and skill before "
        "emitting. Loud clears it. The flag outranks all other scheduling "
        "logic — a daemon with something to say must queue it, not speak it, "
        "while quiet is set.",
        "Per-bot mute toggles put the bookkeeping on the user; they give up "
        "and mute the whole channel instead, losing the critical signals too.",
        "Give LEVI a single quiet/loud switch at the chat layer that every "
        "background source honors, with the exception list visible in help.",
        "LEVI's turn pipeline can check a global quiet flag before any "
        "daemon-generated speech, with an explicit short list of breakers.",
    ),
    (
        "Two-miss escalation with original-lock quoting",
        "technique",
        "When a locked commitment is missed twice, the system escalates: it "
        "quotes the user's original wording back and demands a new time or "
        "an explicit drop — no pep talk.",
        "The first miss gets a check-in; the second triggers escalation with "
        "the exact original commitment quoted verbatim, forcing the user to "
        "either recommit with a time or kill it openly. Ambiguity is not an "
        "option the design offers.",
        "Missed commitments rot silently when the system accepts vague "
        "reschedules; the user learns that locks are decorative.",
        "Model LEVI's commitment tracking with a miss counter and a fixed "
        "escalation script at two misses: quote, demand time or drop.",
        "LEVI's warden-style tracking can store the original lock text and "
        "surface it verbatim at escalation, making the accountability loop "
        "mechanical rather than motivational.",
    ),
    (
        "Weekly forced kill-list",
        "technique",
        "Once a week the system forces a stop-doing list: three things to "
        "stop, one of which must be a meeting, a half-project, or a vanity "
        "metric.",
        "A scheduled session demands exactly three kills, with a category "
        "constraint that blocks the easy answers. The output is a committed "
        "stop list, not advice — the mechanism attacks scope creep by making "
        "stopping a first-class weekly ritual.",
        "Productivity systems optimize adding and scheduling; nothing ever "
        "gets removed, so the list grows until the system collapses under "
        "its own commitments.",
        "Add a weekly LEVI ritual that produces a concrete stop-doing list "
        "with the same category pressure, and wire it to actually cancel or "
        "archive the killed items.",
        "LEVI's weekly review can include a mandatory kill-list card; the "
        "growth loop can then track whether killed items actually stayed "
        "dead.",
    ),
]


def build_records() -> list[ArchiveRecord]:
    records = []
    for title, kind, summary, mechanism, decline, recipe, app in RECORDS:
        rid = make_id(kind, TAG, title, ERA)
        records.append(
            ArchiveRecord(
                id=rid,
                title=title,
                era=ERA,
                kind=kind,
                summary=summary,
                mechanism=mechanism,
                decline=decline,
                revival_recipe=recipe,
                levi_application=app,
                sources=[],
                rating="useful-pattern",
                status="alive-underused",
                skepticism=(
                    "Spec-level claims only: the pack is a design document, "
                    "not a shipped product with measured outcomes. Status is "
                    "heuristic (alive-underused) since the spec is current "
                    "and referenced but has no canonical implementation to "
                    "check against."
                ),
                provenance=PROV,
            )
        )
    return records


def main() -> int:
    store = ArchiveStore()
    before = store.count()
    result = store.add_many(build_records())
    after = store.count()
    print(
        "before=%d added=%d skipped=%d after=%d"
        % (before, result["added"], result["skipped"], after)
    )
    if "--verify" in sys.argv:
        from levi.archive.search import search  # noqa: E402

        hits = search(store, "focus mute")
        print("search 'focus mute': %d hit(s)" % len(hits))
        for h in hits[:3]:
            print("  -", h.record.id, "|", h.score if hasattr(h, "score") else "")
        rec = store.get("arch-%s-technique-graded-heartbeat-signaling-2026" % TAG)
        print(
            "direct get signal-grades record:", "OK" if rec is not None else "MISSING"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
