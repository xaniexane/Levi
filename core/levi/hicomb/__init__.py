"""Hicomb — the house editor (KFX2 milestone 1: Phase-0 skeleton).

Editor-as-organ, not editor-as-tool: the buffer engine here is the
deterministic, offline, stdlib-only core that the phone UI drives. The
daemon owns the state (sessions, journals); the UI process owns pixels.

What milestone 1 builds (plan M1):
  buffer    open / edit / save, undo / redo, large-file awareness
  highlight deterministic syntax tokens (python, js/ts, html, css,
            markdown, shell) with windowed highlighting for big files
  search    find / replace in-buffer and project-wide, ternary verdicts
  tabs      multi-tab session, file tree, .git detection, JSON session
            state that survives app kills (continuity is the product)
  commands  touch command bar: proposer + verifier twins, fuzzy palette
  snippets  extra-keyboard row: bracket pairs + per-language snippets
  themes    Myspace-style structured theming on every editor surface —
            safe by construction, never raw HTML/JS
  journal   append-only edit journal per project (no hostage data)
  economy   PLATFORM_CUT = 0.12 named constant; entry fee owner-gated
  dock      home-agnostic docking for the builders package (Hicomb-embedded
            vs standalone is GATED ON CHAUNCEY — this package docks either way)

Doctrines encoded here: uproar (Acode/Spck parity — palette, tabs, project
search, snippet rows, Git-aware project shape — plus our exclusives:
offline-first, zero ads, unmetered, daemon-owned state); the ternary
(EXECUTED / ARGS_REVIEW / UNKNOWN_COMMAND, REPLACED / REVIEW_NEEDED /
SKIPPED); the paired mind (CommandBar proposes, CommandVerifier verifies);
no-free-core (entry mechanics raise OwnerGateRequired until Chauncey sets
the price); "1 is all" (local JSON state, stdlib-only, no silo formats).

Local-only. No network calls in any core path. No ads, no meters, no
telemetry — opt-in everything.
"""

from __future__ import annotations

from levi.hicomb.buffer import Buffer, BufferError, Position
from levi.hicomb.commands import (
    Command,
    CommandBar,
    CommandRegistry,
    CommandVerdict,
    CommandVerifier,
    default_registry,
    dispatch,
)
from levi.hicomb.dock import DockReport, builders_available, dock_builders
from levi.hicomb.economy import (
    PLATFORM_CUT,
    OwnerGateRequired,
    collect_entry_fee,
    marketplace_royalty,
)
from levi.hicomb.highlight import (
    TOKEN_KINDS,
    detect_language,
    highlight,
    tokenize,
)
from levi.hicomb.journal import EditJournal, JournalEntry
from levi.hicomb.search import (
    FileVerdict,
    Match,
    ProjectHit,
    find_all,
    project_replace,
    project_search,
    replace_all,
)
from levi.hicomb.snippets import bracket_pairs, expand, row_for
from levi.hicomb.tabs import Session, Tab, file_tree
from levi.hicomb.themes import (
    Theme,
    ThemeError,
    customize,
    export_theme,
    get_theme,
    list_themes,
    theme_from_json,
    validate_theme,
)
from levi.hicomb.pollen import (
    FormatterError,
    format_text,
    language_for_path,
    languages as pollen_languages,
    register as register_formatter,
)
from levi.hicomb.pipeline import SaveResult, save_pipeline
from levi.hicomb.ai import (
    Analysis,
    Completion,
    LocalEngine,
    PairProgrammer,
)
from levi.hicomb.card import (
    CARD_TOKENS,
    GBC_PALETTE,
    gbc_card_theme_data,
    get_gbc_theme,
)
from levi.hicomb.studio import (
    STUDIO_HTML,
    check_panels,
    check_self_contained,
    studio_manifest,
)

__all__ = [
    "PLATFORM_CUT",
    "TOKEN_KINDS",
    "Buffer",
    "BufferError",
    "Command",
    "CommandBar",
    "CommandRegistry",
    "CommandVerdict",
    "CommandVerifier",
    "DockReport",
    "EditJournal",
    "FileVerdict",
    "JournalEntry",
    "Match",
    "OwnerGateRequired",
    "Position",
    "ProjectHit",
    "Session",
    "Tab",
    "Theme",
    "ThemeError",
    "bracket_pairs",
    "builders_available",
    "collect_entry_fee",
    "customize",
    "default_registry",
    "detect_language",
    "dispatch",
    "dock_builders",
    "expand",
    "export_theme",
    "file_tree",
    "find_all",
    "get_theme",
    "highlight",
    "list_themes",
    "marketplace_royalty",
    "project_replace",
    "project_search",
    "replace_all",
    "row_for",
    "theme_from_json",
    "tokenize",
    "validate_theme",
    "Analysis",
    "CARD_TOKENS",
    "Completion",
    "FormatterError",
    "GBC_PALETTE",
    "LocalEngine",
    "PairProgrammer",
    "SaveResult",
    "check_panels",
    "check_self_contained",
    "format_text",
    "gbc_card_theme_data",
    "get_gbc_theme",
    "language_for_path",
    "pollen_languages",
    "register_formatter",
    "save_pipeline",
    "studio_manifest",
]
