"""Surveys — fun, skippable, local-first.

Every question is skippable (empty answer = skip). Any survey can be
aborted mid-run ("skip" at any prompt). Answers are stored locally with
600 permissions and never leave the machine. On completion the store
computes *aggregate* per-question tallies (counts of which options were
picked, never free-text answers, never who said what) and reports them
to DemandPulse's store via ``scan_seed`` — that's the full-circle
return to the hub.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

KINDS = ("choice", "scale", "text")


@dataclass
class Question:
    id: str
    prompt: str
    kind: str = "choice"  # choice | scale | text
    options: List[str] = field(default_factory=list)
    scale_min: int = 1
    scale_max: int = 5
    footer: str = ""  # playful flavor line, shown under the prompt

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            self.kind = "text"

    def valid(self, raw: str) -> bool:
        """Answers are never rejected hard — skips always pass."""
        text = (raw or "").strip()
        if not text:
            return True  # skipped
        if self.kind == "choice" and self.options:
            return text in self.options or text.isdigit() and 1 <= int(text) <= len(self.options)
        if self.kind == "scale":
            return text.isdigit() and self.scale_min <= int(text) <= self.scale_max
        return True

    def normalize(self, raw: str) -> str:
        text = (raw or "").strip()
        if not text:
            return ""
        if self.kind == "choice" and self.options and text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(self.options):
                return self.options[idx]
        return text


@dataclass
class Survey:
    id: str
    title: str
    tagline: str
    intro: str
    questions: List[Question]
    outro: str
    track: str = "both"  # ai | si | both

    def __post_init__(self) -> None:
        if self.track not in ("ai", "si", "both"):
            self.track = "both"


# ---------------------------------------------------------------- starter set

SURVEYS: Dict[str, Survey] = {}


def _reg(s: Survey) -> Survey:
    SURVEYS[s.id] = s
    return s


_reg(
    Survey(
        id="welcome-walk",
        title="The Familiarization Walk",
        tagline="five questions, zero homework — show Levi how you roll",
        intro=(
            "Fresh drops land all the time here, and they all circle back to "
            "the hub. This walk tells the organism what you actually care about "
            "so it stops guessing. Skip anything — really."
        ),
        questions=[
            Question(
                id="mission",
                prompt="First things first — what should Levi do for you FIRST?",
                options=[
                    "hunt work / find me gigs",
                    "build something with me",
                    "teach me the organism",
                    "keep me organized",
                ],
                footer="no wrong answers, only wrong guesses",
            ),
            Question(
                id="tone",
                prompt="How do you like your answers served?",
                options=["short and sharp", "deep and thorough", "playful, keep me grinning"],
                footer="you can change this anytime — I'm synthetic, not sensitive",
            ),
            Question(
                id="drop",
                prompt="Rolling drops ship year-round on three tracks. Which track pulls you?",
                options=["services — done-for-you work", "SI — the mind itself", "AI agents — the legion"],
                footer="each drop is its own MVP; nothing waits on everything",
            ),
            Question(
                id="checkin",
                prompt="Want me to check in when something worth your eyes drops?",
                options=["weekly digest", "daily nudge", "only the big ones", "I'll come to you"],
            ),
            Question(
                id="superpower",
                prompt="One sentence: if Levi had ONE superpower for you, what is it?",
                kind="text",
                footer="dream big — the legion reads these in aggregate",
            ),
        ],
        outro=(
            "Walk complete. Your answers stay on this machine — the hub only "
            "learns the shape of what users want, never your words."
        ),
        track="both",
    )
)

_reg(
    Survey(
        id="feature-hunt",
        title="Feature Hunt",
        tagline="a treasure hunt through the organism — find your favorite organs",
        intro=(
            "Somewhere in Levi's 170+ modules are the tools that'll make your "
            "week. This hunt maps which organs to introduce first. Every skip "
            "is a clue too."
        ),
        questions=[
            Question(
                id="organ",
                prompt="Which division would you tour first?",
                options=[
                    "Cybrus — vault, identity, the money gate",
                    "UniForge — the code surgeon",
                    "DemandPulse — the sensing skin",
                    "Oracle — the weighing mind",
                    "the bounty board — hunts for hire",
                ],
                footer="guided tours available — ask anytime",
            ),
            Question(
                id="service",
                prompt="First service you'd actually pay for?",
                options=[
                    "cyber audit of my stuff",
                    "a site lift (glow-up for my site)",
                    "job search that runs itself",
                    "a custom automation",
                ],
                footer="doctrine pricing: entry $1–5, always below the giants",
            ),
            Question(
                id="agent",
                prompt="If a legion agent worked a shift for you, the shift is…",
                options=["research", "writing", "code", "organizing chaos"],
            ),
            Question(
                id="fear",
                prompt="Be honest — what worries you about an AI this ambitious?",
                kind="text",
                footer="this one matters. the organism reads every word — in aggregate.",
            ),
        ],
        outro="Hunt mapped. The hub now knows which doors to open first.",
        track="both",
    )
)

_reg(
    Survey(
        id="vault-guard",
        title="Vault Guard Quiz",
        tagline="five quick checks — are your keys safer than a dragon's hoard?",
        intro=(
            "Cybrus guards the vault, but you're the other half of the wall. "
            "Quick posture check — playful, no grades, no shame. Skips welcome."
        ),
        questions=[
            Question(
                id="passwords",
                prompt="Where do your passwords live right now?",
                options=[
                    "a password manager",
                    "the browser",
                    "my head (good luck to me)",
                    "sticky notes (we need to talk)",
                ],
                footer="Cybrus has a local-first vault, just saying",
            ),
            Question(
                id="twofa",
                prompt="Two-factor on your important accounts?",
                options=["everywhere", "most places", "what's two-factor?"],
            ),
            Question(
                id="backup",
                prompt="If your phone died tonight, your stuff is…",
                options=["backed up, sleeping easy", "mostly safe", "gone — don't think about it"],
                footer="the organism backs itself up; you should too",
            ),
            Question(
                id="phish",
                prompt="A text says your package is stuck — click the link?",
                options=["verify the sender first", "click, then regret", "forward it to someone who knows"],
                footer="Cybrus rule #1: the link is never the link",
            ),
            Question(
                id="comfort",
                prompt="Rate your comfort with Levi holding your credentials in its local vault (1=never, 5=take my keys):",
                kind="scale",
                scale_min=1,
                scale_max=5,
            ),
        ],
        outro=(
            "Quiz done. Cybrus approves of the honesty. Security tips drop "
            "with the campaigns — opt in and they find you."
        ),
        track="si",
    )
)


_reg(
    Survey(
        id="si-deep-dive",
        title="The Mind Survey",
        tagline="tune the SI mind — how should Levi think for you?",
        intro=(
            "The SI track is the mind: the companion, the brain, Oracle, "
            "memory. Tell it how to think and it'll stop thinking wrong."
        ),
        questions=[
            Question(
                id="memory",
                prompt="How deep should Levi's memory of you go?",
                options=[
                    "remember everything, it's all useful",
                    "remember what matters, forget the noise",
                    "short memory — each day is new",
                ],
                footer="growth only ever writes growth-tagged memories — never policy, never identity",
            ),
            Question(
                id="proactive",
                prompt="When should the mind speak up unprompted?",
                options=[
                    "when it spots something time-sensitive",
                    "daily digest, nothing more",
                    "never — I'll come to it",
                ],
            ),
            Question(
                id="oracle",
                prompt="You ask Oracle for counsel. What do you want back?",
                options=[
                    "the move, and exactly why",
                    "options with trade-offs, I decide",
                    "a projection: five ahead, three locked",
                ],
                footer="Oracle weighs — it never scouts. DemandPulse does that.",
            ),
            Question(
                id="brain",
                prompt="The native brain is Levi's own weights, trained from scratch. What should it learn first?",
                kind="text",
                footer="it learns from the organism's own corpus — never the open web",
            ),
        ],
        outro="Mind tuned. The SI track adjusts — in aggregate, always.",
        track="si",
    )
)

_reg(
    Survey(
        id="agent-crew",
        title="Build Your Crew",
        tagline="the AI track: pick your agents, set their leash length",
        intro=(
            "The AI track fields the hands: the legion, the minions, the "
            "bounty hunter. Design your crew and how much rope they get."
        ),
        questions=[
            Question(
                id="crew",
                prompt="Which three agents make your starting crew? (pick the anchor)",
                options=[
                    "UniForge — the surgeon fixes my code",
                    "bounty hunter — hunts problems for pay",
                    "automation minions — the background swarm",
                    "DemandPulse scouts — always sensing",
                ],
                footer="490 seats in the legion. start with three.",
            ),
            Question(
                id="leash",
                prompt="How much autonomy for mid-level work?",
                options=[
                    "full auto with receipts — I trust the gates",
                    "auto, but ping me first each time",
                    "nothing without my explicit word",
                ],
                footer="the six gates govern regardless: plan → preview → permission → execute → verify → receipt",
            ),
            Question(
                id="shift",
                prompt="If a minion worked one background shift daily, the shift is…",
                options=[
                    "inbox zero — triage everything",
                    "money watch — income events + pool",
                    "code patrol — surgeon sweeps",
                    "news brief — the world, distilled",
                ],
            ),
            Question(
                id="dream",
                prompt="One automation you wish existed but doesn't:",
                kind="text",
                footer="the legion reads these in aggregate — today's wish is tomorrow's minion",
            ),
        ],
        outro="Crew drafted. The AI track musters — in aggregate, always.",
        track="ai",
    )
)


def get_survey(survey_id: str) -> Optional[Survey]:
    return SURVEYS.get(survey_id)


def take_survey(
    survey: Survey,
    answers: Dict[str, str],
    store: "EngagementStore | None" = None,
) -> Dict:
    """Record a completed survey non-interactively.

    ``answers`` maps question id → raw answer ("" = skipped). Invalid
    answers are dropped to skips, never hard errors. Returns the result
    dict (also persisted via the store when given).
    """
    cleaned: Dict[str, str] = {}
    skipped = 0
    for q in survey.questions:
        raw = (answers or {}).get(q.id, "")
        cleaned[q.id] = q.normalize(raw) if q.valid(raw) else ""
        if not cleaned[q.id]:
            skipped += 1
    result = {
        "survey_id": survey.id,
        "answers": cleaned,
        "answered": len(cleaned) - skipped,
        "skipped": skipped,
        "total": len(cleaned),
    }
    if store is not None:
        store.record_survey(result)
    return result


def run_interactive(survey: Survey, store: "EngagementStore | None" = None) -> Dict:
    """Interactive terminal run. Type 'skip' or leave blank to skip."""
    print(f"\n== {survey.title} ==")
    print(survey.tagline)
    print(survey.intro + "\n")
    answers: Dict[str, str] = {}
    for q in survey.questions:
        print(f"  {q.prompt}")
        if q.kind == "choice" and q.options:
            for i, opt in enumerate(q.options, 1):
                print(f"    {i}. {opt}")
        elif q.kind == "scale":
            print(f"    ({q.scale_min}–{q.scale_max})")
        if q.footer:
            print(f"    — {q.footer}")
        try:
            raw = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  (aborted — progress kept, nothing lost)")
            break
        if raw.lower() == "skip":
            raw = ""
        answers[q.id] = raw
        print()
    result = take_survey(survey, answers, store)
    print(survey.outro)
    print(f"  answered {result['answered']}/{result['total']} (skipped {result['skipped']})")
    return result
