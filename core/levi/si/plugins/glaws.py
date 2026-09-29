"""Google plugin G-LAWS — declared up front, machine-checked in tests/test_si_layer.py.

G1 SCOPED-DRIVE
    Code/text files only. The plugin NEVER deletes, trash-empties, or
    changes permissions (nothing-thrown-away law). DriveSession has no
    delete/trash/permissions method at all — the capability does not exist.

G2 EXPLICIT-ONLY
    No background sync, no watchers. Every Drive call originates from an
    explicit invocation (engine call or CLI command the user runs).

G3 HONEST-RECEIPTS
    Every transfer returns {file_id, name, sha256, bytes, timestamp}.
    The cell never claims a transfer it didn't do — it stages files and
    names the engine command that completes the transfer (G6).

G4 SIZE-AND-TYPE GUARD
    Text only; downloads over 1MB are refused before decode; undecodable
    bytes raise instead of being guessed. Google Workspace docs are read
    via export to text/plain and labeled as exports.

G5 ADDITIVE
    New files only, under core/levi/si/plugins/ (engine) and
    core/levi/si/plugins/cells/google-drive/ (cell). No Hicomb, builder,
    buzztunes, or brain core file is modified.

G6 CELL-HONESTY
    The cell cannot reach the Drive API (no exec capability in the
    tricombs contract — verified against caps.ts). It stages the active
    buffer to the outbox via fs-write and tells the user the exact
    engine command to run. It never claims to push/pull itself.

G7 NO-SECRET
    Auth rides the existing connected hatch_gws_cli session. The plugin
    never handles, logs, or stores tokens.
"""

GLAWS = {
    "G1": "SCOPED-DRIVE — no delete/trash/permissions; capability does not exist",
    "G2": "EXPLICIT-ONLY — no background sync; every call is an explicit invocation",
    "G3": "HONEST-RECEIPTS — every transfer returns file_id/name/sha256/bytes/timestamp",
    "G4": "SIZE-AND-TYPE GUARD — text only, 1MB cap, exports labeled",
    "G5": "ADDITIVE — new files only; no core files modified",
    "G6": "CELL-HONESTY — cell stages via fs caps, never claims Drive IO",
    "G7": "NO-SECRET — existing hatch_gws_cli auth; no token handling",
}

# glaw -> test names in tests/test_si_layer.py (proof map)
GLAW_TESTS = {
    "G1": ["test_drive_session_has_no_destructive_methods"],
    "G2": ["test_drive_session_makes_no_calls_on_init"],
    "G3": ["test_drive_transfer_receipts_carry_provenance"],
    "G4": ["test_drive_refuses_oversize_and_binary"],
    "G5": ["test_layer_additive_no_core_patching", "test_google_cell_manifest_validates"],
    "G6": ["test_google_cell_stages_not_transfers"],
    "G7": ["test_drive_session_handles_no_tokens"],
}
