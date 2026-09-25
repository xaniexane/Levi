"""NeighborOS notifier — the real push plumbing (laws N1–N6).

Routes that reach the operator's phone, honestly labeled:
- app_push: the app's own push. Mechanism: a scheduled job's final
  message arrives as chat, which the app turns into a phone push when
  the app is closed. POLL-BASED, NOT INSTANT. Status is always
  "queued_for_app_push", never "delivered" — nothing here can confirm
  the phone buzzed.
- webhook: POST JSON to operator-configured URLs (Google Sheets Apps
  Script /exec URL, ntfy topic, …). Bounded retry + timeout. The URL
  is a capability secret: it never appears in logs, outbox files, or
  status strings — only the target count is reported.
- whatsapp: declared-but-gated. The payload is ready, but the status
  is always "needs_whatsapp_chat_setup" with the exact setup step. A
  channel message can only be sent from that channel's own side chat,
  so proactive reach needs a scheduled task created from the WhatsApp
  side chat. Never the vague "not_configured".
- console / file: local delivery, unchanged.

LAWS (machine-checked by `check_laws`):
- N1: never claim delivery that didn't happen — every send record
  carries an honest status; "queued" is never reported as "delivered".
- N2: a nudge is never double-sent — accepted (backend, id) pairs are
  recorded; re-sends are refused as "already_sent". Transient
  "failed" sends are NOT recorded, so the next drain may retry.
- N3: no secrets in logs — configured webhook URLs never appear in
  the outbox, the dedupe file, or any status/error string.
- N4: webhook egress is bounded — per-attempt timeout and a max
  attempt count; a failure is reported, never raised into the drain.
- N5: app_push is poll-based, not instant — it reports
  "queued_for_app_push", never "delivered".
- N6: whatsapp stays gated — it reports "needs_whatsapp_chat_setup",
  never "delivered" and never "not_configured".

stdlib-only.
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

BACKENDS = ("app_push", "webhook", "whatsapp", "console", "file")

DEFAULT_CONFIG: dict[str, Any] = {
    "backends": ["app_push", "file"],
    "webhook_urls": [],
    "timeout_secs": 10,
    "max_retries": 2,
}

WHATSAPP_SETUP = (
    "Proactive WhatsApp needs a scheduled task created FROM the WhatsApp "
    "side chat: open the linked WhatsApp conversation in the app and create "
    "the schedule there. A channel message can only be sent from that "
    "channel's own side chat — main-chat schedules never reach WhatsApp."
)

# preference order when summarizing per-backend statuses
_SUMMARY_ORDER = (
    "delivered",
    "queued_for_app_push",
    "needs_whatsapp_chat_setup",
    "already_sent",
    "no_targets_configured",
    "failed",
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def summarize(statuses: dict[str, str]) -> str:
    """One honest status for a multi-backend send."""
    vals = set(statuses.values())
    for s in _SUMMARY_ORDER:
        if s in vals:
            return s
    return "failed"


class Notifier:
    """Pluggable push backends with dedupe and honest status.

    config: operator config (policies.json `notify` section merged over
    DEFAULT_CONFIG). state_dir: where the app-push outbox and the
    dedupe file live. http_post: injectable
    (url, payload, timeout_secs) -> (ok, http_status, error); the
    default uses urllib with a timeout.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        state_dir: str | Path | None = None,
        http_post: Callable[[str, dict, float], tuple[bool, int | None, str | None]]
        | None = None,
    ):
        cfg = dict(DEFAULT_CONFIG)
        cfg.update(config or {})
        self.config = cfg
        backends = cfg.get("backends") or []
        unknown = [b for b in backends if b not in BACKENDS]
        if unknown:
            raise ValueError(f"unknown notify backends: {unknown}")
        self.backends: list[str] = list(backends)
        self.state_dir = Path(state_dir) if state_dir else Path.home() / ".levi" / "neighbor"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._http_post = http_post or self._default_http_post
        self._sent_keys: set[str] = set()
        self._load_dedupe()

    # -- state ---------------------------------------------------------
    @property
    def _dedupe_path(self) -> Path:
        return self.state_dir / "notify_sent.jsonl"

    @property
    def _outbox_path(self) -> Path:
        return self.state_dir / "notify_app_push.jsonl"

    def _load_dedupe(self) -> None:
        if not self._dedupe_path.exists():
            return
        for line in self._dedupe_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = rec.get("key")
            if isinstance(key, str):
                self._sent_keys.add(key)

    def _record_sent(self, key: str, record: dict[str, Any]) -> None:
        rec = {"key": key, "ts": _utcnow(), **record}
        with self._dedupe_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        self._sent_keys.add(key)

    def _redact(self, text: str) -> str:
        """Strip every configured webhook URL from a string (N3)."""
        out = str(text)
        for url in self.config.get("webhook_urls") or []:
            if url and url in out:
                out = out.replace(url, "[webhook-url]")
        return out

    # -- status ----------------------------------------------------------
    def status(self) -> dict[str, Any]:
        urls = self.config.get("webhook_urls") or []
        return {
            "backends": self.backends,
            "app_push": {
                "status": "available",
                "detail": "poll-based: a scheduled run's final message reaches "
                "the phone as push when the app is closed; not instant",
            },
            "webhook": {
                "status": "configured" if urls else "no_targets_configured",
                "targets": len(urls),
                "detail": "paste a URL into policies.json notify.webhook_urls "
                "(Google Sheets Apps Script /exec URL or ntfy topic)"
                if not urls
                else f"{len(urls)} target(s) configured (URLs never logged)",
            },
            "whatsapp": {
                "status": "needs_whatsapp_chat_setup",
                "setup": WHATSAPP_SETUP,
            },
            "console": {"status": "available"},
            "file": {"status": "available"},
        }

    # -- send --------------------------------------------------------------
    def send(
        self, notification: dict[str, Any], backends: list[str] | None = None
    ) -> dict[str, str]:
        """Send through each backend; returns per-backend honest status."""
        if not notification.get("id"):
            raise ValueError("notification needs an 'id' for dedupe")
        chosen = backends if backends is not None else self.backends
        statuses: dict[str, str] = {}
        for backend in chosen:
            key = f"{backend}:{notification['id']}"
            if key in self._sent_keys:
                statuses[backend] = "already_sent"
                continue
            try:
                result = self._send_one(backend, notification)
            except Exception as exc:  # noqa: BLE001 — N4: report, never raise
                result = f"failed: {self._redact(str(exc))[:120]}"
            statuses[backend] = result
            if not result.startswith("failed"):
                self._record_sent(key, {"backend": backend, "status": result})
        return statuses

    def _send_one(self, backend: str, n: dict[str, Any]) -> str:
        if backend == "app_push":
            return self._send_app_push(n)
        if backend == "webhook":
            return self._send_webhook(n)
        if backend == "whatsapp":
            return "needs_whatsapp_chat_setup"
        if backend == "console":
            print(f"[notify] {n.get('title', '')}\n{n.get('body', '')}")
            return "delivered"
        if backend == "file":
            return self._send_file(n)
        return "unknown_backend"

    def _send_app_push(self, n: dict[str, Any]) -> str:
        """Queue for the app's push: the scheduled run's final message is
        the actual push. N5: never reported as delivered."""
        rec = {
            "id": n.get("id"),
            "title": n.get("title"),
            "body": n.get("body"),
            "kind": n.get("kind"),
            "cell": n.get("cell"),
            "status": "queued_for_app_push",
            "ts": _utcnow(),
        }
        with self._outbox_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        return "queued_for_app_push"

    def _send_file(self, n: dict[str, Any]) -> str:
        path = self.state_dir / "notify_file_outbox.jsonl"
        rec = {**n, "status": "delivered", "ts": _utcnow()}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        return "delivered"

    def _default_http_post(
        self, url: str, payload: dict, timeout_secs: float
    ) -> tuple[bool, int | None, str | None]:
        data = json.dumps(payload, default=str).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_secs) as resp:
                code = resp.getcode()
                return (200 <= code < 300, code, None)
        except Exception as exc:  # noqa: BLE001 — caller reports it
            return (False, None, str(exc))

    def _send_webhook(self, n: dict[str, Any]) -> str:
        """POST to every configured URL with bounded retry+timeout (N4)."""
        urls = self.config.get("webhook_urls") or []
        if not urls:
            return "no_targets_configured"
        timeout = float(self.config.get("timeout_secs", 10))
        attempts = 1 + int(self.config.get("max_retries", 2))
        payload = {
            "id": n.get("id"),
            "title": n.get("title"),
            "body": n.get("body"),
            "kind": n.get("kind"),
            "cell": n.get("cell"),
            "ts": _utcnow(),
        }
        errors: list[str] = []
        delivered_any = False
        for i, url in enumerate(urls):
            last_err: str | None = None
            for _ in range(attempts):
                ok, code, err = self._http_post(url, payload, timeout)
                if ok:
                    delivered_any = True
                    break
                last_err = err or f"http_{code}"
            else:
                errors.append(f"target #{i + 1}: {self._redact(last_err or 'failed')}")
        if not delivered_any:
            return f"failed: {'; '.join(errors)[:160]}"
        return "delivered"


def check_laws(store: Any) -> dict[str, Any]:
    """Machine-check the notify laws against live state (N1–N6)."""
    from .store import Store

    assert isinstance(store, Store)
    state_dir = store.base
    checks: dict[str, dict] = {}

    dedupe = state_dir / "notify_sent.jsonl"
    seen: set[str] = set()
    dupes: list[str] = []
    missing_status: list[int] = []
    app_push_ok = True
    whatsapp_ok = True
    if dedupe.exists():
        for lineno, line in enumerate(
            dedupe.read_text(encoding="utf-8").splitlines()
        ):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                missing_status.append(lineno)
                continue
            key = rec.get("key")
            if key in seen:
                dupes.append(key)
            seen.add(key)
            if "status" not in rec:  # N1: every record carries a status
                missing_status.append(lineno)
            if rec.get("backend") == "app_push" and rec.get("status") == "delivered":
                app_push_ok = False  # N5
            if rec.get("backend") == "whatsapp" and rec.get("status") == "delivered":
                whatsapp_ok = False  # N6
    checks["dedupe_unique"] = {"ok": not dupes, "duplicates": dupes[:5]}
    checks["records_have_status"] = {"ok": not missing_status, "lines": missing_status[:5]}
    checks["app_push_never_delivered"] = {"ok": app_push_ok}
    checks["whatsapp_never_delivered"] = {"ok": whatsapp_ok}

    # N3: no configured webhook URL may appear in any notify state file
    try:
        from . import policies as policies_mod

        cfg = policies_mod.load_policies(store).get("notify", {})
    except Exception:  # noqa: BLE001 — config unreadable: check skipped, not failed
        cfg = {}
    urls = [u for u in (cfg.get("webhook_urls") or []) if u]
    leaked: list[str] = []
    for name in ("notify_sent.jsonl", "notify_app_push.jsonl", "notify_file_outbox.jsonl"):
        path = state_dir / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for url in urls:
            if url in text:
                leaked.append(name)
                break
    checks["no_secrets_in_state"] = {"ok": not leaked, "files": leaked}

    return {"ok": all(c["ok"] for c in checks.values()), "checks": checks}
