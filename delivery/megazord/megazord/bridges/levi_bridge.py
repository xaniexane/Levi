"""
L.W.P. ↔ Levi Core Bridge

Provides the roundtrip from an incoming L.W.P. envelope (HTTP, WS, etc.)
into a Levi-interpretable dict, and back out to a reaction envelope.

Usage:
    from levi_bridge import LeviBridge
    bridge = LeviBridge(persona="alpha")
    # ── inbound (workspace → Levi) ─────────────────────────────────
    levi_event = bridge.dispatch(raw_envelope)   # validates + maps to Levi event
    # ── outbound (Levi → workspace) ─────────────────────────────────
    envelope = bridge.build(
        msg_type="action",
        payload={"intent": "write_file", "target": "/tmp/out.txt", "args": {"body": "hello"}},
        soul={"joy": 0.8, "trust": 0.9, "fear": 0.0, "surprise": 0.1, "sadness": 0.0}
    )
    # ── reaction ────────────────────────────────────────────────────
    reaction = bridge.react(correlation_id=envelope["id"], status="ok", body={"path": "/tmp/out.txt"})
"""

import uuid, json, datetime
from typing import Optional

# ── Internal Levi event types (what Levi Core consumes) ───────────────────────
LEVI_EVENT_TYPES = {
    "prompt",   # user / system input
    "sync",      # bulk catch-up
    "reaction",  # result of a previously dispatched action
}


class LeviBridgeError(Exception):
    pass


class LeviBridge:
    VERSION = "0.1"

    def __init__(self, persona: str = "alpha", workspace: str = "omega"):
        self.persona  = persona          # e.g. "alpha", "cybrus", "echo"
        self.workspace = workspace        # e.g. "omega", "browser_ext"
        self._handlers = {}               # msg_type → callable

    # ── Inbound: envelope → Levi event ───────────────────────────────────────

    def dispatch(self, envelope: dict) -> dict:
        """
        Validate an inbound L.W.P. envelope and map it to a Levi-readable event dict.
        Raises LeviBridgeError on validation failure.
        """
        self._validate_envelope(envelope)
        msg_type = envelope["type"]

        if msg_type not in LEVI_EVENT_TYPES:
            raise LeviBridgeError(
                f"Unsupported inbound message type: {msg_type!r}"
            )

        event = {
            "event_id":   envelope["id"],
            "event_type": msg_type,
            "ts":         envelope["ts"],
            "from":       envelope["from"],
            "payload":    envelope["payload"],
            "soul":       envelope.get("soul"),
            "raw":        envelope,
        }

        # Route to registered handler if any
        handler = self._handlers.get(msg_type)
        if handler:
            handler(event)

        return event

    # ── Outbound: Levi event → envelope ──────────────────────────────────────

    def build(
        self,
        msg_type: str,
        payload: dict,
        soul: Optional[dict] = None,
        to: Optional[str] = None,
        _id: Optional[str] = None,
    ) -> dict:
        """
        Build a L.W.P. envelope from Levi output.
        msg_type: one of thought|prompt|action|reaction|state|sync
        """
        now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        envelope = {
            "lwp":    self.VERSION,
            "id":     _id or str(uuid.uuid4()),
            "ts":     now,
            "from":   f"levi.persona.{self.persona}",
            "to":     to or f"workspace.{self.workspace}",
            "type":   msg_type,
            "payload": payload,
        }
        if soul:
            envelope["soul"] = self._clamp_soul(soul)
        return envelope

    def build_action(
        self,
        intent: str,
        target: str,
        args: dict,
        soul: Optional[dict] = None,
        priority: str = "normal",
    ) -> dict:
        """Convenience: build a typed action envelope."""
        env = self.build(
            msg_type="action",
            payload={"intent": intent, "target": target, "args": args, "priority": priority},
            soul=soul,
        )
        env["payload"]["correlation_id"] = env["id"]
        return env

    def build_thought(self, text: str, soul: Optional[dict] = None) -> dict:
        """Emit a thought envelope (Levi internal monologue stream)."""
        return self.build(msg_type="thought", payload={"text": text}, soul=soul)

    def build_state(self, soul_delta: dict, memory_delta: Optional[dict] = None) -> dict:
        """Emit a state envelope (soul + memory snapshot delta)."""
        payload = {"soul_delta": self._clamp_soul(soul_delta)}
        if memory_delta:
            payload["memory_delta"] = memory_delta
        return self.build(msg_type="state", payload=payload)

    # ── Reaction ───────────────────────────────────────────────────────────────

    def react(
        self,
        correlation_id: str,
        status: str = "ok",
        body: Optional[dict] = None,
        error: Optional[str] = None,
        soul: Optional[dict] = None,
    ) -> dict:
        """Build a reaction envelope in response to an action's correlation_id."""
        if status == "error" and not error:
            raise LeviBridgeError("react() called with status=error but no error message")
        payload = {"status": status, "correlation_id": correlation_id}
        if body:
            payload["body"] = body
        if error:
            payload["error"] = error
        return self.build(msg_type="reaction", payload=payload, soul=soul)

    # ── Handler registry ───────────────────────────────────────────────────────

    def on(self, msg_type: str):
        """Decorator to register a handler for a message type."""
        def decorator(fn):
            self._handlers[msg_type] = fn
            return fn
        return decorator

    # ── Validation ─────────────────────────────────────────────────────────────

    REQUIRED_ENVELOPE_FIELDS = ["lwp", "id", "ts", "from", "to", "type", "payload"]

    def _validate_envelope(self, env: dict):
        for field in self.REQUIRED_ENVELOPE_FIELDS:
            if field not in env:
                raise LeviBridgeError(f"Missing required envelope field: {field!r}")

        major = env["lwp"].split(".")[0]
        if major != self.VERSION.split(".")[0]:
            raise LeviBridgeError(
                f"Incompatible L.W.P. major version: got {env['lwp']!r}, expected {self.VERSION!r}"
            )

        if env["type"] not in {
            "thought", "prompt", "action", "reaction", "state", "sync"
        }:
            raise LeviBridgeError(f"Invalid message type: {env['type']!r}")

    SOUL_AXES = ["joy", "trust", "fear", "surprise", "sadness"]

    def _clamp_soul(self, soul: dict) -> dict:
        clamped = {}
        for axis in self.SOUL_AXES:
            val = float(soul.get(axis, 0.0))
            clamped[axis] = max(-1.0, min(1.0, val))
        return clamped

    # ── Serialization helpers ───────────────────────────────────────────────────

    def to_json(self, envelope: dict) -> bytes:
        return json.dumps(envelope, indent=2, sort_keys=True).encode("utf-8")

    def from_json(self, data: bytes) -> dict:
        return json.loads(data.decode("utf-8"))

    def parse(self, raw: bytes) -> dict:
        """Parse raw HTTP body bytes into a Levi event dict."""
        env = self.from_json(raw)
        return self.dispatch(env)


if __name__ == "__main__":
    # ── Demo ──────────────────────────────────────────────────────────────────
    bridge = LeviBridge(persona="cybrus")

    # Simulate an inbound prompt envelope
    inbound = {
        "lwp":   "0.1",
        "id":    str(uuid.uuid4()),
        "ts":    "2026-09-04T12:00:00Z",
        "from":  "workspace.omega",
        "to":    "levi.persona.cybrus",
        "type":  "prompt",
        "payload": {"text": "Run a full diagnostic on the system."},
        "soul":  {"joy": 0.6, "trust": 0.7, "fear": 0.1, "surprise": 0.3, "sadness": 0.0},
    }
    event = bridge.dispatch(inbound)
    print(f"[IN]  Levi event: {event['event_type']!r} | soul joy={event['soul']['joy']}")

    # Levi thinks about it
    thought = bridge.build_thought(
        "Running deep system diagnostic before touching anything sensitive."
    )
    print(f"[OUT] Thought → {thought['id']}")

    # Levi decides to run a diagnostic action
    action = bridge.build_action(
        intent="system.diagnostic",
        target="omega.os",
        args={"scope": "full"},
        soul={"joy": 0.5, "trust": 0.6, "fear": 0.2, "surprise": 0.1, "sadness": 0.0},
        priority="high",
    )
    print(f"[OUT] Action correlation_id={action['payload']['correlation_id']}")

    # Simulate workspace reaction
    reaction = bridge.react(
        correlation_id=action["id"],
        status="ok",
        body={"nodes_checked": 14, "issues_found": 0},
    )
    print(f"[OUT] Reaction → {reaction['payload']['status']}")

    print("\n✓ LeviBridge demo complete.")
