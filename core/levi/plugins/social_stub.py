"""Social stub connector — LOCAL LOOPBACK, test/demo only. NO NETWORK.

Purpose: give ``levi king social-post`` a real connector to route
through (blueprint §4: posting must go through ``plugins/registry.py``,
never touch the network from King) without needing real social
credentials. The "transport" of this connector is an in-memory
outbox: ``perform()`` records the payload and returns it. Nothing
leaves the machine — the success message says so explicitly.

Honesty notes (blueprint §1.5, §3):
* ``publish`` is a write operation, so ``requires_confirmation=True``
  is forced at class-definition time — the confirmation gate cannot be
  bypassed, even by King.
* The connector is credentialless by design: ``credential()`` returns
  the ``"loopback"`` sentinel. ``missing_credential`` therefore never
  fires here; the gates that matter (confirmation + loopback) do.
* ``ok=True`` means "the loopback accepted and recorded the payload",
  never "a network post succeeded". The result message and the
  ``loopback: True`` data flag say exactly that.

To post to a REAL platform later, add a connector with a real
transport here (id per platform, e.g. ``"x"``) and map it in
``levi.king.PLATFORM_CONNECTORS``. This stub must never be mistaken
for one — its id and display name say "stub".
"""

from __future__ import annotations

from typing import Any

from .registry import (
    Capability,
    Connector,
    InvalidParams,
    Operation,
    register_connector,
)

#: In-memory outbox: every loopback "post", newest last. Tests assert
#: against this to prove the pipeline reached the connector.
OUTBOX: list[dict[str, Any]] = []


class SocialStubConnector(Connector):
    id = "social-stub"
    display_name = "Social Stub (local loopback — test/demo only)"
    credential_env_var = "LEVI_SOCIAL_STUB_TOKEN"  # accepted, never required
    capabilities = (
        Capability(
            "publish",
            "Accept a social pack into the local loopback outbox",
            write=True,
        ),
    )
    operations = (
        Operation(
            "publish",
            "Record caption+hashtags locally (no network)",
            write=True,
            params=("platform", "caption", "hashtags"),
        ),
    )

    def credential(self) -> str | None:
        # Credentialless by design: the loopback needs no secret.
        return "loopback"

    def perform(
        self,
        operation: str,
        params: dict[str, Any],
        token: str | None,
        transport: Any,
    ) -> Any:
        if operation != "publish":
            raise InvalidParams(
                f"unknown operation {operation!r} for social-stub — nothing recorded."
            )
        platform = str(params.get("platform") or "").strip()
        caption = str(params.get("caption") or "")
        hashtags = params.get("hashtags") or []
        if not platform:
            raise InvalidParams("publish needs a platform — nothing recorded.")
        if not caption.strip():
            raise InvalidParams("publish needs a non-empty caption — nothing recorded.")
        if transport is not None:
            # Tests inject a fake transport here; the loopback defers to it.
            return transport(
                "POST",
                f"/stub/publish/{platform}",
                token,
                {"platform": platform, "caption": caption, "hashtags": hashtags},
            )
        record = {
            "platform": platform,
            "caption": caption,
            "hashtags": list(hashtags),
            "loopback": True,
        }
        OUTBOX.append(record)
        return {
            "loopback": True,
            "platform": platform,
            "caption_chars": len(caption),
            "message": "loopback accepted — payload stayed on this machine; no network post.",
        }


register_connector(SocialStubConnector)
