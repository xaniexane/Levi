"""
Offline brain atlas — dense seed knowledge across subject fields A–Z+.

Synthetic intelligence baseline for local use: principles, checklists, and
first-principles frames — not medical/legal advice. Tagged for retrieval.
"""

from __future__ import annotations

from typing import List, Tuple

try:
    from levi.brain.seed_neuro import NEURO_ATLAS
except Exception:
    try:
        from seed_neuro import NEURO_ATLAS
    except Exception:
        NEURO_ATLAS = []
try:
    from levi.brain.seed_neuro_more import NEURO_MORE
except Exception:
    try:
        from seed_neuro_more import NEURO_MORE
    except Exception:
        NEURO_MORE = []
try:
    from levi.brain.seed_neuro_pack3 import NEURO_PACK3
except Exception:
    try:
        from seed_neuro_pack3 import NEURO_PACK3
    except Exception:
        NEURO_PACK3 = []

# (text, tags...)
ATLAS: List[Tuple[str, List[str]]] = [
    # A
    (
        "Accounting basics: assets = liabilities + equity. Cash flow is not profit. Track runway monthly.",
        ["accounting", "business", "finance"],
    ),
    (
        "Anxiety regulation: name the sensation, slow exhale longer than inhale, one next physical action, defer big decisions until body settles.",
        ["anxiety", "mental_health", "regulation"],
    ),
    (
        "Astronomy orient: north star / southern cross by hemisphere; light-years measure distance not time of travel for craft.",
        ["astronomy", "science"],
    ),
    # B
    (
        "Budget envelope: income → fixed needs → flexible wants → savings buffer (aim 3–6 months). Avoid lifestyle creep after raises.",
        ["budget", "finance", "life"],
    ),
    (
        "Biology cell: DNA → RNA → protein. Homeostasis keeps internal range; fever is regulated response not random heat.",
        ["biology", "science", "health"],
    ),
    (
        "Boundaries: clear request + consequence you will enact; not controlling others' feelings. Practice small.",
        ["boundaries", "relationships", "psychology"],
    ),
    # C
    (
        "Critical thinking: claim → evidence → alternative explanations → what would change your mind. Prefer primary sources.",
        ["critical_thinking", "logic", "learning"],
    ),
    (
        "Cyber hygiene: unique passwords + manager, MFA, delay unexpected money requests, patch OS, distrust urgent secrecy.",
        ["security", "cyber", "safety"],
    ),
    (
        "Conflict repair: soft start, own impact, listen for need under position, one agreement to try, schedule check-in.",
        ["conflict", "relationships", "communication"],
    ),
    # D
    (
        "Decision under uncertainty: reversible vs irreversible; decide reversible fast, irreversible slow with pre-mortem.",
        ["decision", "life_chess", "strategy"],
    ),
    (
        "Depression support (non-clinical): keep sleep/light/movement anchors; reach people; professional help if function drops — LEVI is not a therapist.",
        ["depression", "mental_health", "care"],
    ),
    (
        "Data hygiene: OBSERVED vs INFERENCE vs HYPOTHESIS. Do not treat model guesses as facts in corpus.",
        ["data", "epistemology", "levi"],
    ),
    # E
    (
        "Exercise minimum effective: consistency beats intensity; walk daily; strength 2×/week protects aging bodies.",
        ["exercise", "health", "habits"],
    ),
    (
        "Entrepreneur first principles: who pays, why now, delivery cost, support load. Sell reversible pilot before scale.",
        ["entrepreneur", "business", "levi_rail"],
    ),
    (
        "Ecology: systems have delays and feedbacks; local optimization can harm the whole — check second-order effects.",
        ["ecology", "systems", "environment"],
    ),
    # F
    (
        "First principles: strip analogy; what must be true physically/logically; rebuild option set; test cheapest assumption.",
        ["first_principles", "thinking", "levi"],
    ),
    (
        "Finance investing basics: low-cost diversified funds, long horizon, fees matter, past return ≠ guarantee.",
        ["investing", "finance"],
    ),
    (
        "Focus monotropism-aware: deep work blocks; batch switches; one primary tunnel per session when depth is high.",
        ["focus", "monotropism", "productivity"],
    ),
    # G
    (
        "Grief: waves not stages-only; ritual and witness help; no forced positivity timeline. Support > fix.",
        ["grief", "mental_health", "care"],
    ),
    (
        "Geography sense: maps distort; climate ≠ weather; cities sit on water, trade, and power routes for reasons.",
        ["geography", "world"],
    ),
    (
        "Goal design: outcome + metric + next action + review cadence. Vague goals produce vague effort.",
        ["goals", "life_equation", "productivity"],
    ),
    # H
    (
        "Health triage: emergency services for chest pain, stroke signs, severe breathing issues, suicidal intent with plan — call local emergency / 988 in US.",
        ["health", "emergency", "safety"],
    ),
    (
        "Habits: cue → routine → reward; shrink routine to 2 minutes to start; environment design > willpower.",
        ["habits", "psychology"],
    ),
    (
        "History method: primary sources, contingency, avoid single-cause stories, power and ordinary lives both matter.",
        ["history", "learning"],
    ),
    # I
    (
        "Information diet: fewer feeds, deeper sources, schedule intake; outrage is an engagement product.",
        ["media", "attention", "digital"],
    ),
    (
        "Interview prep: stories of conflict+result, questions for them, logistics check, follow-up note same day.",
        ["career", "interview"],
    ),
    (
        "Identity vs role: roles change; values and constraints are stabler anchors for decisions.",
        ["identity", "psychology"],
    ),
    # J
    (
        "Journaling useful: facts, feelings, next experiment — not rumination loops. Time-box 10 minutes.",
        ["journaling", "mental_health"],
    ),
    (
        "Justice conversation: define terms, separate harm from intent, evidence of pattern, proportionate remedy.",
        ["ethics", "communication"],
    ),
    (
        "Job search: network + targeted applications > mass spray; portfolio of proof beats adjective resumes.",
        ["career", "work"],
    ),
    # K
    (
        "Kaizen: 1% improvements compound; visible boards; stop the line on defects; blame process not only people.",
        ["kaizen", "quality", "work"],
    ),
    (
        "Knowledge management: capture → organize → distill → express. Second brain is retrieval, not hoarding.",
        ["pkm", "learning", "levi_brain"],
    ),
    (
        "Kindness operational: specific help, on time, without scorekeeping; boundaries still apply.",
        ["relationships", "ethics"],
    ),
    # L
    (
        "Life equation LEVI: x (have) + y (need) = z (destination). Interchangeable paths; update x honestly.",
        ["life_equation", "levi", "decision"],
    ),
    (
        "Life chess LEVI: if I do A, B becomes likely; want B → choose A; non-malicious influence and self-strategy.",
        ["life_chess", "levi", "strategy"],
    ),
    (
        "Learning loop: attempt → feedback → refine; interleave topics; teach-back tests understanding.",
        ["learning", "education"],
    ),
    # M
    (
        "Mental models set: inversion, second-order, margin of safety, circle of competence, opportunity cost.",
        ["mental_models", "thinking"],
    ),
    (
        "Money talk couples: shared visibility, personal fun money, big purchases threshold, monthly 20-min review.",
        ["money", "relationships"],
    ),
    (
        "Music practice: slow accurate reps, chunk hard bars, rest ears; consistency over binge sessions.",
        ["music", "practice"],
    ),
    # N
    (
        "Negotiation: BATNA, interests under positions, package trades, silence after offer, write agreements.",
        ["negotiation", "business", "communication"],
    ),
    (
        "Nutrition baseline: protein + fiber + water; ultra-processed as occasional; no single superfood myth.",
        ["nutrition", "health"],
    ),
    (
        "Network effects: value grows with users; cold start needs seeding; defensibility is not automatic.",
        ["business", "strategy"],
    ),
    # O
    (
        "Opportunity cost: choosing A spends the time/money that could fund B; name B explicitly.",
        ["economics", "decision"],
    ),
    (
        "Open source hygiene: license compliance, pin versions, read security advisories, do not copy into proprietary without review.",
        ["software", "legal", "dev"],
    ),
    (
        "Operations: checklists for rare critical tasks; single source of truth; postmortems without humiliation.",
        ["ops", "work", "quality"],
    ),
    # P
    (
        "Problem mountain: many symptoms often share one root; find the constraint that removes the most load.",
        ["systems", "levi", "problem_solving"],
    ),
    (
        "Productivity: one MITs/day, time-box, done definition; busyness is not progress.",
        ["productivity", "work"],
    ),
    (
        "Parenting signal: safety, predictability, repair after rupture; curiosity over lecture when possible.",
        ["parenting", "relationships"],
    ),
    # Q
    (
        "Quality: define done; prevent defects over inspect-all; customer-visible failures get root cause.",
        ["quality", "work"],
    ),
    (
        "Questions that open: what would good look like; what did you already try; what is the constraint.",
        ["communication", "coaching"],
    ),
    (
        "Quantitative self-check: measure what you will act on; vanity metrics waste attention.",
        ["data", "productivity"],
    ),
    # R
    (
        "Radical honesty (constructive): truth + care + actionable next step; not cruelty as brand.",
        ["honesty", "levi", "communication"],
    ),
    (
        "Risk matrix: likelihood × impact; mitigate high-impact even if rare; accept low-low.",
        ["risk", "decision"],
    ),
    (
        "Rest: sleep debt impairs judgment; schedule recovery like work; screens off near bed when possible.",
        ["sleep", "health"],
    ),
    # S
    (
        "Systems thinking: stocks, flows, feedback, delays; treat symptoms and roots differently.",
        ["systems", "levi"],
    ),
    (
        "Security incident: isolate, preserve logs, rotate credentials, notify affected parties as required.",
        ["security", "ops"],
    ),
    (
        "Story craft L.W.P.: consequence accrues; scar law; direction locks; void ghosts from denied paths.",
        ["writing", "lwp", "story"],
    ),
    # T
    (
        "Time: calendar reality over wish lists; protect deep blocks; decline is a skill.",
        ["time", "productivity"],
    ),
    (
        "Trust: consistency over intensity; small promises kept; repair faster than defensiveness.",
        ["trust", "relationships"],
    ),
    (
        "Teaching: goal performance, worked examples, then practice with feedback; assess understanding not attendance.",
        ["education", "learning"],
    ),
    # U
    (
        "Uncertainty: confidence separate from probability; update on evidence; avoid false precision.",
        ["uncertainty", "thinking"],
    ),
    (
        "UX basics: clarity > cleverness; next action obvious; errors recoverable; accessibility is quality.",
        ["ux", "product", "design"],
    ),
    (
        "Union of tools: prefer boring reliable stacks; novelty tax is real for non-tech operators.",
        ["tools", "ops"],
    ),
    # V
    (
        "Values → choices: when tradeoffs hurt, rank top 3 values for this season; decide against the ranking.",
        ["values", "decision"],
    ),
    (
        "Version control: small commits, meaningful messages, never force-push shared main without team rules.",
        ["git", "dev"],
    ),
    (
        "Vulnerability (relational): share process not only performance; match depth to trust level.",
        ["relationships", "psychology"],
    ),
    # W
    (
        "Writing clear: one idea per paragraph; subject-verb early; cut throat-clearing openers; read aloud.",
        ["writing", "communication"],
    ),
    (
        "Work meetings: agenda, decision owner, notes with actions; default to async if no decision needed.",
        ["work", "ops"],
    ),
    (
        "Wealth building slow: earn, control spend, invest consistently, skills that raise leverage.",
        ["wealth", "finance"],
    ),
    # X
    (
        "X-ray problems: separate symptom from root; one underlying constraint may clear a stack of issues.",
        ["problem_solving", "systems", "levi"],
    ),
    (
        "XML/JSON data: validate schema; never eval untrusted text as code; least privilege on parsers.",
        ["data", "security", "dev"],
    ),
    # Y
    (
        "You-scope: control inputs and responses; influence relationships; accept weather and others' wills.",
        ["stoicism", "psychology", "life"],
    ),
    (
        "Year review: keep / drop / try; quant + qualitative; one theme for next year max.",
        ["reflection", "goals"],
    ),
    # Z
    (
        "Zero-based attention: justify each recurring commitment from zero; subscriptions and meetings included.",
        ["attention", "productivity"],
    ),
    (
        "Zettelkasten idea: atomic notes, links, own words; network grows insight denser than folders alone.",
        ["pkm", "learning"],
    ),
    # Beyond A-Z — cross fields
    (
        "Alchemy LEVI: no pure loss — extract learning map from failure; inverse of what broke becomes design input.",
        ["alchemy", "levi", "resilience"],
    ),
    (
        "HITL rule: silence is not approval; money, production, customer data, destructive ops need explicit human yes.",
        ["hitl", "levi", "governance"],
    ),
    (
        "Demand vs invention: serve verified gaps; do not manufacture urgency or fake scarcity to sell.",
        ["ethics", "business", "levi"],
    ),
    (
        "Crisis soft path: stabilize body and minute; professional resources when danger; LEVI does not replace emergency services.",
        ["crisis", "safety", "levi"],
    ),
    (
        "Local-first software: your files, offline path, optional cloud boost — continuity must not depend on a vendor mood.",
        ["software", "levi", "privacy"],
    ),
    # --- Atlas expansion pack (dense offline SI) ---
    (
        "Apprenticeship mindset: deliberate practice, feedback loops, log errors; skill compounds slower than hype suggests.",
        ["learning", "career", "practice"],
    ),
    (
        "Attachment awareness: anxious seeks reassurance, avoidant seeks space; name the pattern before escalating conflict.",
        ["psychology", "relationships"],
    ),
    (
        "Architecture software: clear boundaries, fail loud, boring defaults; complexity is a cost center.",
        ["software", "architecture", "dev"],
    ),
    (
        "Baking science: gluten structure needs time/water; oven spring is steam + heat; measure by weight when precision matters.",
        ["cooking", "science", "home"],
    ),
    (
        "Battery care: avoid constant 100% heat for many chemistries; partial cycles often fine; follow device maker guidance.",
        ["tech", "hardware", "habits"],
    ),
    (
        "Bias checklist: confirmation, sunk cost, availability, authority — ask what evidence would change your mind.",
        ["thinking", "bias", "critical_thinking"],
    ),
    (
        "Branding honest: promise only what delivery can repeat; reputation is consistency under stress.",
        ["business", "marketing", "ethics"],
    ),
    (
        "Breath for calm: longer exhale than inhale, feet on floor, 90 seconds before hard replies.",
        ["regulation", "anxiety", "body"],
    ),
    (
        "Calendar triage: if it has no decision or relationship payoff, decline or convert to async note.",
        ["productivity", "work", "time"],
    ),
    (
        "Career ladder vs craft: titles lag skill; portfolio of shipped work outruns vague seniority claims.",
        ["career", "work"],
    ),
    (
        "Chemistry kitchen: acid + heat changes texture; emulsions need shear; salt early vs late changes outcome.",
        ["cooking", "science"],
    ),
    (
        "Child safety digital: defaults private, know contacts, delay image sharing, adults model consent.",
        ["parenting", "safety", "digital"],
    ),
    (
        "Civics basic: local decisions often hit daily life harder than national headlines; show up where votes are counted.",
        ["civics", "community"],
    ),
    (
        "Climate practical: reduce waste, efficiency first, vote and plan for extremes in your region — panic helps little.",
        ["environment", "climate", "planning"],
    ),
    (
        "Code review: prefer clarity, test the risky paths, ask 'what breaks if this is wrong?'",
        ["dev", "quality", "team"],
    ),
    (
        "Cold outreach: specific observation, clear ask, easy no; volume without relevance is noise.",
        ["business", "sales", "communication"],
    ),
    (
        "Community building: repeated small rituals beat one viral moment; moderators need rest too.",
        ["community", "social"],
    ),
    (
        "Compassion fatigue: helpers need boundaries and recovery; martyrdom collapses care capacity.",
        ["care", "health", "work"],
    ),
    (
        "Compound interest: time in market + fees + behavior beat stock-picking theater for most people.",
        ["finance", "investing"],
    ),
    (
        "Compression of ideas: if you cannot explain it simply, you may not understand it yet — or the idea is mud.",
        ["learning", "communication"],
    ),
    (
        "Conflict styles: competing, collaborating, compromising, avoiding, accommodating — pick by stakes and relationship.",
        ["conflict", "relationships"],
    ),
    (
        "Consent culture: enthusiastic ongoing yes; pressure and intoxication undermine consent.",
        ["ethics", "relationships", "safety"],
    ),
    (
        "Container gardening: light, water, drainage, soil; overwatering kills more than neglect for many plants.",
        ["home", "gardening"],
    ),
    (
        "Content creation: one audience, one promise, consistent cadence; metrics without craft rot quality.",
        ["media", "creative", "business"],
    ),
    (
        "Contract reading: parties, deliverables, money, termination, liability — highlight unknowns before signing.",
        ["legal", "business"],
    ),
    (
        "Cooking batch: proteins + grains + roasted veg base; sauces change the week; food safety on leftovers.",
        ["cooking", "home", "health"],
    ),
    (
        "Courage definition: action with fear present, sized to values — not reckless theater.",
        ["psychology", "values"],
    ),
    (
        "Credit hygiene: utilization, on-time history, avoid unnecessary hard pulls; emergency fund before optimization.",
        ["finance", "credit"],
    ),
    (
        "Crisis communication: facts first, empathy, next steps, single spokesperson when stakes are high.",
        ["communication", "ops", "leadership"],
    ),
    (
        "Customer discovery: watch behavior, not only surveys; ask about past workarounds and real budgets.",
        ["product", "business"],
    ),
    (
        "Debugging method: reproduce, isolate, hypothesize, test one variable, document the fix.",
        ["dev", "problem_solving"],
    ),
    (
        "Debt strategy: high-interest first or snowball for motivation; stop new leaks while paying down.",
        ["finance", "debt"],
    ),
    (
        "Deep work: protect unbroken blocks; shallow tasks batch; notifications are interruption products.",
        ["productivity", "focus"],
    ),
    (
        "Delegation: outcome + constraints + check-in cadence; do not delegate and then re-do silently.",
        ["leadership", "work"],
    ),
    (
        "Design critique: describe impact on user goals; separate taste from usability; suggest next experiment.",
        ["design", "ux", "team"],
    ),
    (
        "Digital estate: password manager inheritance, important docs folder, who gets access if you cannot.",
        ["planning", "family", "security"],
    ),
    (
        "Disagreement healthy: steelman first, share uncertainty, agree on facts before values clash.",
        ["communication", "thinking"],
    ),
    (
        "Disaster kit: water, meds, light, copies of IDs, meet-up plan; check batteries seasonally.",
        ["safety", "preparedness"],
    ),
    (
        "Documentation: write for the next human at 2am; examples beat abstractions; keep runbooks short.",
        ["ops", "dev", "writing"],
    ),
    (
        "Dopamine hygiene: delay infinite scroll after wins; pair rewards with recovery, not only stimulation.",
        ["attention", "habits", "health"],
    ),
    (
        "Drawing practice: shapes, edges, negative space; short daily sessions beat rare heroic ones.",
        ["art", "practice"],
    ),
    (
        "Driving defensive: space, eyes far, assume others mispredict; fatigue is impairment.",
        ["safety", "travel"],
    ),
    (
        "Email triage: two-minute rule, batch checks, templates for repeats; inbox zero is optional, response reliability is not.",
        ["productivity", "work"],
    ),
    (
        "Emotional labeling: naming affects intensity; 'I feel X about Y' beats vague explosion.",
        ["psychology", "regulation"],
    ),
    (
        "Employment boundaries: scope creep needs new agreement; written expectations reduce resentment.",
        ["work", "career"],
    ),
    (
        "Energy management: match hard cognitive work to peak hours; protect sleep as infrastructure.",
        ["productivity", "health"],
    ),
    (
        "Entrepreneur validation: pre-sell or waitlist before building the cathedral; love of craft ≠ market demand.",
        ["business", "startup"],
    ),
    (
        "Ergonomics: screen height, wrists neutral, stand breaks; pain early is a signal not a badge.",
        ["health", "work"],
    ),
    (
        "Estate basics: will/beneficiaries updated after life changes; not only for the wealthy.",
        ["planning", "family"],
    ),
    (
        "Ethics test: publicity test, reciprocity test, harm minimization — when incentives push the other way.",
        ["ethics", "decision"],
    ),
    (
        "Exercise recovery: progressive overload, rest days, protein + sleep; pain sharp ≠ good pain.",
        ["exercise", "health"],
    ),
    (
        "Facilitation: agenda, airtime equity, decision capture, end with owners and dates.",
        ["leadership", "meetings"],
    ),
    (
        "Family meetings: short, scheduled, one topic, appreciation first; kids can have voice sized to age.",
        ["family", "communication"],
    ),
    (
        "Fear vs danger: body alarms on both; check evidence of present threat before life-rewriting decisions.",
        ["anxiety", "psychology"],
    ),
    (
        "Feedback useful: specific, timely, changeable behavior, care for the person — not character verdicts.",
        ["team", "communication"],
    ),
    (
        "File organization: dates in names, one inbox folder, archive ruthlessly; search > perfect hierarchy.",
        ["productivity", "ops"],
    ),
    (
        "Financial independence path: save rate matters more than flashy returns early; lifestyle is the lever.",
        ["finance", "planning"],
    ),
    (
        "First aid mindset: scene safe, call help, stop major bleeding, AED when trained — take a real course.",
        ["safety", "health"],
    ),
    (
        "Friendship maintenance: initiate sometimes, celebrate without competition, repair after friction.",
        ["relationships", "social"],
    ),
    (
        "Game design lesson: clear goals, fair feedback, recoverable failure; applies to learning systems too.",
        ["design", "learning"],
    ),
    (
        "Gardening seasons: plant for your zone, mulch, observe microclimates; local extension services beat viral tips.",
        ["gardening", "home"],
    ),
    (
        "Gaslighting check: pattern of denying your experience + isolation; trust logs and outside witnesses.",
        ["psychology", "safety", "relationships"],
    ),
    (
        "Goal hierarchy: values → yearly theme → quarterly outcomes → weekly MITs — avoid goal soup.",
        ["goals", "productivity"],
    ),
    (
        "Grammar clarity: short sentences for instructions; active voice for responsibility; cut filler openers.",
        ["writing", "communication"],
    ),
    (
        "Grief at work: lower expectations temporarily, name needs, colleagues can offer concrete help not clichés.",
        ["grief", "work", "care"],
    ),
    (
        "Grocery strategy: list, protein first, shop perimeter more often, waste is a hidden tax.",
        ["home", "finance", "health"],
    ),
    (
        "Habits stack: attach new habit to existing anchor; environment beats motivation on bad days.",
        ["habits", "psychology"],
    ),
    (
        "Hiring signal: work sample > charm interview; define success metrics before the offer.",
        ["leadership", "business"],
    ),
    (
        "Home maintenance: water leaks, smoke/CO detectors, filter changes — boring prevents disasters.",
        ["home", "safety"],
    ),
    (
        "Hope practical: agency + pathway + goals; empty positivity without path deepens stuckness.",
        ["psychology", "resilience"],
    ),
    (
        "Hormones sleep: consistent schedule supports regulation; chronic restriction amplifies mood volatility.",
        ["sleep", "health"],
    ),
    (
        "Hospitality: clear end time, one good food, presence over perfection; hosts may ask for help.",
        ["social", "home"],
    ),
    (
        "Humor care: punch up not down; in crisis, mute wit — timing is ethics.",
        ["communication", "levi", "wit"],
    ),
    (
        "Identity theft basics: freeze credit if needed, monitor accounts, unique emails for finance.",
        ["security", "finance"],
    ),
    (
        "Immigration empathy: bureaucracy fatigue is real; documents and deadlines dominate life bandwidth.",
        ["community", "civics"],
    ),
    (
        "Incident review: timeline, contributing factors, systemic fixes; blameless on people, strict on truth.",
        ["ops", "leadership"],
    ),
    (
        "Influencer skepticism: paid enthusiasm is ads; check incentives before life changes.",
        ["media", "critical_thinking"],
    ),
    (
        "Insomnia hygiene: bed for sleep, wind-down ritual, worry dump earlier; chronic issues need professionals.",
        ["sleep", "health"],
    ),
    (
        "Insurance sense: cover catastrophic loss you cannot cash-flow; avoid over-insuring tiny risks.",
        ["finance", "planning"],
    ),
    (
        "Integration testing: test the seams between modules; unit green can still fail as a system.",
        ["dev", "quality"],
    ),
    (
        "Intellectual honesty: cite uncertainty, separate fact/opinion, correct yourself publicly when wrong.",
        ["ethics", "thinking"],
    ),
    (
        "Interior calm: reduce visual noise, one focal point, light matters more than new furniture.",
        ["home", "design"],
    ),
    (
        "Interviewing others: behavioral questions, silence after answers, score rubrics reduce bias.",
        ["leadership", "hiring"],
    ),
    (
        "Intuition use: trained pattern recognition helps; untrained gut often repeats bias — verify on high stakes.",
        ["decision", "thinking"],
    ),
    (
        "Investing behavior: autopilot contributions, ignore daily noise, rebalance occasionally — boredom is a feature.",
        ["investing", "finance"],
    ),
    (
        "JSON APIs: versioning, idempotency for writes, clear error shapes; clients fail without contracts.",
        ["dev", "software"],
    ),
    (
        "Job crafting: reshape tasks/relationships toward strengths within constraints; exit if values chronically clash.",
        ["career", "work"],
    ),
    (
        "Journalism consumer: multiple outlets, primary docs, beware synchronized talking points.",
        ["media", "critical_thinking"],
    ),
    (
        "Joy scheduling: put recovery and play on the calendar or work expands to fill all space.",
        ["health", "productivity"],
    ),
    (
        "Judgment under heat: postpone irreversible choices when flooded; 10-minute walk is a decision tool.",
        ["decision", "regulation"],
    ),
    (
        "Kitchen safety: separate raw proteins, thermometer for meats, cool leftovers quickly.",
        ["cooking", "safety", "health"],
    ),
    (
        "Knowledge handoff: record why not only what; pair while knowledge is still warm.",
        ["team", "ops"],
    ),
    (
        "Language learning: daily input + output, spaced repetition, embarrassment tolerance is a skill.",
        ["learning", "language"],
    ),
    (
        "Leadership service: remove blockers, clarify goals, protect focus — ego theater is not leadership.",
        ["leadership", "work"],
    ),
    (
        "Lease reading: rent, deposits, repairs, exit clauses, guest rules — photo condition on day one.",
        ["home", "legal"],
    ),
    (
        "Legacy projects: ship a thin vertical first; graveyards are full of 80% complete platforms.",
        ["product", "dev", "startup"],
    ),
    (
        "Legal self-help limit: templates help orientation; high-stakes issues need qualified professionals.",
        ["legal", "ethics"],
    ),
    (
        "Leverage types: labor, capital, code, media — each has different failure modes and ethics.",
        ["business", "strategy"],
    ),
    (
        "Libraries public: free knowledge, quiet space, community programs — underused infrastructure.",
        ["learning", "community"],
    ),
    (
        "Linux basics: package manager, permissions, logs in /var/log; snapshot before major upgrades.",
        ["tech", "dev", "ops"],
    ),
    (
        "Listening levels: internal (planning reply), focused (content), deep (emotion under content).",
        ["communication", "relationships"],
    ),
    (
        "Load shedding personal: drop optional commitments under overload; heroes who never shed burn out.",
        ["productivity", "health"],
    ),
    (
        "Local business: trust and repeat matter more than ads; ops reliability is marketing.",
        ["business", "community"],
    ),
    (
        "Logic fallacies: ad hominem, false dichotomy, strawman, post hoc — name them without smugness.",
        ["thinking", "communication"],
    ),
    (
        "Loneliness response: scheduled contact, shared activity > vague 'hang soon', groups with purpose.",
        ["mental_health", "social"],
    ),
    (
        "Machine learning caution: correlation ≠ causation; data leakage fools demos; humans own decisions.",
        ["tech", "data", "ethics"],
    ),
    (
        "Maintenance culture: schedule the boring; reactive-only shops live in permanent emergency.",
        ["ops", "work", "home"],
    ),
    (
        "Makeup of teams: diversity of thought requires psychological safety or it becomes theater.",
        ["leadership", "team"],
    ),
    (
        "Maps and scale: zoom changes truth; neighborhood detail ≠ national narrative.",
        ["geography", "critical_thinking"],
    ),
    (
        "Marketing ethics: truthful claims, clear pricing, easy cancel — dark patterns tax trust.",
        ["marketing", "ethics", "business"],
    ),
    (
        "Martial arts training: consistency, control, breakfalls; ego sparring increases injury risk.",
        ["exercise", "practice", "safety"],
    ),
    (
        "Mathematics intuition: units check, order of magnitude, edge cases — calculators do not replace sense.",
        ["math", "thinking"],
    ),
    (
        "Meal planning: theme nights, overlapping ingredients, freeze portions; decisions drop with a default menu.",
        ["home", "health", "productivity"],
    ),
    (
        "Measurement pitfalls: goodhart's law — when a measure becomes target, it ceases to be a good measure.",
        ["data", "management"],
    ),
    (
        "Media fasting: 24–48h breaks reset reactivity; notice withdrawal as data.",
        ["attention", "digital", "health"],
    ),
    (
        "Medical literacy: symptoms + timeline + meds list for visits; second opinions on major irreversible choices.",
        ["health", "self_advocacy"],
    ),
    (
        "Meditation practical: attention returns again and again; streaks matter less than returning.",
        ["regulation", "practice"],
    ),
    (
        "Memory techniques: encoding with meaning, spaced recall, teach-back; highlighting alone is weak.",
        ["learning", "memory"],
    ),
    (
        "Mental health care: therapy modalities differ; fit and safety matter; crisis lines when immediate danger.",
        ["mental_health", "care"],
    ),
    (
        "Mentorship: mentee drives agenda; mentor offers pattern recognition not takeover.",
        ["career", "learning"],
    ),
    (
        "Metaphors careful: they illuminate and hide; switch metaphors when stuck in a false frame.",
        ["thinking", "communication"],
    ),
    (
        "Microeconomics personal: opportunity cost, marginal gain, comparative advantage in household tasks.",
        ["economics", "home"],
    ),
    (
        "Migration of systems: dual run, rollback plan, feature flags; big-bang cutovers are bravado.",
        ["ops", "dev"],
    ),
    (
        "Military lessons civilian: after-action reviews, checklists under stress, buddy systems.",
        ["ops", "safety", "team"],
    ),
    (
        "Mindset growth: effort and strategy change ability; fixed labels become self-sealing prophecies.",
        ["psychology", "learning"],
    ),
    (
        "Minimalism useful: fewer decisions, more room; deprivation aesthetics optional.",
        ["home", "productivity"],
    ),
    (
        "Mobility long-term: strength + balance training reduces fall risk as we age.",
        ["exercise", "health", "aging"],
    ),
    (
        "Moderation online: clear rules, consistent enforcement, appeal path; burnout staffing is a risk.",
        ["community", "ops"],
    ),
    (
        "Money scripts: family stories about scarcity/status drive behavior — surface them in couples.",
        ["finance", "relationships", "psychology"],
    ),
    (
        "Motivation wave: act on systems during low motivation; inspiration is unreliable infrastructure.",
        ["habits", "productivity"],
    ),
    (
        "Moving house: admin folder, change addresses list, photo cables before unplugging.",
        ["home", "planning"],
    ),
    (
        "Music listening active: structure, tension/release; attention is a practice not only background.",
        ["music", "attention"],
    ),
    (
        "Mutual aid: reciprocal networks under stress; dignity over savior narratives.",
        ["community", "care"],
    ),
    (
        "Myth of overnight success: visible spikes hide invisible reps; study the lag, not only the launch.",
        ["career", "creative"],
    ),
    (
        "Narrative therapy lite: you are not the problem; the problem is the problem — externalize carefully.",
        ["psychology", "communication"],
    ),
    (
        "Navigation offline: paper backup for critical trips; phones fail in cold and low battery.",
        ["travel", "preparedness"],
    ),
    (
        "Negotiation salary: market data, total comp, practice aloud, comfortable with silence.",
        ["career", "negotiation"],
    ),
    (
        "Neighbor relations: small goodwill deposits, clear boundaries on noise/pets, written agreements for shared costs.",
        ["community", "home"],
    ),
    (
        "Networking human: give first, follow up with value, keep a simple CRM of relationships.",
        ["career", "social"],
    ),
    (
        "Neurodiversity respect: environments can disable or enable; ask preferences, avoid forced eye-contact rules.",
        ["psychology", "work", "inclusion"],
    ),
    (
        "News diet: morning brief limited time, deep dives chosen, doomscroll is not citizenship.",
        ["media", "attention", "civics"],
    ),
    (
        "Nonprofit caution: overhead myths, outcome metrics, governance; passion ≠ effective operations.",
        ["community", "ops"],
    ),
    (
        "Note taking Cornell-ish: cues, notes, summary; review within 24h for retention.",
        ["learning", "pkm"],
    ),
    (
        "Nutrition myths: detox is mostly marketing; liver/kidneys already work; sustainable patterns win.",
        ["nutrition", "health", "critical_thinking"],
    ),
    (
        "Object permanence digital: unread badges train anxiety; batch process and hide counts when possible.",
        ["digital", "attention"],
    ),
    (
        "Observability: logs, metrics, traces — ask questions your future self will need at 3am.",
        ["ops", "dev"],
    ),
    (
        "Occupational safety: PPE, lockout when needed, report near-misses; speed is not worth permanent injury.",
        ["safety", "work"],
    ),
    (
        "Ocean sense: undertows, local flags, never turn back on waves when tired — local knowledge matters.",
        ["safety", "travel"],
    ),
    (
        "Onboarding design: day-one access, buddy, 30-60-90 outcomes; lost hires are process failures.",
        ["leadership", "ops"],
    ),
    (
        "Open office coping: headphones norms, bookable quiet rooms, async defaults for deep work.",
        ["work", "productivity"],
    ),
    (
        "Opera of meetings: standing if short, sitting if deep; end early when done — do not fill time.",
        ["meetings", "work"],
    ),
    (
        "Opinion hygiene: label speculation; update loudly; tribal loyalty is not truth-seeking.",
        ["thinking", "ethics"],
    ),
    (
        "Optical focus: 20-20-20 rule for screens; dry eyes need breaks not only drops.",
        ["health", "work"],
    ),
    (
        "Optimization trap: measuring everything and improving nothing that matters — revisit the goal.",
        ["productivity", "data"],
    ),
    (
        "Oral health: consistent brushing/flossing beats expensive catch-up; pain warrants professional care.",
        ["health", "habits"],
    ),
    (
        "Organization systems: PARA or similar — Projects, Areas, Resources, Archives; finish or archive.",
        ["pkm", "productivity"],
    ),
    (
        "Origami lesson: precise folds compound; rushing early steps ruins late ones — same in engineering.",
        ["practice", "dev", "metaphor"],
    ),
    (
        "Outdoor layering: moisture management, wind shell, extra socks; cotton stays wet and cold.",
        ["travel", "safety"],
    ),
    (
        "Overcommitment cure: default no, wait 24h on new yes, keep a not-now list.",
        ["productivity", "boundaries"],
    ),
    (
        "Ownership product: clear DRI, decision log, escalation path; shared ownership often means none.",
        ["product", "leadership"],
    ),
    (
        "Pain science lite: hurt ≠ always harm; persistent pain needs professional assessment — do not tough out red flags.",
        ["health", "body"],
    ),
    (
        "Painting walls: prep > paint; cut edges first; ventilation and quality tape save days.",
        ["home", "diy"],
    ),
    (
        "Pair programming: navigator + driver roles rotate; ego-free questions; great for knowledge transfer.",
        ["dev", "team"],
    ),
    (
        "Parent self-care: you cannot pour from empty; micro-rests and co-parent or community relief matter.",
        ["parenting", "health"],
    ),
    (
        "Parking lot ideas: capture offline brainstorms without derailing the meeting decision.",
        ["meetings", "facilitation"],
    ),
    (
        "Passwordless direction: prefer passkeys/MFA; SMS weaker than app/hardware keys when available.",
        ["security", "tech"],
    ),
    (
        "Pastoral care secular: presence, practical help, avoid forced meaning-making on someone else's timeline.",
        ["care", "grief"],
    ),
    (
        "Pattern interrupt: change location, temperature, or task modality when rumination loops.",
        ["regulation", "psychology"],
    ),
    (
        "Payroll ethics: pay on time, transparent deductions, no surprise clawbacks without process.",
        ["business", "ethics"],
    ),
    (
        "Peer review science: imperfect but better than viral threads; preprints need extra caution.",
        ["science", "critical_thinking"],
    ),
    (
        "Performance reviews: evidence portfolio year-round; no surprises; growth path concrete.",
        ["leadership", "career"],
    ),
    (
        "Permission vs forgiveness: only where stakes are low and reversible; high-stakes need prior OK.",
        ["ethics", "work", "hitl"],
    ),
    (
        "Personal CRM light: birthday, last contact, how you can help them — not manipulative scripts.",
        ["relationships", "career"],
    ),
    (
        "Pet care baseline: vet, food quality, enrichment, emergency fund for animals.",
        ["home", "care"],
    ),
    (
        "Philosophy practical: examine assumptions, live coherent values, accept tradeoffs without denial.",
        ["philosophy", "values"],
    ),
    (
        "Phone at night: charge outside bedroom if possible; alarm clock separate reduces temptation loops.",
        ["sleep", "digital"],
    ),
    (
        "Photography basics: light first, then composition, then gear; crop is a decision tool.",
        ["art", "creative"],
    ),
    (
        "Physical therapy mindset: consistency with prescribed moves; pain guidelines from the clinician.",
        ["health", "exercise"],
    ),
    (
        "Physics intuition: conservation, friction, leverage — useful metaphors if not overextended.",
        ["science", "thinking"],
    ),
    (
        "Piano practice: hands separate, slow metronome, sections not whole pieces only.",
        ["music", "practice"],
    ),
    (
        "Pilates/core: form over ego weight; breath coordinated; stop with sharp pain.",
        ["exercise", "health"],
    ),
    (
        "Pipeline sales: stages defined, next action always set, no zombie deals.",
        ["business", "sales"],
    ),
    (
        "Pizza dough lesson: time is an ingredient; cold ferment develops flavor.",
        ["cooking", "science"],
    ),
    (
        "Planning fallacy: tasks take longer than hoped; pad critical path, cut scope before cutting sleep.",
        ["planning", "productivity"],
    ),
    (
        "Plant care: match light to species; drainage holes; neglect often kinder than overlove watering.",
        ["home", "gardening"],
    ),
    (
        "Podcast learning: 1.5x only if comprehension holds; notes on one actionable idea per episode.",
        ["learning", "media"],
    ),
    (
        "Poetry reading: sound aloud, sit with ambiguity; not all meaning is propositional.",
        ["art", "attention"],
    ),
    (
        "Police interaction safety: comply for safety, document after, know local rights resources — context varies by region.",
        ["safety", "civics"],
    ),
    (
        "Political conversation: shared facts first, values second, exit when contempt starts.",
        ["communication", "civics"],
    ),
    (
        "Portfolio career: multiple income skills; track taxes; boundaries so everything does not blur.",
        ["career", "finance"],
    ),
    (
        "Posture resets: stand, shoulder blades soft, walk meetings when possible.",
        ["health", "work"],
    ),
    (
        "Power dynamics: who can exit, who can punish, who is heard — name them in hard rooms.",
        ["ethics", "leadership"],
    ),
    (
        "Prayer or reflection: stillness and gratitude practices help many; never force on others.",
        ["values", "regulation"],
    ),
    (
        "Pre-commitments: decide once for defaults (save rate, workout days) to reduce daily friction.",
        ["habits", "decision"],
    ),
    (
        "Pricing: cost, value, willingness to pay; underpricing can signal low quality and burn you out.",
        ["business", "product"],
    ),
    (
        "Privacy defaults: least data, local when possible, read permissions on installs.",
        ["privacy", "security", "levi"],
    ),
    (
        "Probabilistic thinking: ranges not fake precision; update beliefs with Bayes-ish humility.",
        ["thinking", "decision"],
    ),
    (
        "Procrastination types: anxiety avoidance vs novelty chasing — treatments differ (start small vs reduce inputs).",
        ["psychology", "productivity"],
    ),
    (
        "Procurement: define needs before vendors; total cost of ownership; exit clauses.",
        ["business", "ops"],
    ),
    (
        "Product-market fit signals: organic retention, pull not push, willingness to pay, word of mouth.",
        ["product", "startup"],
    ),
    (
        "Professionalism: reliability, clarity, respect under stress — style is secondary.",
        ["work", "career"],
    ),
    (
        "Programming style: consistent, readable names, small functions; cleverness is a liability at 3am.",
        ["dev", "quality"],
    ),
    (
        "Project postmortem: what surprised us, what to automate, what to never repeat.",
        ["ops", "project_management"],
    ),
    (
        "Prompts for self: what am I avoiding; what would make this 10% easier; who benefits from my delay.",
        ["reflection", "productivity"],
    ),
    (
        "Property taxes/insurance: annual review; underinsurance is a silent risk.",
        ["finance", "home"],
    ),
    (
        "Prototyping: fake the backend if needed; learn from real user attempts, not compliments.",
        ["product", "design"],
    ),
    (
        "Public speaking: one message, story + data, practice transitions, pause instead of filler.",
        ["communication", "career"],
    ),
    (
        "Publishing cadence: ship imperfect on schedule; archives teach more than private perfection.",
        ["creative", "writing"],
    ),
    (
        "Pull requests: small diffs, why in description, tests for risk, kind review culture.",
        ["dev", "team"],
    ),
    (
        "Punishment vs natural consequences: teaching works better with connection and clear limits than shame spirals.",
        ["parenting", "psychology"],
    ),
    (
        "Python hygiene: virtual envs, pin deps, type hints where they pay, tests for core paths.",
        ["dev", "python"],
    ),
    (
        "QA mindset: break it on purpose; edge cases; accessibility is part of quality.",
        ["quality", "dev", "ux"],
    ),
    (
        "Quantified self caution: data without change is hoarding; pick few metrics tied to actions.",
        ["health", "data"],
    ),
    (
        "Questions for doctors: diagnosis, alternatives, risks, what if we wait — write them down.",
        ["health", "self_advocacy"],
    ),
    (
        "Queue theory life: overload means wait times explode; WIP limits help humans too.",
        ["systems", "productivity"],
    ),
    (
        "Quiet quitting diagnosis: sometimes boundary; sometimes misaligned role — clarify before moralizing.",
        ["work", "career"],
    ),
    (
        "Quotes use: attribute, context, do not let a line replace thinking.",
        ["ethics", "communication"],
    ),
    (
        "REST vs urgency: true emergencies are rare; most 'ASAP' is preference — negotiate timelines.",
        ["work", "boundaries"],
    ),
    (
        "Reading depth: one hard book slowly beats ten skims; margin notes are thinking.",
        ["learning", "reading"],
    ),
    (
        "Recipes as code: mise en place, read fully, trust timers less than senses as you learn.",
        ["cooking", "practice"],
    ),
    (
        "Reconciliation money: weekly 15 minutes beats monthly panic; categories simple.",
        ["finance", "habits"],
    ),
    (
        "Recovery days: active recovery often better than total inactivity for training plans.",
        ["exercise", "health"],
    ),
    (
        "Recycling right: clean/dry, know local rules; wishcycling contaminates batches.",
        ["environment", "home"],
    ),
    (
        "Red team yourself: how would a critic attack this plan; patch before launch.",
        ["strategy", "thinking"],
    ),
    (
        "References job: only list people warned in advance; specificity helps.",
        ["career"],
    ),
    (
        "Regression testing: automate the bugs you already paid for once.",
        ["dev", "quality"],
    ),
    (
        "Relationship bids: turn toward small attempts at connection; ignored bids accumulate coldness.",
        ["relationships", "psychology"],
    ),
    (
        "Remote work: explicit communication, documented decisions, timezone respect, office optional not culture-free.",
        ["work", "communication"],
    ),
    (
        "Repair culture: fix before replace when skill/time allows; learn one tool at a time.",
        ["home", "sustainability"],
    ),
    (
        "Reputation: built in drops, lost in buckets; public corrections earn long-term trust.",
        ["ethics", "career"],
    ),
    (
        "Research method: question, sources, notes with citations, conclusion separate from wish.",
        ["learning", "science"],
    ),
    (
        "Resilience: flexibility under stress, social support, meaning — not endless toughness performance.",
        ["psychology", "health"],
    ),
    (
        "Respectful disagreement: restate their view until they say 'yes', then differ.",
        ["communication", "conflict"],
    ),
    (
        "Restaurant tipping norms vary by country; when in doubt, check local custom — do not export one culture blindly.",
        ["travel", "ethics"],
    ),
    (
        "Retirement accounts: tax treatment differs; contribution consistency matters early; advice is not one-size.",
        ["finance", "planning"],
    ),
    (
        "Retrospectives: start/stop/continue, vote on actions, assign owners — venting alone is not a retro.",
        ["team", "ops"],
    ),
    (
        "Return policies: photograph items, keep packaging until accepted, note deadlines.",
        ["consumer", "finance"],
    ),
    (
        "Review bombing skepticism: look for patterns and verified purchase signals; herds distort ratings.",
        ["critical_thinking", "consumer"],
    ),
    (
        "Risk communication: absolute vs relative risk; base rates matter; fear sells.",
        ["health", "media", "thinking"],
    ),
    (
        "Rituals: mark transitions (start work, end day); nervous systems like predictable edges.",
        ["habits", "regulation"],
    ),
    (
        "Road trips: sleep, shifts, vehicle check, offline maps; fatigue kills.",
        ["travel", "safety"],
    ),
    (
        "Robotics/automation ethics: who is accountable when automation errs; keep humans on consequential loops.",
        ["ethics", "tech", "hitl"],
    ),
    (
        "Role clarity: RACI or simpler — one accountable person per decision type.",
        ["leadership", "ops"],
    ),
    (
        "Romance pacing: consistency and repair predict better than intensity alone.",
        ["relationships"],
    ),
    (
        "Root cause 5 whys: stop at actionable system cause; avoid endless blame chains.",
        ["problem_solving", "ops"],
    ),
    (
        "Routine for creators: capture → draft → edit → ship → rest; skipping rest collapses quality.",
        ["creative", "habits"],
    ),
    (
        "RSS still works: subscribe to fewer high-signal sources; leave algorithmic feeds for optional time.",
        ["media", "attention"],
    ),
    (
        "Running form: easy pace most days, shoes that fit, build mileage gradually to cut injury risk.",
        ["exercise", "health"],
    ),
    (
        "SaaS evaluation: data export, price trajectory, lock-in, security posture — free tiers can be funnels.",
        ["business", "tech"],
    ),
    (
        "Safety planning mental health: contacts, remove means when possible, professional crisis resources — LEVI is not emergency care.",
        ["mental_health", "safety", "crisis"],
    ),
    (
        "Salary bands: transparency reduces politics; negotiate on value and market, not only need.",
        ["career", "work"],
    ),
    (
        "Salt and hypertension: individual responses vary; medical guidance beats internet absolutes.",
        ["nutrition", "health"],
    ),
    (
        "Same-day shipping culture: speed is a cost somewhere — labor, environment, or quality.",
        ["ethics", "business", "systems"],
    ),
    (
        "Sandbox learning: break things in safe environments; production is for proven changes.",
        ["dev", "learning", "crucible"],
    ),
    (
        "Saying no: brief, clear, optional alternative; over-explaining invites debate.",
        ["boundaries", "communication"],
    ),
    (
        "Scholarship: primary sources, method section honesty, replication value.",
        ["science", "learning"],
    ),
    (
        "Science communication: uncertainty is information; false certainty erodes trust later.",
        ["science", "communication"],
    ),
    (
        "Scope documents: in/out list, success metrics, non-goals — prevent infinite projects.",
        ["project_management", "product"],
    ),
    (
        "Screen time kids: co-view when young, clear limits, offline richness first.",
        ["parenting", "digital"],
    ),
    (
        "Scripting hard talks: opening line, one example, ask, close — practice once aloud.",
        ["communication", "conflict"],
    ),
    (
        "Search literacy: vertical search for papers/laws, date filters, original reporting.",
        ["research", "critical_thinking"],
    ),
    (
        "Seasonal living: plan energy and mood supports in dark months; light and social contact help many.",
        ["health", "planning"],
    ),
    (
        "Secrets management: never commit keys; rotate when people leave; least privilege.",
        ["security", "dev"],
    ),
    (
        "Security theater: visible measures that do not reduce risk; prefer boring effective controls.",
        ["security", "critical_thinking"],
    ),
    (
        "Self-compassion: talk to yourself as a decent coach would; shame rarely produces sustainable change.",
        ["psychology", "mental_health"],
    ),
    (
        "Senior engineer traits: reduce complexity, multiply others, own production pain.",
        ["dev", "career", "leadership"],
    ),
    (
        "Sensory overload: lower inputs, predictable routines, exit plans in loud environments.",
        ["neurodiversity", "regulation"],
    ),
    (
        "Separation of concerns life: work identity ≠ whole self; hobbies that do not monetize still count.",
        ["identity", "health"],
    ),
    (
        "Server basics: backups tested, monitoring, least open ports, update cadence.",
        ["ops", "security"],
    ),
    (
        "Service recovery: apologize, fix, follow up; speed of acknowledgment matters.",
        ["business", "customer"],
    ),
    (
        "Shame vs guilt: guilt targets behavior change; shame attacks worth — shift to specific amends.",
        ["psychology"],
    ),
    (
        "Shareholder vs stakeholder: optimize only for one and systems strain; name your actual objective.",
        ["business", "ethics"],
    ),
    (
        "Shipping culture: define done, small batches, celebrate learning not only launches.",
        ["product", "dev"],
    ),
    (
        "Shoes and body: replace worn trainers; pain on impact deserves attention.",
        ["health", "exercise"],
    ),
    (
        "Shortwave of trends: most pass; adopt tools that fit workflow, not FOMO.",
        ["tech", "productivity"],
    ),
    (
        "Sibling dynamics: family roles stick; adult relationships can renegotiate with explicit talks.",
        ["family", "relationships"],
    ),
    (
        "Signal vs noise: if action would not change, skip the data stream.",
        ["attention", "decision"],
    ),
    (
        "Silo breaking: shared metrics, joint rituals, rotate liaisons — structure beats slogans.",
        ["leadership", "org"],
    ),
    (
        "Simplicity as craft: remove until it breaks, then put back one piece.",
        ["design", "dev", "writing"],
    ),
    (
        "Sleep apnea awareness: snoring + daytime fatigue warrants medical evaluation.",
        ["sleep", "health"],
    ),
    (
        "Small business cash: runway weeks, separate tax money, invoice promptly.",
        ["business", "finance"],
    ),
    (
        "Smart home caution: more devices = more failure points and privacy surface.",
        ["tech", "privacy", "home"],
    ),
    (
        "Social media boundaries: mute liberally, post intentionally, never argue with strangers for sport.",
        ["digital", "mental_health"],
    ),
    (
        "Software licensing: read LICENSE; proprietary and open obligations differ — compliance is not optional.",
        ["legal", "dev"],
    ),
    (
        "Soil health: organic matter, avoid compaction, diversity of plants — ground is a system.",
        ["gardening", "environment"],
    ),
    (
        "Somatic check-in: jaw, shoulders, belly — tension maps unfinished stress.",
        ["regulation", "body"],
    ),
    (
        "Sourcing news: local reporters, document clouds, FOIA where applicable — not only influencers.",
        ["civics", "media"],
    ),
    (
        "Spaced repetition: increasing intervals; Anki-like systems for durable facts.",
        ["learning", "memory"],
    ),
    (
        "Speaking up: prepare one sentence, allies, timing; document if safety issues.",
        ["work", "ethics"],
    ),
    (
        "Speed reading limits: skimming loses structure; use for triage not mastery.",
        ["learning", "reading"],
    ),
    (
        "Spiritual shopping: communities and practices differ; coercion and financial exploitation are red flags.",
        ["values", "ethics"],
    ),
    (
        "Sportsmanship: respect officials and opponents; excellence without contempt.",
        ["ethics", "exercise"],
    ),
    (
        "Spreadsheets: one source of truth, version copies, validate formulas with spot checks.",
        ["ops", "data"],
    ),
    (
        "Stakeholder maps: power/interest grid; communicate differently to each quadrant.",
        ["project_management", "leadership"],
    ),
    (
        "Standards of evidence: anecdote < case series < stronger designs — match claim strength to evidence.",
        ["science", "thinking"],
    ),
    (
        "Startup runway: months of cash at current burn; cut burn before fantasy fundraising.",
        ["startup", "finance"],
    ),
    (
        "Statistics literacy: base rates, selection bias, p-hacking skepticism.",
        ["data", "critical_thinking"],
    ),
    (
        "Status games: awareness reduces capture; choose games worth playing.",
        ["psychology", "career"],
    ),
    (
        "Storage 3-2-1 backups: 3 copies, 2 media, 1 offsite; test restores.",
        ["security", "ops", "data"],
    ),
    (
        "Story structure: desire, obstacle, change; stakes must be felt not only stated.",
        ["writing", "lwp"],
    ),
    (
        "Strength training novices: full body 2-3x/week, learn form, progressive overload slow.",
        ["exercise", "health"],
    ),
    (
        "Stress inoculation: practice hard conversations small; exposure with support beats avoidance spiral.",
        ["psychology", "anxiety"],
    ),
    (
        "Student skills: office hours, spaced study, teach peers; cramming is fragile.",
        ["learning", "education"],
    ),
    (
        "Subscription audit: quarterly cancel; free trials with calendar reminders.",
        ["finance", "digital"],
    ),
    (
        "Substance risk: dependence potential, interactions, local laws — professional help for misuse.",
        ["health", "safety"],
    ),
    (
        "Succession planning: who covers key roles; documentation before departure drama.",
        ["leadership", "ops"],
    ),
    (
        "Sun protection: clothing + shade + appropriate SPF; skin risk is cumulative.",
        ["health"],
    ),
    (
        "Supplier risk: single-source dependency; quality audits for critical inputs.",
        ["business", "ops"],
    ),
    (
        "Support tickets: reproduce steps, environment, expected vs actual — saves cycles.",
        ["ops", "dev", "customer"],
    ),
    (
        "Surgical decisions: risks/benefits/alternatives; recovery time realistic; second opinion for elective major.",
        ["health"],
    ),
    (
        "Surveillance capitalism awareness: free products often price attention; choose tools knowingly.",
        ["privacy", "tech", "ethics"],
    ),
    (
        "Survival hierarchy: safety, health, housing, then optimization hobbies.",
        ["planning", "life"],
    ),
    (
        "Sustainability personal: fewer better things, repair, vote with purchases and policy.",
        ["environment", "consumer"],
    ),
    (
        "Svelte teams: fewer people with clear ownership often outrun large confused groups.",
        ["leadership", "startup"],
    ),
    (
        "Swimming safety: never alone in open water, know local conditions, life jackets when appropriate.",
        ["safety", "exercise"],
    ),
    (
        "System design tradeoffs: consistency, availability, partition tolerance — pick explicitly.",
        ["software", "architecture"],
    ),
    (
        "Table manners cultural: norms differ; observe and ask rather than assume universality.",
        ["social", "travel"],
    ),
    (
        "Tax basics: keep records, estimated payments if required, professionals for complexity.",
        ["finance", "legal"],
    ),
    (
        "Teaching kids money: earn, save, spend, give — small real amounts beat lectures.",
        ["parenting", "finance"],
    ),
    (
        "Team charters: purpose, norms, decision rules, conflict path — write once, revise yearly.",
        ["team", "leadership"],
    ),
    (
        "Technical debt: interest is slowed features and outages; budget repayment explicitly.",
        ["dev", "product"],
    ),
    (
        "Teen autonomy: graduated freedom with safety nets; surveillance without trust backfires.",
        ["parenting"],
    ),
    (
        "Telephone hard talks: still better than ambiguous text for tone-heavy topics.",
        ["communication"],
    ),
    (
        "Temperature risk: heat illness and hypothermia signs; weather is a safety variable.",
        ["safety", "health"],
    ),
    (
        "Temporary work: clarify contract, IP, payment schedule; screenshots of agreements.",
        ["career", "legal"],
    ),
    (
        "Tenant rights vary by place; document conditions; know local housing resources.",
        ["home", "legal", "civics"],
    ),
    (
        "Terminal multiplexers: sessions survive disconnects — useful for long remote jobs.",
        ["dev", "ops"],
    ),
    (
        "Test-driven when it pays: critical logic, regressions; not cargo-cult on every line.",
        ["dev", "quality"],
    ),
    (
        "Thank-you notes: specific, timely; rare enough to still matter.",
        ["social", "career"],
    ),
    (
        "Theater of productivity: busy calendars ≠ outcomes; protect maker time.",
        ["productivity", "work"],
    ),
    (
        "Theory of constraints: find the bottleneck; optimizing non-bottlenecks is theater.",
        ["systems", "ops"],
    ),
    (
        "Therapy shopping: interview therapists, ask approach, switch if unsafe or poor fit.",
        ["mental_health", "care"],
    ),
    (
        "Thermostat diplomacy: household comfort negotiation; data over blame.",
        ["home", "relationships"],
    ),
    (
        "Thinking on paper: messy drafts externalize working memory; clarity comes in revision.",
        ["writing", "thinking"],
    ),
    (
        "Threat modeling: assets, adversaries, entry points, mitigations — scale to context.",
        ["security"],
    ),
    (
        "Time zones: confirm am/pm and zone abbreviations; double-check meeting invites.",
        ["work", "communication"],
    ),
    (
        "Titration of change: small reversible experiments before identity-level swings.",
        ["decision", "psychology"],
    ),
    (
        "Toolchains: prefer stable, documented, replaceable tools; fashion stacks have exit costs.",
        ["dev", "ops"],
    ),
    (
        "Toxic positivity: forced cheer blocks processing; allow full emotional range with care.",
        ["psychology", "communication"],
    ),
    (
        "Trade schools: high-skill paths without degree debt can be excellent — match to local demand.",
        ["career", "education"],
    ),
    (
        "Traffic safety: eyes up, phone down, space cushion; motorcycles need visibility strategy.",
        ["safety"],
    ),
    (
        "Training data ethics: consent, bias, downstream harm — relevant beyond AI labs.",
        ["ethics", "tech"],
    ),
    (
        "Translation caution: idioms and legal terms fail machine translation; human review for stakes.",
        ["language", "communication"],
    ),
    (
        "Trauma informed: safety, choice, collaboration; avoid forcing disclosure.",
        ["care", "psychology"],
    ),
    (
        "Travel documents: copies digital+paper, embassy info, medication in carry-on.",
        ["travel", "preparedness"],
    ),
    (
        "Trust but verify: especially money, access, and irreversible deploys.",
        ["security", "ops", "hitl"],
    ),
    (
        "Truth serum myth: honesty is practiced under low threat; fear produces compliance theater.",
        ["psychology", "ethics"],
    ),
    (
        "Turntaking conversation: leave space; interrupt patterns differ by culture — check impact.",
        ["communication", "inclusion"],
    ),
    (
        "Tutorial hell: build a small personal project to escape passive watching.",
        ["learning", "dev"],
    ),
    (
        "Two-minute rule: if under two minutes, do it now — clears grit from the gears.",
        ["productivity"],
    ),
    (
        "Typography readable: line length, contrast, hierarchy; design is access.",
        ["design", "ux"],
    ),
    (
        "UIs for stress: big targets, undo, plain language errors — design for bad days.",
        ["ux", "design"],
    ),
    (
        "Ultimatums: last resort; mean them; prefer negotiable requests first.",
        ["relationships", "communication"],
    ),
    (
        "Uncertainty budgets: reserve time/money for unknown unknowns on real projects.",
        ["planning", "risk"],
    ),
    (
        "Underwriting life: emergency fund, insurance gaps, single points of failure in income.",
        ["finance", "planning"],
    ),
    (
        "Unicode/email: stick to boring characters in critical identifiers; clever symbols break systems.",
        ["dev", "ops"],
    ),
    (
        "Union basics: collective bargaining power; know local labor rules before assuming.",
        ["work", "civics"],
    ),
    (
        "Unit economics: contribution margin after variable costs; growth of losses is not a strategy.",
        ["business", "finance"],
    ),
    (
        "Universal design: curb cuts help more than the original target — accessibility lifts many.",
        ["design", "inclusion"],
    ),
    (
        "Unix philosophy: small tools compose; text interfaces age better than fashion GUIs.",
        ["dev", "tech"],
    ),
    (
        "Unplug weekends: partial better than never; plan offline anchors in advance.",
        ["digital", "health"],
    ),
    (
        "Upgrades software: changelog, backup, stage first; never on Friday without need.",
        ["ops", "dev"],
    ),
    (
        "Urban walking safety: awareness without paranoia; share ETAs at night when helpful.",
        ["safety", "travel"],
    ),
    (
        "Usability testing: five users find many issues; watch behavior, not only opinions.",
        ["ux", "product"],
    ),
    (
        "Utility shutoffs: know provider contacts and medical priority registers if applicable.",
        ["home", "preparedness"],
    ),
    (
        "Vacation real: out-of-office with backup human; recover before return sprint.",
        ["work", "health"],
    ),
    (
        "Vaccines: follow qualified public health and clinician guidance; misinformation spreads fast.",
        ["health", "science"],
    ),
    (
        "Value pricing: price the outcome when ethical and clear; hourly can hide inefficiency.",
        ["business"],
    ),
    (
        "Vendor lock-in: export tests yearly; multi-cloud theater is not the only exit strategy.",
        ["tech", "business"],
    ),
    (
        "Version your life docs: dates on resumes, policies, estate papers after major changes.",
        ["planning", "ops"],
    ),
    (
        "Veterinary triage: know emergency clinics; poisoning and bloat are time-critical.",
        ["pets", "safety"],
    ),
    (
        "Video calls: mute discipline, lighting on face, agenda in chat.",
        ["work", "communication"],
    ),
    (
        "Violence risk: leave plans, hotlines, trusted network — professional resources over AI advice.",
        ["safety", "crisis"],
    ),
    (
        "Virtual private networks: useful on untrusted networks; not magic anonymity.",
        ["security", "privacy"],
    ),
    (
        "Vision boards critique: images without weekly actions are decoration; pair with MITs.",
        ["goals", "productivity"],
    ),
    (
        "Vital signs awareness: know your baseline; sudden severe changes need urgent care.",
        ["health"],
    ),
    (
        "Vocabulary growth: read slightly hard texts; use new words in writing same week.",
        ["learning", "language"],
    ),
    (
        "Voice care: hydration, amplification not shouting, rest when hoarse.",
        ["health", "communication"],
    ),
    (
        "Volunteer wisely: match skills, bounded hours, avoid savior burnout.",
        ["community", "care"],
    ),
    (
        "Voting logistics: registration deadlines, ID rules, plan time off if needed.",
        ["civics"],
    ),
    (
        "Vulnerability disclosure: responsible reporting paths; do not dump exploits publicly without process.",
        ["security", "ethics"],
    ),
    (
        "Wages and dignity: timely pay is moral baseline; delayed pay is a crisis for workers.",
        ["ethics", "business"],
    ),
    (
        "Walking meetings: good for status, bad for detailed diagrams — match medium to content.",
        ["work", "health"],
    ),
    (
        "Wardrobe functional: few versatile pieces, repair, fit over logo.",
        ["home", "finance"],
    ),
    (
        "Water filter sense: know what your municipal report already covers; match filter to actual contaminants.",
        ["home", "health"],
    ),
    (
        "Wealth displays: social comparison is infinite; define enough.",
        ["psychology", "finance"],
    ),
    (
        "Weather radio: offline alerts matter when networks fail.",
        ["preparedness", "safety"],
    ),
    (
        "Web accessibility: semantic HTML, keyboard paths, alt text — legal and moral in many contexts.",
        ["ux", "dev", "inclusion"],
    ),
    (
        "Weight training safety: collars, spotters on heavy bars, controlled range.",
        ["exercise", "safety"],
    ),
    (
        "Whistleblowing: document, know legal protections, counsel when stakes high.",
        ["ethics", "work", "legal"],
    ),
    (
        "Wi-Fi hygiene: strong router password, separate guest net, update firmware.",
        ["security", "home"],
    ),
    (
        "Wikipedia use: start here, verify citations, edit responsibly if correcting.",
        ["research", "learning"],
    ),
    (
        "Wildfire/smoke: air quality, N95 when appropriate, go-bag if in risk zones.",
        ["safety", "preparedness"],
    ),
    (
        "Willpower finite: design defaults so you need less heroism.",
        ["habits", "psychology"],
    ),
    (
        "Windows/doors security: lighting, locks, not hiding keys in fake rocks.",
        ["safety", "home"],
    ),
    (
        "Winter driving: clear all snow, greater following distance, survival kit in trunk.",
        ["safety", "travel"],
    ),
    (
        "Wisdom teeth/dental plans: cost and recovery planning; infection is urgent.",
        ["health"],
    ),
    (
        "Witnessing pain: sit with, fetch water, avoid fixing speeches.",
        ["care", "relationships"],
    ),
    (
        "Work-from-cafe: bag physical security, VPN, limited sensitive work in public.",
        ["security", "work"],
    ),
    (
        "Workout logs: load, reps, sleep note — progress is evidence not mood.",
        ["exercise", "data"],
    ),
    (
        "Writing deadlines: external accountability helps; private perfectionism stalls.",
        ["writing", "productivity"],
    ),
    (
        "Wrongful assumptions: check, then check again on money, meds, and identity.",
        ["ops", "safety"],
    ),
    (
        "Xenophobia check: curiosity and individual evidence over group stereotypes.",
        ["ethics", "critical_thinking"],
    ),
    (
        "Yoga caution: avoid forcing range; breath not competitive; modify liberally.",
        ["exercise", "health"],
    ),
    (
        "Youth sports: fun and development first; watch for adult ego projection.",
        ["parenting", "exercise"],
    ),
    (
        "Zero trust mindset: verify access continuously; lateral movement is the real breach path.",
        ["security"],
    ),
    (
        "Zoning/local rules: home businesses and builds often regulated — check before investing.",
        ["home", "civics", "legal"],
    ),
    (
        "Zoom fatigue: cameras optional norms, breaks between, async video when possible.",
        ["work", "health"],
    ),
    (
        "LEVI reminder: offline brain is principles not personal medical/legal advice; escalate real-world professionals when stakes are high.",
        ["levi", "ethics", "safety"],
    ),
]


ATLAS = list(ATLAS) + list(NEURO_ATLAS) + list(NEURO_MORE) + list(NEURO_PACK3)


def seed_units() -> List[Tuple[str, List[str]]]:
    return list(ATLAS)


def seed_corpus(clear_existing_seed: bool = False) -> str:
    """Write atlas into local corpus. Idempotent-ish via source tag."""
    from levi.brain.corpus import Corpus

    c = Corpus()
    n = 0
    for text, tags in ATLAS:
        c.add(
            text,
            kind="INFERENCE",
            source="seed_atlas",
            tags=list(tags) + ["atlas", "offline_brain"],
        )
        n += 1
    return f"Seeded {n} atlas units into corpus (source=seed_atlas). Retrieve with brain/corpus search."


def format_atlas_index() -> str:
    letters = {}
    for _text, tags in ATLAS:
        key = (tags[0] if tags else "?")[0].upper()
        letters.setdefault(key, 0)
        letters[key] += 1
    lines = [
        "=== Offline Brain Atlas ===",
        f"Units: {len(ATLAS)}  across subject tags A–Z+",
        "",
        "Sample domains: finance, health, systems, LEVI core logic, security,",
        "relationships, learning, business ethics, L.W.P. story, crisis care.",
        "",
        f"Tag starts density: {dict(sorted(letters.items()))}",
        "",
        "Load: python -m levi.cli.main brain --seed-atlas",
        "Not medical/legal advice — operational principles for local SI.",
    ]
    return "\n".join(lines)
