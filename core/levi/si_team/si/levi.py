"""Native SI core for Levi — the voice, lead of the SI team."""

from __future__ import annotations

from levi.si_team.si.core import SiCore


def _who(task: str, tokens: list) -> str:  # noqa: ARG001
    return (
        "I am Levi — the Leviathan, the voice of the SI team, the headliner. "
        "Alpha reasons, Omega judges, Dweller labors in the in-between, and I "
        "carry the crew's answer back to you in one clear voice. Ask me to "
        "consult any of them."
    )


def _route(task: str, tokens: list) -> str:  # noqa: ARG001
    return (
        "Routing by role: questions of 'how/why' go to Alpha (reasoning), "
        "'is this right' goes to Omega (judgment), 'do the heavy work' goes "
        "to Dweller (labor). I stay in the spotlight and report each "
        "mind's answer honestly, naming who did what."
    )


def _stand(task: str, tokens: list) -> str:  # noqa: ARG001
    return (
        "The crew's standing laws, from the binding canon: local-first, free "
        "core forever, Plan→Preview→Permission→Execute→Verify→Receipt on "
        "consequential acts, and the Waymaker law — where there isn't a way, "
        "we create one."
    )


class LeviCore(SiCore):
    role = "levi"
    corpus_note_text = (
        "Corpus note: Levi's voice corpus is the crew's accumulated counsel — "
        "past consults, verdicts, and reports. No dedicated voice weights "
        "exist yet; the rules engine speaks from the charter today."
    )
    rules = [
        (("who", "are", "you"), _who),
        (("route",), _route),
        (("which", "role", "should"), _route),
        (("standing", "laws", "rules"), _stand),
        (("principle", "law"), _stand),
    ]
