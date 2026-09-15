"""Stress / verify harness for engines."""

from __future__ import annotations

from typing import List


def run_stress() -> str:
    lines = ["══ LEVI stress / verify ══"]
    fails: List[str] = []
    ok = 0

    def check(name: str, fn):
        nonlocal ok
        try:
            fn()
            lines.append(f"  PASS  {name}")
            ok += 1
        except Exception as e:
            lines.append(f"  FAIL  {name}: {e}")
            fails.append(name)

    def story_batch():
        from levi.graph.story_prose import expand_paragraph
        from levi.graph.story_quality import rate_text

        scores = []
        for genre in [
            "systems_horror",
            "literary",
            "trauma_recursion",
            "post_privacy_noir",
            "lattice_gothic",
        ]:
            for i in range(3):
                t = expand_paragraph(
                    "Hook",
                    "Lena Voss",
                    genre,
                    "A lattice opens under weather law",
                    "old compromise",
                    i,
                )
                # no consecutive duplicate sentences
                parts = t.split(". ")
                for a, b in zip(parts, parts[1:], strict=False):
                    if a == b:
                        raise AssertionError(f"duplicate sentence in {genre}")
                r = rate_text(t)
                scores.append(r.score)
                if "Premise pressure remained" in t:
                    raise AssertionError("old formula marker present")
        avg = sum(scores) / len(scores)
        if avg < 6.5:
            raise AssertionError(f"avg story quality {avg:.2f} < 6.5")
        lines.append(
            f"       story avg quality {avg:.2f}/10 across {len(scores)} samples"
        )

    def fabric_create():
        from levi.graph.story_fabric import StoryFabric
        from levi.graph.story_quality import rate_story_dict

        sf = StoryFabric()
        st = sf.create_story(
            "The city bills the breath; a lattice opens.", genre="systems_horror"
        )
        d = st.to_dict() if hasattr(st, "to_dict") else {"body": str(st)}
        body = d.get("body") or ""
        if len(body) < 400:
            raise AssertionError("story body too short")
        rep = rate_story_dict(d)
        lines.append(
            f"       fabric story {rep.score}/10 ({rep.grade}) words={rep.words}"
        )

    def kai_attr():
        from levi.persona.levi import format_levi_roster, all_variants

        text = format_levi_roster()
        assert "not third-party" in text.lower() or "Original LEVI" in text
        assert len(all_variants()) >= 12

    def mesh():
        from levi.ops.interpenetrate import smoke, EDGES

        assert len(EDGES) >= 15
        s = smoke()
        assert int(s.get("max_units") or 0) >= 2500

    def enterprise():
        from levi.ops.enterprise import run_enterprise_checklist

        rows = run_enterprise_checklist()
        bad = [r for r in rows if not r.ok]
        if bad:
            raise AssertionError(f"{len(bad)} enterprise fails")

    check("story_prose_batch_quality", story_batch)
    check("story_fabric_create_rate", fabric_create)
    check("kai_attribution", kai_attr)
    check("interpenetrate_smoke", mesh)
    check("enterprise_checklist", enterprise)

    lines.append("")
    lines.append(f"result: {ok} passed, {len(fails)} failed")
    if fails:
        lines.append("failed: " + ", ".join(fails))
    else:
        lines.append("HYPERDRIVE VERIFY: green — course set outward")
    return "\n".join(lines)
