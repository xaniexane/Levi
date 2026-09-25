"""Shared conventions for the Legion of Anomalies collective.

The "1 is all, all is one" layer in one place: named constants every
workstream reads instead of inventing its own. Local JSON, 127.0.0.1-safe,
stdlib-only. No magic numbers, no silo formats, no private protocols.
"""

from __future__ import annotations

# --- Economics (uproar doctrine: dollar-scale entry, volume over margin) ---
# Platform cut on digital products created AND monetized on-platform.
# Named once here; never hardcode the number elsewhere.
PLATFORM_CUT = 0.12
# Physical-goods cut is OPEN (standing law). Invent nothing: it stays
# explicitly unset until Chauncey sets it.
PLATFORM_CUT_PHYSICAL = None

# --- Locality ---
# This layer never binds, listens, or dials. Local files only.
LOOPBACK_HOST = "127.0.0.1"
NETWORK_BINDS: tuple = ()

# --- Workstream lifecycle (the ternary: everywhere the giants build
# binary, build the skipped third state — not just on/off, but planned) ---
STATUS_PLANNED = "planned"
STATUS_ACTIVE = "active"
STATUS_RETIRED = "retired"
STATUSES = (STATUS_PLANNED, STATUS_ACTIVE, STATUS_RETIRED)

# --- Capability lifecycle (ternary again: exists / planned / retired) ---
CAP_EXISTS = "exists"
CAP_PLANNED = "planned"
CAP_RETIRED = "retired"
CAP_STATUSES = (CAP_EXISTS, CAP_PLANNED, CAP_RETIRED)

# --- Store ---
SCHEMA_VERSION = 1
REGISTRY_FILENAME = "legion-registry.json"
CANON_FILENAME = "legion-canon.json"
DEFAULT_STORE_DIRNAME = ".levi/legion-collective"
STORE_ENV_VAR = "LEGION_COLLECTIVE_STORE"  # full path override, mainly tests

# --- Distribution doctrines, operationalized ---
OPT_IN_DEFAULT = False  # everything opt-in; nothing auto-registers
TELEMETRY = False  # no hidden telemetry, ever
DARK_PATTERNS = False  # inclusion and acceptance, not deceit

# --- Surfaces ---
SURFACE_GENERAL = "general"
SURFACE_ADULT = "adult"  # Plaiground = adult. Echoverse = SFW. NEVER merged.
SURFACES = (SURFACE_GENERAL, SURFACE_ADULT)
