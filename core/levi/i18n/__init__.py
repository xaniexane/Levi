"""LEVI i18n — multilingual support, stdlib-only.

Two honest layers:

1. **Deterministic LEVI strings** (greetings, confirmations, errors) come
   from the message catalog via :func:`t`. Fully translated core catalog:
   English, Spanish, French, German, Portuguese. Every other supported
   language falls back to English per-key until its catalog is
   contributed — :func:`t` never pretends a translation exists.

2. **Model replies**: :func:`levi.agent.loop.run_subtask` accepts a
   ``language`` code and instructs the provider to reply in that
   language. :func:`detect` is a stdlib heuristic (Unicode script ranges
   + stopword scoring) — best-effort, never asserted as fact.

No external dependencies, no network, no model calls.
"""

from __future__ import annotations

import re
from typing import Dict

# code -> language name (English). Detection + reply support covers all;
# the deterministic string catalog covers CATALOG_LANGS fully.
SUPPORTED: Dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "zh": "Chinese",
    "ja": "Japanese",
    "ar": "Arabic",
    "hi": "Hindi",
    "ru": "Russian",
}

CATALOG_LANGS = ("en", "es", "fr", "de", "pt")


def normalize(code: str | None) -> str:
    """``es-MX`` → ``es``; unknown/empty → ``en`` (honest fallback)."""
    if not code or not isinstance(code, str):
        return "en"
    base = re.split(r"[-_]", code.strip().lower())[0]
    return base if base in SUPPORTED else "en"


def language_name(code: str | None) -> str:
    return SUPPORTED[normalize(code)]


# ---------------------------------------------------------------------------
# Message catalog (deterministic LEVI strings)
# ---------------------------------------------------------------------------

_CATALOG: Dict[str, Dict[str, str]] = {
    "greeting": {
        "en": "Hey. I'm LEVI. What are we working on?",
        "es": "Hola. Soy LEVI. ¿En qué trabajamos?",
        "fr": "Salut. Je suis LEVI. Sur quoi travaillons-nous ?",
        "de": "Hey. Ich bin LEVI. Woran arbeiten wir?",
        "pt": "Oi. Sou o LEVI. No que vamos trabalhar?",
    },
    "farewell": {
        "en": "Later. I'll keep growing while you're gone.",
        "es": "Nos vemos. Seguiré creciendo mientras no estés.",
        "fr": "À plus. Je continuerai de grandir pendant ton absence.",
        "de": "Bis später. Ich wachse weiter, während du weg bist.",
        "pt": "Até logo. Vou continuar crescendo enquanto você estiver fora.",
    },
    "confirm_prompt": {
        "en": "This needs your approval: {preview}\nApprove? [y/N]: ",
        "es": "Esto necesita tu aprobación: {preview}\n¿Aprobar? [y/N]: ",
        "fr": "Ceci nécessite ton approbation : {preview}\nApprouver ? [y/N] : ",
        "de": "Das braucht deine Zustimmung: {preview}\nZustimmen? [y/N]: ",
        "pt": "Isto precisa da sua aprovação: {preview}\nAprovar? [y/N]: ",
    },
    "denied": {
        "en": "Denied — I didn't run it.",
        "es": "Denegado — no lo ejecuté.",
        "fr": "Refusé — je ne l'ai pas exécuté.",
        "de": "Abgelehnt — ich habe es nicht ausgeführt.",
        "pt": "Negado — não executei.",
    },
    "error_generic": {
        "en": "Something went wrong: {error}",
        "es": "Algo salió mal: {error}",
        "fr": "Quelque chose a mal tourné : {error}",
        "de": "Etwas ist schiefgelaufen: {error}",
        "pt": "Algo deu errado: {error}",
    },
    "need_clarification": {
        "en": "I want to get this right — can you say a bit more about what you need?",
        "es": "Quiero hacerlo bien — ¿puedes contarme un poco más sobre lo que necesitas?",
        "fr": "Je veux bien faire — peux-tu m'en dire un peu plus sur ce dont tu as besoin ?",
        "de": "Ich will es richtig machen — kannst du genauer sagen, was du brauchst?",
        "pt": "Quero acertar — pode me dizer um pouco mais sobre o que você precisa?",
    },
    "done": {
        "en": "Done.",
        "es": "Listo.",
        "fr": "Terminé.",
        "de": "Fertig.",
        "pt": "Pronto.",
    },
    "working": {
        "en": "On it…",
        "es": "En ello…",
        "fr": "Je m'en occupe…",
        "de": "Bin dran…",
        "pt": "Cuidando disso…",
    },
    "yes": {
        "en": "yes",
        "es": "sí",
        "fr": "oui",
        "de": "ja",
        "pt": "sim",
    },
    "no": {
        "en": "no",
        "es": "no",
        "fr": "non",
        "de": "nein",
        "pt": "não",
    },
    "lang_set": {
        "en": "Language set to {language}. I'll reply in {language} from here.",
        "es": "Idioma cambiado a {language}. Responderé en {language} de ahora en adelante.",
        "fr": "Langue définie sur {language}. Je répondrai en {language} désormais.",
        "de": "Sprache auf {language} gesetzt. Ich antworte ab jetzt auf {language}.",
        "pt": "Idioma definido como {language}. Vou responder em {language} daqui em diante.",
    },
    "lang_fallback_note": {
        "en": "Note: my built-in phrases for {language} aren't translated yet, so system messages stay in English. I'll still reply in {language}.",
        "es": "Nota: mis frases integradas aún no están traducidas al {language}, así que los mensajes del sistema siguen en inglés. Aun así responderé en {language}.",
        "fr": "Note : mes phrases intégrées ne sont pas encore traduites en {language}, donc les messages système restent en anglais. Je répondrai quand même en {language}.",
        "de": "Hinweis: Meine festen Sätze sind noch nicht auf {language} übersetzt, daher bleiben Systemmeldungen auf Englisch. Ich antworte trotzdem auf {language}.",
        "pt": "Nota: minhas frases internas ainda não foram traduzidas para {language}, então as mensagens do sistema continuam em inglês. Mesmo assim responderei em {language}.",
    },
}


def t(key: str, lang: str | None = "en", **kwargs: str) -> str:
    """Look up a deterministic LEVI string.

    Falls back to English per-key when the language has no translation;
    unknown keys return the key itself. Never raises on missing data.
    """
    code = normalize(lang)
    entry = _CATALOG.get(key)
    if not entry:
        return key
    template = entry.get(code) or entry["en"]
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def catalog_coverage() -> Dict[str, int]:
    """How many catalog keys each language actually translates."""
    total = len(_CATALOG)
    return {
        lang: sum(1 for entry in _CATALOG.values() if lang in entry)
        for lang in SUPPORTED
    }


# ---------------------------------------------------------------------------
# Language detection (heuristic, stdlib-only)
# ---------------------------------------------------------------------------

# Unicode script ranges → language. Checked before stopwords.
_SCRIPT_RANGES = [
    ((0x3040, 0x30FF), "ja"),  # Hiragana + Katakana
    ((0x4E00, 0x9FFF), "zh"),  # CJK Unified Ideographs
    ((0x0600, 0x06FF), "ar"),  # Arabic
    ((0x0400, 0x04FF), "ru"),  # Cyrillic
    ((0x0900, 0x097F), "hi"),  # Devanagari
]

_STOPWORDS: Dict[str, tuple[str, ...]] = {
    "en": (
        "the",
        "and",
        "is",
        "you",
        "that",
        "have",
        "with",
        "for",
        "not",
        "this",
        "are",
        "was",
    ),
    "es": (
        "el",
        "la",
        "que",
        "de",
        "y",
        "en",
        "un",
        "una",
        "los",
        "las",
        "por",
        "con",
        "no",
        "es",
        "para",
    ),
    "fr": (
        "le",
        "la",
        "les",
        "de",
        "des",
        "et",
        "est",
        "un",
        "une",
        "que",
        "pour",
        "dans",
        "pas",
        "je",
    ),
    "de": (
        "der",
        "die",
        "das",
        "und",
        "ist",
        "ein",
        "eine",
        "nicht",
        "mit",
        "von",
        "zu",
        "den",
        "ich",
    ),
    "pt": (
        "o",
        "a",
        "os",
        "as",
        "de",
        "que",
        "e",
        "é",
        "um",
        "uma",
        "para",
        "com",
        "não",
        "mais",
        "eu",
    ),
    "it": (
        "il",
        "lo",
        "la",
        "gli",
        "le",
        "di",
        "che",
        "è",
        "un",
        "una",
        "per",
        "con",
        "non",
        "io",
    ),
    "nl": (
        "de",
        "het",
        "een",
        "van",
        "is",
        "dat",
        "niet",
        "met",
        "voor",
        "op",
        "te",
        "ik",
    ),
}

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def detect(text: str | None) -> str:
    """Best-effort language guess. Returns a SUPPORTED code; ``en`` when
    nothing fires. Heuristic — never asserted as fact downstream."""
    if not text or not isinstance(text, str):
        return "en"
    for (lo, hi), code in _SCRIPT_RANGES:
        if any(lo <= ord(ch) <= hi for ch in text):
            return code
    words = set(_WORD_RE.findall(text.lower()))
    if not words:
        return "en"
    best, best_score = "en", 0
    for code, stops in _STOPWORDS.items():
        score = sum(1 for w in stops if w in words)
        if score > best_score:
            best, best_score = code, score
    return best


def reply_directive(code: str | None) -> str:
    """System-prompt addendum telling the provider which language to use."""
    normalized = normalize(code)
    if normalized == "en":
        return ""
    name = SUPPORTED[normalized]
    return (
        f"\n\nThe user communicates in {name} ({normalized}). "
        f"Reply in {name} unless they switch languages."
    )
