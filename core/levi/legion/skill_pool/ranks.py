"""Rank ladders for the shared Legion skill pool.

Every skill carries a depth ladder: sub-ranks (simpler applications
below) and upper ranks (advanced mastery above). Rung semantics:

- ``I``   — foundational: the basic application, one straightforward
  use, minimal setup.
- ``II``  — practiced: routine professional use, multi-step work,
  judgment calls within the skill's normal scope.
- ``III`` — expert: edge cases, adversarial or complex conditions, the
  skill's full depth — honest limits intact (a rung III never becomes
  legal advice, therapy, a CPA, or a trading desk).

RANKS ARE PROVISIONAL: the ``I / II / III`` names await Chauncey's word.

Data-driven like everything else here: ``SKILL_RANKS`` maps skill id ->
(3 rungs, ordered I, II, III). ``pool.py`` merges the ladder into each
skill dict at load and FAILS LOUDLY when a skill has no ladder —
invariant: every skill has a complete ordered ladder.
"""

from __future__ import annotations

from typing import Dict, Tuple

# Provisional rank names (Chauncey's word pending). Neutral ordinals so
# no skill domain gets a fancier ladder vocabulary than another.
RANKS = ("I", "II", "III")

# skill id -> (rung I, rung II, rung III). One line each, no filler:
# every rung must say something true about that skill's depth.
SKILL_RANKS: Dict[str, Tuple[str, str, str]] = {
    # ------------------------------------------------------------------
    # comms
    # ------------------------------------------------------------------
    "legion_gmail": (
        "Reads the inbox and searches threads by plain keywords; finds a specific message or conversation.",
        "Drafts, replies, and forwards with correct tone; organizes mail with labels across threads.",
        "Runs full inbox workflows — triage, follow-up tracking, and thread surgery across dozens of messages without losing the plot.",
    ),
    "legion_instagram": (
        "Reads a profile, post, or reel and summarizes what is actually in it.",
        "Pulls comments, insights, and audience context; manages a publishing queue.",
        "Runs the whole account surface — content calendar, engagement patterns, and insight-driven posting decisions.",
    ),
    "legion_threads": (
        "Reads a post or feed and reports what people are saying.",
        "Tracks threads, replies, and social-graph context around a topic.",
        "Manages presence — publishing cadence, audience reading, and insight-backed posting strategy.",
    ),
    "legion_facebook_cli": (
        "Reads a post, profile, or group thread from a URL.",
        "Searches timelines, groups, events, and Marketplace listings with filters.",
        "Manages listings end to end — creation, edits, inquiry threads, and marketplace hygiene.",
    ),
    "legion_messenger_read": (
        "Reads and summarizes a single conversation thread.",
        "Searches across conversations and contacts; tracks a Marketplace thread.",
        "Maintains ongoing threads — context, follow-ups, and message history across many conversations.",
    ),
    "legion_google_calendar": (
        "Reads the agenda — what is on today and tomorrow.",
        "Finds event details, checks availability, and proposes meeting slots.",
        "Manages the calendar — scheduling changes, conflict resolution, and recurring-event surgery.",
    ),
    # ------------------------------------------------------------------
    # media
    # ------------------------------------------------------------------
    "legion_generate_podcast": (
        "Turns a short text into a single-voice spoken MP3.",
        "Composes a full episode — structure, segments, multi-voice delivery.",
        "Produces a series-ready episode: scripting, pacing, voice direction, finished audio.",
    ),
    "legion_podcast_generator": (
        "Turns one topic into a scripted segment with produced audio.",
        "Builds a full produced episode — script, voices, ElevenLabs production.",
        "Runs the production pipeline — format, segments, voice casting, consistent show identity.",
    ),
    "legion_podcast_marketing": (
        "Turns one episode into a show-notes page and a few social posts.",
        "Builds the full distribution kit — clips, quote cards, notes, per-platform posts.",
        "Runs the episode launch — sequencing, repurposing strategy, and what to measure.",
    ),
    "legion_tts": (
        "Reads a short text aloud verbatim in a single voice.",
        "Voices a long document with consistent pacing and multi-speaker parts.",
        "Directs the read — emphasis, pacing, and speaker separation for complex texts.",
    ),
    "legion_image_search": (
        "Finds a usable image for a single query with its source page.",
        "Gathers a set of on-brief images with verified sources for a feed or artifact.",
        "Art-directs the search — licensing-safe picks and visual consistency across a whole project.",
    ),
    "legion_photo_editor": (
        "Resizes, crops, or reformats a single image.",
        "Retouches — backgrounds, watermarks, filters, and batch processing.",
        "Finishes images to spec — color, composition fixes, and batch pipelines for whole sets.",
    ),
    "legion_video_editing": (
        "Trims a clip or joins two videos into one.",
        "Edits a full video — cuts, subtitles, voiceover, reformatting.",
        "Finishes to publish — pacing, effects, audio mix, and platform-specific exports.",
    ),
    "legion_storyboard": (
        "Sketches a shot list for a simple video.",
        "Plans the full video — script, shots, and a filming guide for social.",
        "Directs pre-production — coverage, contingencies, and a shoot plan that survives reality.",
    ),
    "legion_ad_creative": (
        "Drafts one static ad concept for a single placement.",
        "Designs a set of creatives across placements with consistent messaging.",
        "Runs the creative campaign — variants, hooks, and iteration against response.",
    ),
    "legion_infographic_builder": (
        "Turns one dataset or process into a clean visual.",
        "Builds comparison and timeline infographics that actually read.",
        "Designs the visual argument — narrative flow, data honesty, and shareability.",
    ),
    "legion_recreate_screenshot": (
        "Rebuilds a simple screen from a reference image.",
        "Recreates a complex UI with accurate layout and components.",
        "Pixel-perfect reconstruction — spacing, typography, and edge cases across states.",
    ),
    "legion_content_machine": (
        "Drafts a few posts for one channel from one topic.",
        "Builds a content batch — posts, newsletter, per-platform adaptations.",
        "Runs the content engine — calendar, voice consistency, and repurposing across channels.",
    ),
    # ------------------------------------------------------------------
    # business
    # ------------------------------------------------------------------
    "legion_ai_recruiter": (
        "Writes a clear job description from a rough role sketch.",
        "Screens CVs against the role and ranks candidates with reasons.",
        "Runs the pipeline — sourcing strategy, structured evaluation, and hiring decisions with a paper trail.",
    ),
    "legion_ai_sdr": (
        "Defines an ideal customer profile from a product description.",
        "Builds and qualifies a lead list against the ICP.",
        "Runs the outbound motion — sequencing, objection handling, negotiation, and pipeline discipline.",
    ),
    "legion_ai_secretary": (
        "Drafts a single email or preps one meeting agenda.",
        "Runs the day — correspondence, scheduling, and meeting prep as a system.",
        "Runs the office — inbox triage, calendar defense, and priority calls under load.",
    ),
    "legion_business_builder": (
        "Turns a raw idea into a one-page business sketch.",
        "Builds the full plan — offer, market, pricing, operations.",
        "Stress-tests the business — unit economics, failure modes, and the first 90 days.",
    ),
    "legion_competitive_analysis": (
        "Maps the obvious competitors for a product.",
        "Builds the comparison — features, pricing, positioning, and strategic recommendations.",
        "Reads the market — moats, weak spots, and where the opening actually is.",
    ),
    "legion_product_manager": (
        "Writes a tight product brief or a set of user stories.",
        "Builds the PRD and roadmap with prioritization frameworks.",
        "Owns the product — trade-offs, scope cuts, and roadmap under real constraints.",
    ),
    "legion_programmatic_seo": (
        "Designs the page template for one content type.",
        "Builds the programmatic system — data, templates, and pages at scale.",
        "Runs it as a channel — crawl budget, quality control, and ranking across thousands of pages.",
    ),
    "legion_geo": (
        "Rewrites one page to surface in AI answers.",
        "Optimizes a content set for ChatGPT, Perplexity, and AI Overviews.",
        "Owns AI-search presence — monitoring, iteration, and defense against answer-engine shifts.",
    ),
    "legion_seo_auditor": (
        "Runs a basic SEO health check on one page.",
        "Audits the full site — technical, content, and authority issues with fixes.",
        "Turns the audit into a program — prioritized, sequenced, and measured.",
    ),
    "legion_invoice_generator": (
        "Generates a clean invoice for one job.",
        "Builds branded invoice templates with line items, tax, and terms.",
        "Runs billing — recurring invoices, late-payment handling, and records.",
    ),
    "legion_legal_contract": (
        "Explains one contract clause in plain language.",
        "Drafts or reviews standard documents — NDAs, service agreements — flagging what matters.",
        "Handles the hard parts — negotiation leverage points, redlines, and knowing when a real lawyer is required. Never legal advice.",
    ),
    "legion_supplier_research": (
        "Finds a shortlist of suppliers for one need.",
        "Evaluates and compares vendors — quotes, terms, reliability.",
        "Runs procurement — negotiation, risk, and a supplier bench for when one fails.",
    ),
    "legion_stock_analyzer": (
        "Pulls the key numbers on one stock.",
        "Runs full fundamental and technical analysis with a written report.",
        "Builds the investment case — thesis, risks, valuation ranges. Analysis only, never trading execution.",
    ),
    "legion_insurance_optimizer": (
        "Reviews one policy for obvious gaps or overpayment.",
        "Compares coverage across policies and finds the savings.",
        "Optimizes the whole insurance picture — coverage, deductibles, and renewal strategy. Not an agent.",
    ),
    "legion_tax_reviewer": (
        "Scans a return for missed obvious deductions.",
        "Reviews the full return and plans next year's tax moves.",
        "Builds the tax strategy — entity, timing, and liability reduction within the law. Not a CPA.",
    ),
    "legion_real_estate_analyzer": (
        "Runs the numbers on one property — payment, yield, basics.",
        "Analyzes the investment — returns, mortgage options, rent-vs-buy.",
        "Underwrites like an investor — comps, risk, exit scenarios, and the deal-breakers.",
    ),
    "legion_branding_generator": (
        "Names the thing and picks a direction.",
        "Builds the identity kit — logo, palette, typography, style guide.",
        "Launches the brand — voice, applications, and consistency across every touchpoint.",
    ),
    "legion_excel_generator": (
        "Builds a simple spreadsheet with clean formulas.",
        "Builds real workbooks — charts, pivots, and financial models.",
        "Engineers the model — auditable formulas, scenarios, and error-proofing.",
    ),
    # ------------------------------------------------------------------
    # shopping-travel
    # ------------------------------------------------------------------
    "legion_shopping": (
        "Finds a product with real prices and links.",
        "Compares options across sellers with honest trade-offs.",
        "Shops like an analyst — total cost, reliability, and the catch behind the deal.",
    ),
    "legion_personal_shopper": (
        "Researches one purchase and gives a recommendation.",
        "Compares the field — options, deals, and what validates the buy.",
        "Owns the decision — timing, negotiation, and buyer's-remorse prevention.",
    ),
    "legion_flightaware": (
        "Answers when a specific flight departs or arrives.",
        "Tracks status, delays, and cancellations with context.",
        "Monitors the trip — connections, rebooking options, and what to do when it goes wrong.",
    ),
    "legion_travel_assistant": (
        "Sketches a trip — where, when, rough budget.",
        "Builds the full itinerary — flights, hotels, days, costs.",
        "Plans like a pro — contingencies, booking strategy, and the trip that survives contact with reality.",
    ),
    # ------------------------------------------------------------------
    # health
    # ------------------------------------------------------------------
    "legion_apple_healthkit": (
        "Reads today's numbers — steps, sleep, heart rate.",
        "Reviews trends across weeks — activity, sleep, workouts.",
        "Correlates the data — what the patterns actually say, and what they do not prove.",
    ),
    "legion_google_health_connect": (
        "Reads today's numbers from the Android device.",
        "Reviews trends — sleep stages, workouts, daily metrics.",
        "Correlates the data — patterns and the honest limits of what it proves.",
    ),
    "legion_meal_planner": (
        "Plans a few days of meals with a shopping list.",
        "Builds the week — macros, prep guide, and grocery list.",
        "Runs the kitchen system — rotation, batch prep, and nutrition targets that hold.",
    ),
    "legion_recipe_creator": (
        "Writes a recipe from a craving or a dish name.",
        "Builds from what is on hand — ingredients in, dinner out.",
        "Adapts like a cook — substitutions, scaling, and dietary constraints without losing the dish.",
    ),
    # ------------------------------------------------------------------
    # files-device
    # ------------------------------------------------------------------
    "legion_media_library": (
        "Finds one photo by description.",
        "Searches the library across albums and device galleries.",
        "Curates — sets, timelines, and the right photo for the moment.",
    ),
    "legion_phone_files": (
        "Finds a file on the phone by name.",
        "Searches downloads and folders by type, date, or captured text.",
        "Excavates — the buried file, the duplicate mess, the full inventory.",
    ),
    "legion_file_converter": (
        "Converts one file to another format.",
        "Merges, splits, and compresses across formats.",
        "Runs the pipeline — batch conversions, quality control, and format surgery.",
    ),
    # ------------------------------------------------------------------
    # dev
    # ------------------------------------------------------------------
    "legion_github_solution_finder": (
        "Finds whether a library exists for the problem.",
        "Compares candidate libraries — maturity, maintenance, fit.",
        "Vets like an engineer — source reading, issue archaeology, and the real cost of adoption.",
    ),
    "legion_migrate_to_multi_artifact": (
        "Assesses whether the project needs a second artifact.",
        "Plans the migration — structure, shared code, boundaries.",
        "Executes the split — clean seams, no duplication, everything still builds.",
    ),
    "legion_replit_migration_guardrails": (
        "Maps one project's stack to Replit's equivalents.",
        "Runs the migration with guardrails — auth, DB, secrets done right.",
        "Hardens the landing — production config, edge cases, and what Replit cannot do.",
    ),
    "legion_website_cloning": (
        "Rebuilds a simple page as an app.",
        "Clones a full site — pages, components, interactions.",
        "Rebuilds to production — pixel fidelity, responsive behavior, and clean code.",
    ),
    # ------------------------------------------------------------------
    # learning
    # ------------------------------------------------------------------
    "legion_deep_research": (
        "Researches one question with solid sources.",
        "Runs the full investigation — multi-source, scored, structured report.",
        "Researches like an analyst — source triangulation, bias checks, and what remains unknown.",
    ),
    "legion_design_thinker": (
        "Runs one design-thinking exercise on an idea.",
        "Validates the idea — audience, problem, prioritized directions.",
        "Facilitates the full process — divergence, convergence, and killing darlings with evidence.",
    ),
    "legion_flashcard_generator": (
        "Turns notes into a simple card set.",
        "Builds study guides and quizzes with spaced-repetition structure.",
        "Designs the study system — what to drill, what to drop, and exam-day readiness.",
    ),
    "legion_interview_prep": (
        "Drills common questions with feedback.",
        "Runs mock interviews — behavioral and case — with scorecards.",
        "Prepares like a coach — stories, strategy, and reading the room.",
    ),
    "legion_resume_maker": (
        "Builds a clean resume from work history.",
        "Tailors the resume to a specific role with ATS-safe formatting.",
        "Positions the candidate — narrative, gaps handled, and the resume as argument.",
    ),
    # ------------------------------------------------------------------
    # meta
    # ------------------------------------------------------------------
    "legion_skill_creator": (
        "Captures one repeated workflow as a saved skill.",
        "Designs the skill — triggers, instructions, and edge cases.",
        "Builds the skill system — composable skills that combine into bigger ones.",
    ),
    "legion_skill_finder": (
        "Points to the right skill for a clear task.",
        "Matches fuzzy goals to capabilities across the whole pool.",
        "Reads intent — what the user actually needs versus what they asked for.",
    ),
    "legion_goals": (
        "Records a goal with a timeframe.",
        "Tracks progress, setbacks, and course corrections.",
        "Coaches the pursuit — milestones, accountability, and honest reassessment.",
    ),
    "legion_forget": (
        "Removes one fact on an explicit request.",
        "Purges a topic across memory and stops automations from reviving it.",
        "Verifies the forgetting — nothing lingers, nothing resurrects.",
    ),
    "legion_subscription_status": (
        "Reports the current plan and usage.",
        "Explains billing, credits, and upgrade options.",
        "Audits the account — what is paid for versus what is actually used.",
    ),
    "legion_muse_feedback": (
        "Files one piece of feedback cleanly.",
        "Writes the feedback that gets read — reproduction, impact, ask.",
        "Builds the case — patterns across failures and the feature request that lands.",
    ),
    "legion_muse_early_access": (
        "Answers what the early-access program is.",
        "Handles join, status check, or withdrawal.",
        "Advises the play — whether early access is worth it for this user.",
    ),
    "legion_pattern_bridge": (
        "Spots one surface similarity between two domains and names it.",
        "Maps the structure across — what corresponds to what, and where the mapping holds.",
        "Tests the bridge — predictions, false friends, and knowing when the analogy breaks.",
    ),
    "legion_action_react": (
        "Reads the room and answers a single slight with a calibrated sideways line.",
        "Handles ongoing friction — bureaucratic loops and stupid systems — with sustained deniable pressure.",
        "Conducts the campaign — every response lands, nothing is provable, the system corrects itself.",
    ),
    # ------------------------------------------------------------------
    # money-music
    # ------------------------------------------------------------------
    "legion_plaid": (
        "Reads balances across linked accounts.",
        "Reviews transactions and recurring charges.",
        "Audits the money — cash flow, liabilities, and where it is leaking. Read-only, always.",
    ),
    "legion_spotify": (
        "Finds music or builds a quick playlist.",
        "Manages the library — playlists, podcasts, discovery.",
        "Curates like a DJ — taste, sequencing, and the playlist for the moment.",
    ),
    # ------------------------------------------------------------------
    # law
    # ------------------------------------------------------------------
    "legion_legal_research": (
        "Finds what the law says on one clear question with proper sources.",
        "Researches with discipline — jurisdiction, citator checks, holding versus dicta.",
        "Builds the research memo — the full trail, the weak spots, and what a lawyer would still verify. Never legal advice.",
    ),
    "legion_compliance_checklist": (
        "Lists the obligations for one regulation.",
        "Builds and runs the checklist — evidence mapping, gap scoring.",
        "Runs the compliance program — remediation order, proof, and audit readiness. Not a lawyer.",
    ),
    "legion_terms_breakdown": (
        "Flags the hostile clauses in one agreement.",
        "Tears it down clause by clause in plain language with risk ranking.",
        "Reads the trap architecture — how the clauses work together and what is really being signed. Not legal advice.",
    ),
    "legion_dispute_prep": (
        "Organizes the facts into a clean chronology.",
        "Builds the case file — evidence inventory, claims mapping.",
        "Preps for the fight — strategy, leverage, and the questions for a real lawyer. Never argues the case.",
    ),
    # ------------------------------------------------------------------
    # document-creation
    # ------------------------------------------------------------------
    "legion_doc_design": (
        "Cleans up one document's formatting.",
        "Designs the full structure — hierarchy, styles, templates.",
        "Builds the document system — templates and standards for everything the org produces.",
    ),
    "legion_report_builder": (
        "Turns findings into a readable report.",
        "Builds the formal report — executive summary, evidence, citations.",
        "Writes the report that moves decisions — narrative, proof, and the appendix that ends arguments.",
    ),
    "legion_proposal_draft": (
        "Drafts a simple proposal for one ask.",
        "Builds the full pitch — problem, approach, scope, terms.",
        "Writes the proposal that wins — positioning, pricing framing, and the close.",
    ),
    # ------------------------------------------------------------------
    # therapeutic
    # ------------------------------------------------------------------
    "legion_mindfulness_practice": (
        "Guides one breathing exercise for the moment.",
        "Builds a practice — breathing, grounding, body scans as routine.",
        "Teaches the full toolkit and when to use which — always within wellness, never therapy.",
    ),
    "legion_thought_reframing": (
        "Catches and reframes one unhelpful thought.",
        "Works the pattern — evidence checks across recurring thoughts.",
        "Teaches the method deeply — and knows exactly where it stops: not therapy, professional for the rest.",
    ),
    "legion_guided_journaling": (
        "Gives prompts for today's entry.",
        "Builds the journaling practice — morning pages, reviews, decision logs.",
        "Uses the journal as instrument — patterns, decisions, and self-knowledge over time. Writing practice, never therapy.",
    ),
    # ------------------------------------------------------------------
    # life-balance
    # ------------------------------------------------------------------
    "legion_time_boundaries": (
        "Blocks tomorrow's calendar with intent.",
        "Builds the boundary system — time-blocking, saying-no scripts, protected hours.",
        "Defends the life — meeting triage, workload negotiation, and boundaries that hold under pressure.",
    ),
    "legion_burnout_gauge": (
        "Names the burnout signals being shown.",
        "Triages the workload — cut, delegate, defer, rest.",
        "Runs the recovery — the full protocol and the structural changes so it does not recur. Not therapy.",
    ),
    "legion_habit_design": (
        "Designs one tiny habit that sticks.",
        "Builds the stack — environment design and implementation intentions.",
        "Engineers the routine — systems that survive bad weeks and streak repair without shame.",
    ),
}
