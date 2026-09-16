"""LEVI Packs — scoped knowledge packs the user owns.

REMIX DELTA: Anthropic's project-knowledge pattern (folder + instructions
as persistent context) is a cloud feature: your context lives on their
servers, inside their product, under their retention policy. LEVI inverts
it: the pack is a *folder on your disk* in an open format
(manifest.json + markdown + content files), assembled locally with
explicit scoping rules you wrote, in an order you can inspect, with
provenance headers on every section so the model always knows which pack
said what. No upload, no retention policy, no lock-in — move the folder
to any machine and it works.

What it adds that the giant refuses: context as portable files instead
of context as a SaaS feature.
"""

from __future__ import annotations

SHELF = {
    "name": "packs",
    "summary": (
        "Scoped knowledge packs: user-owned folders (manifest + "
        "instructions + content) assembled into scoped context by "
        "explicit project/path/tag rules, all local."
    ),
    "items": [
        {"id": "pack-init", "kind": "command",
         "summary": "Create a new pack folder with manifest + instructions.",
         "invoke": "python -m levi.packs init NAME [--scope-always]"},
        {"id": "pack-list", "kind": "command",
         "summary": "List packs with their scope rules.",
         "invoke": "python -m levi.packs list"},
        {"id": "pack-show", "kind": "command",
         "summary": "Show a pack's manifest, instructions, and content files.",
         "invoke": "python -m levi.packs show NAME"},
        {"id": "pack-assemble", "kind": "command",
         "summary": "Assemble scoped context for a project/cwd/tags.",
         "invoke": "python -m levi.packs assemble [--project SLUG] [--cwd PATH]"},
        {"id": "pack-validate", "kind": "command",
         "summary": "Validate every pack's manifest.",
         "invoke": "python -m levi.packs validate"},
    ],
}
