"""Cloud-safe tool profile for LEVI-as-cloud (LEVI-original).

The agent server runs the full tool registry for the owner's master
token, but API keys get a **default-deny** subset: read-only tools with
no host mutation, no access to the owner's private state, and no
arbitrary network egress. The profile is enforced server-side by key
type — a client can never claim a wider profile.

ALLOWLIST (the only tools an API key's agent may call):

    affect_detect, affect_state   self-reported affect state (no side effects)
    capabilities                  the capability atlas (read-only)
    course_brief, course_search   ingested course knowledge (read-only)
    lab_footprint, lab_scenario   lab math + scenario playback (read-only)
    news_latest, news_search      public news corpus (read-only)
    skill_list, skill_load        skill catalog + playbook text (read-only)
    web_search                    search-result snippets (read-only)

DENYLIST (owner token only), with reasons:

    shell_exec                    arbitrary host command execution
    file_write, file_edit         arbitrary file write on the server host
    file_read                     reads the server owner's files
    memory_read, memory_write     the owner's private memory store
    schedule_add, schedule_list,
    schedule_remove               the owner's schedule
    delegate                      spawns subagents outside this profile
                                  (privilege-boundary bypass)
    http_request, web_fetch       arbitrary network egress (SSRF surface)

``build_cloud_registry()`` constructs a fresh registry containing
exactly the allowlist, copied from the default registry so tool
implementations stay identical to the owner's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from levi.agent.tools import ToolRegistry

CLOUD_SAFE_TOOLS: frozenset[str] = frozenset(
    {
        "affect_detect",
        "affect_state",
        "capabilities",
        "course_brief",
        "course_search",
        "lab_footprint",
        "lab_scenario",
        "news_latest",
        "news_search",
        "skill_list",
        "skill_load",
        "web_search",
    }
)

# Everything known at the time of writing that is NOT cloud-safe, kept
# as documentation so a newly added tool is a conscious decision.
CLOUD_DENIED_TOOLS: frozenset[str] = frozenset(
    {
        "shell_exec",
        "file_write",
        "file_edit",
        "file_read",
        "memory_read",
        "memory_write",
        "schedule_add",
        "schedule_list",
        "schedule_remove",
        "delegate",
        "http_request",
        "web_fetch",
    }
)


def build_cloud_registry() -> "ToolRegistry":
    """A registry with exactly :data:`CLOUD_SAFE_TOOLS`."""
    from levi.agent.tools import ToolRegistry, build_default_registry

    full = build_default_registry()
    restricted = ToolRegistry()
    for tool in full.list():
        if tool.name in CLOUD_SAFE_TOOLS:
            restricted.register(tool)
    return restricted


def is_cloud_safe(tool_name: str) -> bool:
    return tool_name in CLOUD_SAFE_TOOLS
