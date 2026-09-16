"""Generation seam for the LEVI Builder.

Every pipeline stage (planner, frontend, backend, data, tester-notes,
packager) produces text through a *generator*: a callable taking
``(prompt, system_prompt)`` and returning raw text.

The default generator reuses the existing agent runtime
(:func:`levi.agent.loop.run_subtask`) — the builder never rebuilds the
loop. Tests and offline runs inject a stub generator instead, so the
pipeline stays hermetic.
"""

from __future__ import annotations

from typing import Callable, Dict

# A generator: (prompt, system_prompt) -> raw text output.
Generator = Callable[[str, str], str]


class GenerationError(RuntimeError):
    """The generator failed or returned nothing usable."""


def strip_fences(text: str) -> str:
    """Remove markdown code fences defensively.

    Stage prompts demand raw file content, but generators sometimes
    fence it anyway. This strips one wrapping fence pair (and any
    language tag) so the pipeline still gets clean content.
    """
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        lines = lines[1:]  # drop opening fence (+language tag)
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def agent_generator(prompt: str, system_prompt: str, *, max_steps: int = 8) -> str:
    """Default generator: one delegated subtask through the agent loop.

    Reuses :func:`levi.agent.loop.run_subtask` — the canonical
    plan→act→observe loop — with the stage's system prompt carrying
    the strict output contract.
    """
    from levi.agent.loop import run_subtask

    transcript = run_subtask(
        prompt,
        system_prompt=system_prompt,
        max_steps=max_steps,
        growth=False,
    )
    if not transcript.ok or not transcript.final.strip():
        raise GenerationError(
            f"agent subtask failed (provider={transcript.provider_name}): "
            f"{transcript.error or 'empty final text'}"
        )
    return strip_fences(transcript.final)


def stub_generator(mapping: Dict[str, str]) -> Generator:
    """Build a canned generator for tests.

    ``mapping`` keys are substrings matched against the prompt; the
    first matching key's value is returned (fences stripped). Raises
    :class:`GenerationError` when nothing matches, so tests fail
    loudly on unexpected stage prompts.
    """

    def _gen(prompt: str, system_prompt: str) -> str:
        for key, value in mapping.items():
            if key in prompt:
                return strip_fences(value)
        raise GenerationError(
            f"stub generator: no canned output for prompt: {prompt[:80]!r}"
        )

    return _gen
