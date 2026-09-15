"""
High-quality offline prose for story expand/create — literary delivery without LLM.

Deterministic, seed-stable, genre-aware paragraphs. Used when local model is absent.
"""

from __future__ import annotations

from typing import List, Optional
import hashlib
import random


def _rng(seed: str) -> random.Random:
    h = int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16)
    return random.Random(h)


GENRE_ATMOSPHERE = {
    "systems_horror": [
        "Protocol metered the room the way weather meters a field.",
        "The infrastructure did not threaten; it administered.",
        "A ceiling of rules lowered until breathing counted as a request.",
        "Somewhere a ledger closed on a cost that had not been named out loud.",
    ],
    "literary": [
        "The brand still meant what it had cost.",
        "Pressure gathered behind the sternum like a held report.",
        "What was said covered less than half the temperature of the hour.",
        "Memory reorganized the present around its old shape without asking.",
    ],
    "trauma_recursion": [
        "The injury re-entered at a deeper register — same door, worse furniture.",
        "The body kept a better archive than the calendar.",
        "Every attempt to leave wrote a finer copy of the original trap.",
    ],
    "post_privacy_noir": [
        "Attention was already public; the remaining work was cost.",
        "Someone somewhere held a cleaner copy of the hour than they did.",
        "The streetlights knew their names before the paperwork did.",
    ],
    "lattice_gothic": [
        "The network kept rooms the way old houses keep drafts.",
        "Corridors of signal bent toward a center that refused to declare itself.",
        "Stone and code shared the same cold patience.",
    ],
    "consent_dystopia": [
        "Agreement was a shape made to keep the scar quiet.",
        "Choice remained, technically, inside a corridor with one exit.",
        "The form had been signed before the body understood the clause.",
    ],
}

BEAT_OPENERS = {
    "Hook": [
        "{lead} arrived after the irreversible had already begun.",
        "The hour did not introduce itself. {lead} was already inside it.",
        "Cost arrived in the body first; {lead} named it later.",
    ],
    "Complication": [
        "A rule of the world tightened until {lead}'s preferred exit no longer opened.",
        "The first real invoice arrived without a line item {lead} could argue.",
        "What had looked like weather became jurisdiction.",
    ],
    "Midpoint Turn": [
        "Information landed that could not be unread. {lead} felt the map redraw.",
        "The choice was not between good and bad — only between two kinds of scar.",
        "Power changed hands in a sentence that sounded like ordinary speech.",
    ],
    "Darkening": [
        "{lead}'s strategy failed in the exact shape of their wound.",
        "The old workaround stopped working the moment it was needed most.",
        "Help was available only in forms that required a surrender {lead} could not afford.",
    ],
    "Convergence": [
        "Threads that had pretended to be separate occupied the same room.",
        "Allies and systems shared air; none of them were neutral.",
        "The cascade no longer asked permission to peak.",
    ],
    "Aftermath": [
        "What remained was not peace — only a new equilibrium with a name.",
        "The ledger stayed open. {lead} could read the next line.",
        "Equilibrium, or recursion: the difference would show in the next season.",
    ],
    "Echo Return": [
        "An earlier hour returned, wearing later knowledge like a second skin.",
        "The loop did not repeat; it refined.",
        "Memory of the first compromise collected interest.",
    ],
    "Spiral Deepening": [
        "Same stakes, higher resolution. The grain of the problem became visible.",
        "{genre} logic tightened one more notch without raising its voice.",
        "Depth was not drama — it was accuracy.",
    ],
    "Final Cost": [
        "What {lead} kept and what they lost could finally be said in one breath.",
        "The price had a face. {lead} looked at it without turning away.",
        "Nothing was free. The bill had always been the story.",
    ],
    "Coda": [
        "A last image held. The bible of this story could close — or reopen under weather.",
        "The room kept a temperature. {lead} left a print on the air.",
        "Endings were only pauses the cascade allowed.",
    ],
}

SENSORY = [
    "the tick of a cooling machine",
    "dust hanging in a shaft of unkind light",
    "a chair leg scraping like a verdict",
    "the sound of the room changing register",
    "cold collecting at the wrists",
    "a metallic taste that belonged to decisions",
    "light that refused to flatter anyone",
    "the weight of a door that had learned their name",
    "air thin with other people's certainty",
]

CLOSING = [
    "Scar law held: yesterday's compromise was still collecting.",
    "Focalization stayed locked; other minds remained weather, not narration rights.",
    "The cascade advanced one typed step — not a flourish, a hinge.",
    "Nothing reset for convenience.",
]


def expand_paragraph(
    beat_name: str,
    lead: str,
    genre: str,
    premise: str,
    wound: str = "",
    index: int = 0,
    supporting: Optional[str] = None,
) -> str:
    """Build a multi-sentence literary paragraph for a cascade beat.

    Hardened: no duplicate atmosphere, less formula scaffolding, denser sensory.
    """
    seed = f"{beat_name}|{lead}|{genre}|{premise}|{index}"
    r = _rng(seed)
    genre_key = genre.strip().lower().replace(" ", "_")
    atmo = list(
        GENRE_ATMOSPHERE.get(genre_key) or GENRE_ATMOSPHERE.get("literary") or []
    )
    openers = BEAT_OPENERS.get(beat_name) or [
        f"{{lead}} moved through the next pressure under {genre.replace('_', ' ')} law."
    ]
    opener = r.choice(openers).format(lead=lead, genre=genre.replace("_", " "))
    parts: List[str] = [opener]

    if premise:
        clip = premise.strip()
        if len(clip) > 120:
            clip = clip[:117] + "…"
        weave = [
            f"The work still traced back to this: {clip}.",
            f"Underneath the hour, the charge remained — {clip}.",
            f"{lead} could not un-know it: {clip}.",
        ]
        parts.append(r.choice(weave))

    used = set()
    if atmo:
        a1 = r.choice(atmo)
        parts.append(a1)
        used.add(a1)
        rest = [a for a in atmo if a not in used]
        if rest and r.random() > 0.35:
            parts.append(r.choice(rest))

    sens = r.choice(SENSORY)
    sens_lines = [
        f"Through {sens}, the beat found its place-time.",
        f"Body inventory: {sens}.",
        f"The world answered with {sens}.",
    ]
    parts.append(r.choice(sens_lines))

    if wound:
        w = wound.rstrip(".")
        wound_lines = [
            f"The old cost — {w} — still structured what moves were legal.",
            f"Scar continuity: {w} had not finished collecting.",
            f"No clean slate: {w} remained load-bearing.",
        ]
        parts.append(r.choice(wound_lines))

    if supporting and r.random() > 0.45:
        parts.append(
            f"{supporting} held the edge of the frame and wanted something unspoken."
        )

    if r.random() > 0.55:
        s2 = r.choice(SENSORY)
        if s2 != sens:
            parts.append(f"Also: {s2}.")

    parts.append(r.choice(CLOSING))

    out: List[str] = []
    for part in parts:
        s = part.rstrip(".") + "."
        if not out or out[-1] != s:
            out.append(s)
    text = " ".join(out)

    words = text.split()
    guard = 0
    pool = [a for a in atmo if (a.rstrip(".") + ".") not in text]
    while len(words) < 95 and pool and guard < 3:
        pick = pool.pop(r.randrange(len(pool)))
        text += " " + pick.rstrip(".") + "."
        words = text.split()
        guard += 1
    return text


def opening_prose(
    lead: str,
    genre: str,
    premise: str,
    want: str = "",
    need: str = "",
    wound: str = "",
    voice: str = "",
) -> str:
    r = _rng(f"open|{lead}|{genre}|{premise}")
    genre_key = genre.strip().lower().replace(" ", "_")
    atmo = GENRE_ATMOSPHERE.get(genre_key) or GENRE_ATMOSPHERE["literary"]
    lines = [
        f"{lead} had already crossed the threshold the story would later call the start.",
        f"Premise: {premise.strip()}",
        r.choice(atmo),
    ]
    if want:
        lines.append(f"Want, named carefully: {want.rstrip('.')}.")
    if need:
        lines.append(f"Need, harder to admit: {need.rstrip('.')}.")
    if wound:
        lines.append(f"Wound under the work: {wound.rstrip('.')}.")
    if voice:
        lines.append(f"Voice held: {voice}.")
    lines.append(r.choice(atmo))
    lines.append(r.choice(CLOSING))
    return " ".join(lines)
