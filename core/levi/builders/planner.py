"""The planner seat: prompt -> architecture plan -> modules -> files.

Every competitor builder that produces genuinely complex apps plans before
it generates (v0's <Thinking>, Replit's plan step, Emergent's Architect,
Bolt's "think holistically"). Their planning is a prompt instruction hoping
the model complies. Ours is a real seat in the pipeline: deterministic,
template-driven, incapable of hallucination.

The plan is the build's contract: the verifier checks the generated files
against it (contracts gate), and refinement re-plans before touching a file.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List

from levi.builders.packs import SHARED_FILES, detect_domain, get_pack
from levi.builders._text import _STOPWORDS, _plural, _slug, _tokens

# Words that mark a request as ambiguous in a way the planner must surface
# rather than guess at. (Guessing is how competitor builds diverge from
# intent; we flag instead.)
_AMBIGUITY_MARKERS = (
    "maybe",
    "perhaps",
    "either",
    "or",
    "not sure",
    "something like",
    "etc",
)


@dataclass
class Field:
    name: str
    type: str  # str | int | float | bool


@dataclass
class EntityModel:
    name: str
    fields: List[Field] = field(default_factory=list)


@dataclass
class ModuleSpec:
    path: str
    kind: str
    purpose: str


@dataclass
class BuildPlan:
    prompt: str
    prompt_hash: str
    seed: int
    app_slug: str
    domain: str
    entities: List[str]
    data_model: List[EntityModel]
    modules: List[ModuleSpec]
    api_surface: List[str]
    design_directives: List[str]
    ambiguities: List[str]
    shared_files: List[str] = field(default_factory=lambda: list(SHARED_FILES))

    @property
    def all_files(self) -> List[str]:
        return [m.path for m in self.modules] + self.shared_files


def _singularize(word: str) -> str:
    """Naive singularizer for planner heuristics (v1-stable, plus sses).

    priorities -> priority, addresses -> address, statuses -> status.
    """
    if word.endswith("sses") and len(word) > 5:
        return word[:-2]  # addresses -> address
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"  # priorities -> priority
    if word.endswith("s") and len(word) > 3 and not word.endswith("ss"):
        return word[:-1]
    return word


# Words that are attributes of a managed thing, never the thing itself.
# "due dates" means a due *field* on the task entity, not a date entity;
# "priorities" means a priority *field*, not a priority entity. Mirrors the
# field hints in _derive_fields: anything the field-deriver would claim as
# a field must not also stand beside the entity as one.
_FIELD_WORDS = frozenset(
    {
        "email",
        "price",
        "cost",
        "amount",
        "date",
        "due",
        "status",
        "priority",
        "quantity",
        "count",
        "description",
        "notes",
        "phone",
        "address",
        "time",
    }
)


# Plural forms of the field words ("statuses", "addresses", "priorities"):
# the naive singularizer mangles some of these, so match them directly.
_FIELD_WORD_PLURALS = frozenset(
    [w + "s" for w in _FIELD_WORDS] + [w + "es" for w in _FIELD_WORDS] + ["priorities"]
)


def _derive_entities(prompt: str) -> List[str]:
    """Same entity heuristics the v1 engine used (kept stable).

    Direct objects of manage-verbs are authoritative: "manage notes" means
    the user manages note records, even though "notes" is field-like.
    Incidental plurals ("due dates", "with priorities") are field-words and
    never become sibling entities — they belong on the data model.
    """

    words = _tokens(prompt)
    managed: List[str] = []
    for i, word in enumerate(words[:-1]):
        if word in {"manage", "track", "store", "organize", "keep"}:
            nxt = words[i + 1]
            if nxt not in _STOPWORDS and len(nxt) > 2:
                managed.append(nxt)
    plural_hits: List[str] = []
    for word in words:
        if (
            len(word) > 3
            and word.endswith("s")
            and word not in _STOPWORDS
            and word not in {"this", "has", "was"}
        ):
            plural_hits.append(word)

    singular: List[str] = []
    for word in managed + plural_hits:
        base = re.sub(r"[^a-z0-9_]", "", _singularize(word))
        field_like = (
            word in _FIELD_WORDS or word in _FIELD_WORD_PLURALS or base in _FIELD_WORDS
        )
        if field_like and word not in managed:
            continue  # a field on the entity, never a sibling entity
        if base and base not in singular and base not in _STOPWORDS:
            singular.append(base)
    return (singular[:3] or ["item"]) if singular else ["item"]


def _derive_fields(prompt: str, seed: int) -> List[Field]:
    """Deterministic field guesses: name/title always, then prompt hints.

    Hints match substrings ("email" in "emailAddress") and singularized
    tokens ("priorities" -> the priority field, "statuses" -> status) —
    attributes belong on the entity's data model, never as entities.
    """
    lowered = prompt.lower()
    singular_tokens = {_singularize(w) for w in _tokens(prompt)}
    fields = [Field("name", "str")]
    hints = (
        ("email", "email", "str"),
        ("price", "price", "float"),
        ("cost", "cost", "float"),
        ("amount", "amount", "float"),
        ("date", "date", "str"),
        ("due", "due", "str"),
        ("status", "status", "str"),
        ("priority", "priority", "str"),
        ("quantity", "quantity", "int"),
        ("count", "count", "int"),
        ("description", "description", "str"),
        ("notes", "notes", "str"),
        ("phone", "phone", "str"),
        ("address", "address", "str"),
    )
    for needle, fname, ftype in hints:
        if needle == "date" and "due" in lowered:
            continue  # "due dates" -> the due field, not a second date field
        hit = needle in lowered or needle in singular_tokens
        if hit and not any(f.name == fname for f in fields):
            fields.append(Field(fname, ftype))
    return fields[:6]


def _derive_api_surface(domain: str, entities: List[str]) -> List[str]:
    if domain in ("web-api", "general"):
        routes = []
        for entity in entities:
            base = "/%s" % _plural(entity)
            routes.extend(
                [
                    "GET %s" % base,
                    "POST %s" % base,
                    "GET %s/{id}" % base,
                    "PUT %s/{id}" % base,
                    "DELETE %s/{id}" % base,
                ]
            )
        return routes
    if domain == "realtime":
        return ["GET /events (server-sent stream)", "POST /publish"]
    if domain == "data-pipeline":
        return ["run.py [--input PATH] [--since OFFSET]"]
    if domain == "cli-tool":
        return ["cli.py <subcommand> [--help]"]
    return []


def _flag_ambiguities(prompt: str) -> List[str]:
    words = set(_tokens(prompt))
    flags = []
    for marker in _AMBIGUITY_MARKERS:
        # Word-boundary match: "records" must not trip the "or" marker.
        if " " in marker:
            hit = marker in prompt.lower()
        else:
            hit = marker in words
        if hit:
            flags.append("prompt contains '%s' — intent unclear" % marker)
    if len(_tokens(prompt)) < 4:
        flags.append("prompt is very short — structure inferred from defaults")
    return flags


def plan(prompt: str) -> BuildPlan:
    """Produce the architecture plan. Deterministic in the prompt."""
    if not prompt or not prompt.strip():
        raise ValueError("prompt must not be empty")
    prompt = prompt.strip()
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    seed = int(digest[:16], 16)

    meaningful = [w for w in _tokens(prompt) if w not in _STOPWORDS]
    slug = _slug("-".join(meaningful[:3]))[:40]

    domain = detect_domain(prompt)
    pack = get_pack(domain)
    entities = _derive_entities(prompt)
    fields = _derive_fields(prompt, seed)
    data_model = [EntityModel(name=e, fields=list(fields)) for e in entities]
    modules = [
        ModuleSpec(path=m["path"], kind=m["kind"], purpose=m["purpose"])
        for m in pack["modules"]
    ]
    return BuildPlan(
        prompt=prompt,
        prompt_hash=digest,
        seed=seed,
        app_slug=slug,
        domain=domain,
        entities=entities,
        data_model=data_model,
        modules=modules,
        api_surface=_derive_api_surface(domain, entities),
        design_directives=list(pack["design_directives"]),
        ambiguities=_flag_ambiguities(prompt),
    )


def plan_summary(plan: BuildPlan) -> Dict:
    """JSON-safe summary for provenance and the ledger."""
    return {
        "domain": plan.domain,
        "entities": plan.entities,
        "modules": [m.path for m in plan.modules],
        "api_surface": plan.api_surface,
        "ambiguities": plan.ambiguities,
    }
