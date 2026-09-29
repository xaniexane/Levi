"""Extra keyboard row: the phone editor's real enemy is the on-screen keyboard.

Per-language snippet rows + bracket-pair auto-close, built in as core —
not an afterthought, not a plugin. Snippet bodies use ${n:placeholder}
tab stops; expansion is pure string work (the UI moves the cursor).
"""

from __future__ import annotations

import re

_TABSTOP = re.compile(r"\$(?:\{(\d+)(?::[^}]*)?\}|(\d+))")

BRACKET_PAIRS = {
    "(": ")",
    "[": "]",
    "{": "}",
    '"': '"',
    "'": "'",
    "`": "`",
}

ROWS: dict[str, list[str]] = {
    "python": [
        "def",
        "class",
        "if",
        "elif",
        "else",
        "for",
        "while",
        "try",
        "import",
        "from",
        "return",
        ":",
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        '"',
        "'",
        "#",
        "=",
        "==",
        "!=",
    ],
    "javascript": [
        "function",
        "const",
        "let",
        "=>",
        "if",
        "else",
        "for",
        "return",
        "import",
        "export",
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        '"',
        "'",
        "`",
        ";",
        "=",
        "===",
        "!=",
    ],
    "typescript": [
        "function",
        "const",
        "let",
        "=>",
        "if",
        "else",
        "for",
        "return",
        "import",
        "export",
        "type",
        "interface",
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        '"',
        "'",
        "`",
        ";",
        "=",
        "===",
        "!=",
    ],
    "html": [
        "<",
        ">",
        "/",
        "=",
        '"',
        "div",
        "span",
        "p",
        "a",
        "img",
        "class",
        "id",
        "<!--",
        "-->",
    ],
    "css": [
        "{",
        "}",
        ":",
        ";",
        "#",
        ".",
        "@media",
        "px",
        "rem",
        "color",
        "margin",
        "padding",
        "display",
    ],
    "markdown": [
        "#",
        "##",
        "**",
        "*",
        "`",
        "```",
        "-",
        "[",
        "]",
        "(",
        ")",
        ">",
        "|",
    ],
    "shell": [
        "if",
        "then",
        "else",
        "fi",
        "for",
        "do",
        "done",
        "|",
        ">",
        ">>",
        "$",
        "${",
        "}",
        '"',
        "'",
        "#",
        "&&",
        "||",
    ],
}

SNIPPETS: dict[str, dict[str, str]] = {
    "python": {
        "def": "def ${1:name}(${2:args}):\n    ${0:pass}",
        "class": "class ${1:Name}:\n    def __init__(self${2:, args}):\n        ${0:pass}",
        "for": "for ${1:item} in ${2:iterable}:\n    ${0:pass}",
        "if": "if ${1:cond}:\n    ${0:pass}",
        "try": "try:\n    ${1:pass}\nexcept ${2:Exception} as ${3:e}:\n    ${0:raise}",
        "with": "with ${1:expr} as ${2:name}:\n    ${0:pass}",
    },
    "javascript": {
        "function": "function ${1:name}(${2:args}) {\n    ${0:// body}\n}",
        "arrow": "(${1:args}) => {\n    ${0:// body}\n}",
        "for": "for (let ${1:i} = 0; ${1:i} < ${2:n}; ${1:i}++) {\n    ${0:// body}\n}",
        "if": "if (${1:cond}) {\n    ${0:// body}\n}",
        "try": "try {\n    ${1:// body}\n} catch (${2:e}) {\n    ${0:// handle}\n}",
        "import": "import ${1:name} from '${2:module}';",
    },
    "typescript": {
        "function": "function ${1:name}(${2:args}): ${3:void} {\n    ${0:// body}\n}",
        "interface": "interface ${1:Name} {\n    ${0:// fields}\n}",
        "type": "type ${1:Name} = ${0:unknown};",
        "for": "for (let ${1:i} = 0; ${1:i} < ${2:n}; ${1:i}++) {\n    ${0:// body}\n}",
        "if": "if (${1:cond}) {\n    ${0:// body}\n}",
    },
    "html": {
        "div": '<div class="${1:cls}">\n    ${0:<!-- content -->}\n</div>',
        "a": '<a href="${1:url}">${0:text}</a>',
        "img": '<img src="${1:src}" alt="${0:alt}">',
        "html5": '<!DOCTYPE html>\n<html>\n<head>\n    <meta charset="utf-8">\n'
        "    <title>${1:title}</title>\n</head>\n<body>\n    ${0:<!-- body -->}\n"
        "</body>\n</html>",
    },
    "css": {
        "media": "@media (${1:max-width}: ${2:600px}) {\n    ${0:/* rules */}\n}",
        "rule": "${1:selector} {\n    ${2:property}: ${0:value};\n}",
    },
    "markdown": {
        "link": "[${1:text}](${0:url})",
        "code": "```${1:lang}\n${0:code}\n```",
        "table": "| ${1:h1} | ${2:h2} |\n| --- | --- |\n| ${0:c1} | ${3:c2} |",
    },
    "shell": {
        "if": "if [ ${1:cond} ]; then\n    ${0::}\nfi",
        "for": "for ${1:f} in ${2:items}; do\n    ${0:cmd}\ndone",
        "func": "${1:name}() {\n    ${0::}\n}",
    },
}


def bracket_pairs() -> dict[str, str]:
    """Auto-close pairs for the soft keyboard. Copy, don't mutate."""
    return dict(BRACKET_PAIRS)


def row_for(language: str) -> list[str]:
    """Extra-keyboard row keys for a language. Copy, don't mutate."""
    return list(ROWS.get(language, ROWS["python"]))


def expand(language: str, trigger: str) -> str | None:
    """Expand a snippet trigger to its body, or None when unknown."""
    return SNIPPETS.get(language, {}).get(trigger)


def triggers(language: str) -> list[str]:
    """Available snippet triggers for a language (for the palette)."""
    return sorted(SNIPPETS.get(language, {}))


def validate_snippets() -> list[str]:
    """Proof over the snippet data: every body scans clean.

    Checks each snippet body for stray ``$`` (only ${n}, ${n:placeholder}
    and $n tab stops are legal) and for balanced braces. Returns a list
    of problem descriptions; an empty list means the data is valid.
    """
    problems: list[str] = []
    for lang, lang_snippets in SNIPPETS.items():
        for trigger, body in lang_snippets.items():
            where = f"{lang}/{trigger}"
            depth = 0
            i = 0
            while i < len(body):
                ch = body[i]
                if ch == "$":
                    m = _TABSTOP.match(body, i)
                    if not m:
                        problems.append(f"{where}: stray '$' at offset {i}")
                        i += 1
                        continue
                    i = m.end()  # whole tab stop consumed; braces are structural
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth < 0:
                        problems.append(f"{where}: unbalanced '}}' at offset {i}")
                        depth = 0
                i += 1
            if depth != 0:
                problems.append(f"{where}: {depth} unclosed '{{'")
    return problems
