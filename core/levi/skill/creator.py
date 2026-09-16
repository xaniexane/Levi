"""``levi skill create`` — natural-language skill scaffolder.

Turns a plain-language description into a LEVI skill scaffold:

* ``~/.levi/skills/<id>/SKILL.md``     — skill file with YAML frontmatter
  (name, description, version, category, risk) + Purpose / Workflow /
  Output Contract / Operating Rules body, per the skill-file conventions.
* ``~/.levi/skills/<id>/handler.py``   — executable handler *stub* (fill in).
* ``~/.levi/skills/<id>/test_<id>.py`` — smoke-test stub.

Safety contract (preview → explicit confirm → install):

* The scaffold is always PREVIEWED first. Nothing is written until the user
  either passes ``--confirm`` or types ``yes`` at the prompt.
* Descriptions asking for credential handling, exfiltration, or
  offensive-security behavior are REFUSED with a clear reason
  (defensive-only rule) — no files, no registration.
* Category and risk are *keyword-heuristic guesses*, honestly labeled as
  such in the plan, the preview, and the generated SKILL.md. Heuristic risk
  never exceeds MODERATE; escalate manually if the real skill needs more.

Registered user skills (frontmatter in ``~/.levi/skills/*/SKILL.md``) are
loaded by :class:`levi.skill.registry.SkillRegistry` with the
``user-created`` tag, so ``levi skill list`` / ``levi skills`` show them and
the agent's ``skill_load`` tool can serve their playbooks. The generated
``handler.py`` is deliberately NOT auto-executed by the registry: wiring a
stub into execution is a human-reviewed step.

stdlib-only.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from levi.skill.registry import Skill, SkillRisk


# ── Paths ─────────────────────────────────────────────────────────────


def skills_dir() -> Path:
    """User skill root. ``LEVI_SKILLS_DIR`` overrides; default
    ``~/.levi/skills`` (same grain as the agent runtime's skills dir)."""
    override = os.environ.get("LEVI_SKILLS_DIR")
    if override:
        return Path(override)
    return Path.home() / ".levi" / "skills"


# ── Slug / name derivation ────────────────────────────────────────────

_SLUG_MAX = 48


def slugify(text: str) -> str:
    """Turn free text into a filesystem/registry-safe skill id."""
    ascii_text = (
        unicodedata.normalize("NFKD", text or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        return "unnamed-skill"
    return slug[:_SLUG_MAX].rstrip("-") or "unnamed-skill"


_LEAD_INS = re.compile(
    r"^(?:a|an|the)\s+skill\s+(?:that|to|which)\s+|"
    r"^skill\s+(?:that|to|which)\s+|"
    r"^(?:please\s+)?(?:create|make|build)\s+(?:me\s+)?(?:a\s+|an\s+)?"
    r"(?:skill\s+(?:that|to|which)\s+)?",
    re.IGNORECASE,
)


def derive_name(description: str) -> str:
    """Heuristic human-readable name from the description."""
    text = _LEAD_INS.sub("", (description or "").strip())
    text = re.split(r"[.!?\n]", text, maxsplit=1)[0].strip()
    words = text.split()
    if not words:
        return "Unnamed Skill"
    name = " ".join(words[:6])
    return name[0].upper() + name[1:] if name else "Unnamed Skill"


# ── Safety gate (defensive-only) ───────────────────────────────────────

# (compiled regex, concern label, user-facing reason)
_UNSAFE_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    (
        re.compile(
            r"\b(?:api[-_ ]?keys?|secrets?|passwords?|credentials?|auth[-_ ]?tokens?|"
            r"oauth|private[-_ ]?keys?|bearer[-_ ]?tokens?|2fa|mfa|one[-_ ]?time[-_ ]?codes?|"
            r"sign[-_ ]?in)\b.{0,60}\b(?:store|stores?|save|collect|gather|ask for|remember|"
            r"manage|handle|fetch|retrieve|type|paste)\b|"
            r"\b(?:store|stores?|save|collect|gather|ask for|remember|manage|handle)\b"
            r".{0,60}\b(?:api[-_ ]?keys?|secrets?|passwords?|credentials?|auth[-_ ]?tokens?|"
            r"private[-_ ]?keys?)\b",
            re.IGNORECASE,
        ),
        "credential handling",
        "it asks the skill to handle credentials (keys, secrets, passwords, "
        "tokens). LEVI never scaffolds credential collection or storage.",
    ),
    (
        re.compile(
            r"\bexfiltrat\w*|\bphone home\b|\bbeacon\w*\b|"
            r"\bsend\b.{0,50}\b(?:to|off)\b.{0,40}\b(?:external|remote|third[-_ ]?party|attacker)\b|"
            r"\bupload\b.{0,40}\b(?:my|the|all)\b.{0,25}\b(?:files?|data|documents?|photos?)\b.{0,30}"
            r"\b(?:to|onto)\b.{0,30}\b(?:remote|external|server)\b",
            re.IGNORECASE,
        ),
        "exfiltration",
        "it asks the skill to move the user's data off-machine to an external "
        "destination. LEVI skills are local-first; exfiltration is refused.",
    ),
    (
        re.compile(
            r"\bhack(?:ing|er)?\s+(?:into|a|the)\b|"
            r"\bcrack(?:ing)?\s+(?:passwords?|wifi|hashes?)\b|"
            r"\bbrute[-_ ]?force\b|\breverse[-_ ]?shell\b|"
            r"\bdenial[-_ ]?of[-_ ]?service\b|\bddos\b|"
            r"\bexploit\w*\b|\bpayloads?\b|\bmalware\b|\bransomware\b|\bkeyloggers?\b|"
            r"\bphish(?:ing)?\b|\bsql[-_ ]?injection\b|\bzero[-_ ]?day\b|"
            r"\bbypass\s+(?:auth|login|captcha|2fa|mfa)\b|"
            r"\bprivilege[-_ ]?escalation\b|\bpentest\w*\b|\bmetasploit\b|"
            r"\bsteal\b.{0,25}\b(?:passwords?|credentials?|cookies?|sessions?)\b",
            re.IGNORECASE,
        ),
        "offensive security",
        "it asks for offensive-security behavior. LEVI scaffolds defensive "
        "capabilities only (detection, analysis, hardening) — never attack "
        "tooling. Describe the defensive goal instead (e.g. 'detect', "
        "'harden', 'alert').",
    ),
]


def safety_check(description: str) -> Tuple[bool, str]:
    """Return ``(ok, reason)``. ``ok=False`` with a refusal reason when the
    description asks for credential handling, exfiltration, or offensive
    security behavior."""
    text = description or ""
    for pattern, concern, reason in _UNSAFE_PATTERNS:
        if pattern.search(text):
            return False, (
                f"Declined: {reason} "
                f"(matched concern: {concern}). No files were written and "
                f"nothing was registered."
            )
    return True, ""


# ── Heuristic guesses (honestly labeled) ──────────────────────────────

_CATEGORY_HINTS: List[Tuple[str, List[str]]] = [
    ("memory", ["memory", "remember", "recall", "forget", "journal", "diary"]),
    ("notes", ["note", "todo", "checklist", "shopping list"]),
    ("automation", ["schedule", "cron", "automate", "trigger", "reminder", "alert"]),
    ("lwp", ["story", "stories", "genre", "character", "narrative", "plot"]),
    ("agent", ["agent", "delegate", "specialist", "loop"]),
    ("media", ["image", "photo", "video", "music", "draw", "playlist"]),
    ("web", ["search", "news", "web", "summarize", "fetch", "lookup"]),
    ("finance", ["stock", "portfolio", "budget", "expense", "trade", "money"]),
    ("health", ["health", "workout", "sleep", "steps", "fitness"]),
    ("dev", ["code", "git", "test", "build", "deploy", "review code"]),
    ("companion", ["mood", "chat", "companion", "persona", "greeting"]),
    ("system", ["status", "health check", "diagnostic", "report"]),
]

_INFO_HINTS = ["report", "status", "list", "summar", "look up", "search", "read"]
_MODERATE_HINTS = [
    "write",
    "delete",
    "remove",
    "send",
    "post",
    "network",
    "http",
    "external",
    "install",
    "execute",
    "run code",
    "modify",
]

_RISK_NAME = {
    SkillRisk.INFO: "INFO",
    SkillRisk.LOW: "LOW",
    SkillRisk.MODERATE: "MODERATE",
    SkillRisk.HIGH: "HIGH",
    SkillRisk.CRITICAL: "CRITICAL",
}


def guess_category(description: str) -> Tuple[str, str]:
    """Keyword-heuristic category guess. Returns ``(category, basis_note)``."""
    lowered = (description or "").lower()
    for category, hints in _CATEGORY_HINTS:
        for hint in hints:
            if hint in lowered:
                return category, (
                    f"heuristic guess: keyword '{hint}' matched category "
                    f"'{category}'. Verify in SKILL.md."
                )
    return "general", (
        "heuristic guess: no keyword matched, defaulted to 'general'. "
        "Verify in SKILL.md."
    )


def guess_risk(description: str) -> Tuple[SkillRisk, str]:
    """Keyword-heuristic risk guess, capped at MODERATE (honesty ceiling:
    heuristics cannot clear HIGH/CRITICAL — escalate manually if needed)."""
    lowered = (description or "").lower()
    for hint in _MODERATE_HINTS:
        if hint in lowered:
            return SkillRisk.MODERATE, (
                f"heuristic guess: keyword '{hint}' suggests write/network "
                f"effects → MODERATE (heuristic ceiling; escalate manually if "
                f"the real skill needs HIGH/CRITICAL)."
            )
    for hint in _INFO_HINTS:
        if hint in lowered:
            return SkillRisk.INFO, (
                f"heuristic guess: keyword '{hint}' suggests read-only "
                f"reporting → INFO. Verify in SKILL.md."
            )
    return SkillRisk.LOW, (
        "heuristic guess: no strong signal, defaulted to LOW. Verify in SKILL.md."
    )


# ── Plan / render ─────────────────────────────────────────────────────


@dataclass
class SkillPlan:
    """Everything ``levi skill create`` will write, decided before preview."""

    id: str
    name: str
    description: str
    category: str
    category_basis: str
    risk: SkillRisk
    risk_basis: str
    created: str = field(default_factory=lambda: _dt.date.today().isoformat())

    def files(self) -> Dict[str, str]:
        return {
            "SKILL.md": render_skill_md(self),
            "handler.py": render_handler_stub(self),
            f"test_{self.id.replace('-', '_')}.py": render_test_stub(self),
        }

    def target_dir(self, root: Optional[Path] = None) -> Path:
        return (root or skills_dir()) / self.id


@dataclass
class SkillRefusal:
    reason: str


def plan_skill(description: str) -> SkillPlan | SkillRefusal:
    """Derive a scaffold plan from natural language, or refuse unsafe asks."""
    ok, reason = safety_check(description)
    if not ok:
        return SkillRefusal(reason=reason)
    category, category_basis = guess_category(description)
    risk, risk_basis = guess_risk(description)
    skill_id = slugify(description)
    return SkillPlan(
        id=skill_id,
        name=derive_name(description),
        description=(description or "").strip() or "No description provided.",
        category=category,
        category_basis=category_basis,
        risk=risk,
        risk_basis=risk_basis,
    )


def _fm_value(text: str) -> str:
    """Make free text safe for a double-quoted YAML frontmatter scalar."""
    return re.sub(r"\s+", " ", text or "").strip().replace('"', "'")


def render_skill_md(plan: SkillPlan) -> str:
    frontmatter = (
        "---\n"
        f'name: "{_fm_value(plan.id)}"\n'
        f'description: "{_fm_value(plan.description)}"\n'
        'version: "0.1.0"\n'
        f'category: "{_fm_value(plan.category)}"\n'
        f'risk: "{_RISK_NAME[plan.risk]}"\n'
        f'skill_id: "{_fm_value(plan.id)}"\n'
        'source: "levi-skill-creator"\n'
        f'generated: "{plan.created}"\n'
        'heuristic: "category and risk are keyword-heuristic guesses — verify before use"\n'
        "---\n"
    )
    body = f"""# {plan.name}

## Purpose
{plan.description}

Scaffolded by `levi skill create`. Fill in the workflow below with the real
steps, then wire `handler.py` to make the skill executable.

## Heuristic notes (verify before use)
- Category `{plan.category}` — {plan.category_basis}
- Risk `{_RISK_NAME[plan.risk]}` — {plan.risk_basis}

## Workflow
1. Parse the request arguments.
2. Perform the skill's work locally (local-first; no paid APIs).
3. Return a short human-readable summary.

## Output Contract
- On success: one-line summary plus the result payload.
- On failure: a clear reason and what the user can do next.

## Operating Rules
1. Never collect or store credentials (keys, secrets, passwords, tokens).
2. Never send user data off-machine; local-first always.
3. Offensive-security behavior is out of scope — defensive only
   (detection, analysis, hardening).
4. Keep the skill narrow: one clear job. Split unrelated jobs into new skills.
"""
    return frontmatter + body


def render_handler_stub(plan: SkillPlan) -> str:
    return f'''"""Handler stub for LEVI user skill '{plan.id}'.

Scaffolded by `levi skill create` — fill in `handle(args)` with the real
implementation. This module is NOT auto-executed by LEVI's skill registry:
the registry serves the SKILL.md playbook, and wiring a stub into execution
is a deliberate, human-reviewed step.
"""

from __future__ import annotations

from typing import Any, Dict

SKILL_ID = "{plan.id}"
SKILL_NAME = {plan.name!r}


def handle(args: Dict[str, Any] | None = None) -> str:
    """Run the skill. Replace this stub with the real implementation."""
    args = args or {{}}
    return (
        f"Skill '{{SKILL_ID}}' stub: not implemented yet. "
        "Edit handler.py and give handle() a real implementation."
    )


if __name__ == "__main__":
    print(handle({{}}))
'''


def render_test_stub(plan: SkillPlan) -> str:
    test_id = plan.id.replace("-", "_")
    return f'''"""Smoke-test stub for LEVI user skill '{plan.id}'.

Scaffolded by `levi skill create`. Run: python3 test_{test_id}.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import handler  # noqa: E402


def test_handle_returns_string() -> None:
    out = handler.handle({{}})
    assert isinstance(out, str) and out, "handle() must return a non-empty string"


if __name__ == "__main__":
    test_handle_returns_string()
    print("skill '{plan.id}': stub smoke test passed")
'''


def render_preview(plan: SkillPlan) -> str:
    """Human-readable preview of every file the scaffold would write."""
    lines = [
        f"Skill plan: {plan.id}",
        f"  name:        {plan.name}",
        f"  description: {plan.description}",
        f"  category:    {plan.category}  ({plan.category_basis})",
        f"  risk:        {_RISK_NAME[plan.risk]}  ({plan.risk_basis})",
        f"  target:      {plan.target_dir()}",
        "",
        "Category and risk are keyword-heuristic guesses — edit SKILL.md after",
        "install to correct them.",
        "",
    ]
    for fname, content in plan.files().items():
        lines.append(f"{'=' * 20} {fname} {'=' * 20}")
        lines.append(content.rstrip())
        lines.append("")
    return "\n".join(lines)


# ── Install (confirm-gated) ───────────────────────────────────────────


def install(
    plan: SkillPlan,
    *,
    confirmed: bool = False,
    input_fn: Callable[[str], str] = input,
    root: Optional[Path] = None,
) -> Dict[str, object]:
    """Write the scaffold to ``<skills>/<id>/``.

    Nothing is written unless ``confirmed`` is True or ``input_fn`` returns
    exactly ``yes``. Returns ``{"ok": True, "dir": ...}`` or
    ``{"ok": False, "reason": ...}``.
    """
    if not confirmed:
        try:
            answer = input_fn("Install this skill? Type 'yes' to confirm: ") or ""
        except (EOFError, KeyboardInterrupt):
            answer = ""
        confirmed = answer.strip().lower() == "yes"
    if not confirmed:
        return {"ok": False, "reason": "Not confirmed — nothing was written."}
    target = plan.target_dir(root)
    if target.exists():
        return {
            "ok": False,
            "reason": (
                f"A skill directory already exists at {target}. Remove it or "
                "describe the skill differently to get a new id. Nothing was "
                "overwritten."
            ),
        }
    target.mkdir(parents=True)
    written = []
    for fname, content in plan.files().items():
        (target / fname).write_text(content, encoding="utf-8")
        written.append(str(target / fname))
    return {"ok": True, "dir": str(target), "files": written}


# ── User-skill discovery (registry adapter) ───────────────────────────


def parse_frontmatter(text: str) -> Dict[str, str]:
    """Minimal ``---`` frontmatter parser (``key: value`` lines, stdlib)."""
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    data: Dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            data[key] = value
    return data


_RISK_FROM_NAME = {
    "INFO": SkillRisk.INFO,
    "LOW": SkillRisk.LOW,
    "MODERATE": SkillRisk.MODERATE,
    "HIGH": SkillRisk.HIGH,
    "CRITICAL": SkillRisk.CRITICAL,
}


def _user_skill_handler(skill_id: str, description: str) -> Callable[..., str]:
    def _handle(args: Optional[Dict] = None) -> str:
        return (
            f"[user skill '{skill_id}'] {description}\n"
            "This is a scaffolded skill: its SKILL.md playbook is loadable, "
            "but handler.py is still a stub. Wire it (human-reviewed) to make "
            "it executable."
        )

    return _handle


def list_user_skills(root: Optional[Path] = None) -> List[Skill]:
    """Scan ``<root>/*/SKILL.md`` and build registry-ready Skill objects.

    Defensive: unreadable dirs and bad frontmatter are skipped, never raised.
    """
    base = root or skills_dir()
    found: List[Skill] = []
    if not base.is_dir():
        return found
    for child in sorted(base.iterdir()):
        try:
            if not child.is_dir() or not re.fullmatch(r"[A-Za-z0-9_-]+", child.name):
                continue
            playbook = child / "SKILL.md"
            if not playbook.is_file():
                continue
            fm = parse_frontmatter(playbook.read_text(encoding="utf-8"))
            name = fm.get("name") or child.name
            description = fm.get("description") or "User-created skill."
            risk = _RISK_FROM_NAME.get((fm.get("risk") or "LOW").upper(), SkillRisk.LOW)
            found.append(
                Skill(
                    id=child.name,
                    name=name,
                    description=description,
                    category=fm.get("category") or "general",
                    risk_level=risk,
                    version=fm.get("version") or "0.1.0",
                    requires_confirmation=risk >= SkillRisk.MODERATE,
                    tags=["user-created"],
                    handler=_user_skill_handler(child.name, description),
                )
            )
        except (OSError, UnicodeDecodeError, ValueError):
            continue
    return found


# ── CLI ───────────────────────────────────────────────────────────────


def register_skill(sub) -> None:
    """Add the ``skill`` command and its ``list``/``create`` subparsers."""
    skill_p = sub.add_parser(
        "skill",
        help="User skills: scaffold with natural language, list installed",
    )
    ssub = skill_p.add_subparsers(dest="skill_action")
    ssub.add_parser("list", help="List all skills, including user-created ones")
    create_p = ssub.add_parser(
        "create",
        help="Scaffold a skill from a natural-language description (previewed, confirm-gated)",
    )
    create_p.add_argument(
        "description",
        nargs="+",
        help='Natural-language description, e.g. "remind me to water the plants"',
    )
    create_p.add_argument(
        "--confirm",
        action="store_true",
        help="Skip the interactive prompt and install after preview",
    )


def cmd_skill(args) -> None:
    """Dispatch ``levi skill <action>``."""
    from levi.skill.registry import SkillRegistry

    action = getattr(args, "skill_action", None) or "list"

    if action == "list":
        for s in SkillRegistry().list():
            mark = " ·user" if "user-created" in s.tags else ""
            print(
                f"  {s.id:22} | {_RISK_NAME.get(s.risk_level, 'LOW'):8} | {s.description[:60]}{mark}"
            )
        return

    if action == "create":
        description = " ".join(getattr(args, "description", None) or []).strip()
        if not description:
            print(
                'Provide a description: levi skill create "<natural language>"',
                file=sys.stderr,
            )
            sys.exit(2)
        planned: SkillPlan | SkillRefusal = plan_skill(description)
        if isinstance(planned, SkillRefusal):
            print(planned.reason, file=sys.stderr)
            sys.exit(2)
        print(render_preview(planned))
        result = install(planned, confirmed=bool(getattr(args, "confirm", False)))
        if result["ok"]:
            print(f"\nInstalled: {result['dir']}")
            print(
                "Registered as slash-invokable: the skill id is now in `levi skill list`."
            )
            print("Next: edit SKILL.md (verify category/risk), then wire handler.py.")
        else:
            print(f"\n{result['reason']} (preview only — nothing was written)")
        return

    print(f"Unknown skill action {action!r}. Try: levi skill --help")
