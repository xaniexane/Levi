"""Community charters — versioned signed governance + mod action log.

A charter is a plain dict::

    {
      "id": "haven-charter", "community_id": "haven", "version": 3,
      "created_at": ..., "updated_at": ...,
      "rules": [{"id": "r1", "text": "be kind", "added_in_version": 1,
                 "retired_in_version": null}],
      "roles": [{"id": "mod", "name": "Moderator",
                 "permissions": ["warn", "remove", "ban"]}],
      "succession": {"founder": "ada", "successors": ["grace"],
                     "trigger": "founder absence > 90 days"},
      "amendment": {"procedure": "proposal + 72h discussion, 2/3 of mods",
                    "quorum": 2},
      "history": [{"version": 2, "timestamp": ..., "changes": [...],
                   "approvals_claimed": ["ada", "grace"]}],
    }

Signatures: HMAC-SHA256 over canonical JSON with a per-charter founder
key (``~/.levi/charters/<charter-id>.key``, owner-only 0o600).
HONEST SCOPE — a valid signature proves:

- the artifact was produced by whoever holds the founder key, and
- the artifact has not been altered since signing.

It does NOT prove the founder is who they claim to be, that the rules
are just, or that the community consented. Key custody is the
founder's responsibility; ``rotate-key`` re-signs under a new key and
records the rotation in history (there is an inherent trust gap during
rotation — documented, not hidden). Amendment ``approvals_claimed`` are
RECORDED CLAIMS, not cryptographic per-approver proofs.

Mod action log: every action (warn, remove, ban, unban, appeal-decision)
REQUIRES a non-empty reason — no silent moderation. Appeals move
open -> upheld | overturned, decided by a named moderator with a
decision note.

Export format ``levi-charter-export/1``: sections {charter, mod_log,
appeals} + per-section SHA-256 checksums + manifest; import verifies
everything and fails closed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

EXPORT_FORMAT = "levi-charter-export"
EXPORT_VERSION = 1
_SECTIONS = ("charter", "mod_log", "appeals")
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_MOD_ACTIONS = ("warn", "remove", "ban", "unban", "note", "appeal-decision")


def _home() -> Path:
    override = os.environ.get("LEVI_HOME")
    if override:
        return Path(override)
    return Path.home() / ".levi"


def _base() -> Path:
    return _home() / "charters"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_id(value: str, what: str) -> str:
    value = value.strip()
    if not _ID_RE.match(value):
        raise CharterError(f"{what} id must match [A-Za-z0-9_-]{{1,64}}, got {value!r}")
    return value


class CharterError(ValueError):
    """Invalid charter operation or corrupt export."""


# ---------------------------------------------------------------------------
# Canonical JSON + checksums + HMAC
# ---------------------------------------------------------------------------

def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sign(key: bytes, payload: Dict[str, Any]) -> str:
    return hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Charter store
# ---------------------------------------------------------------------------

class CharterStore:
    """Versioned charters, mod logs, and appeals — all local."""

    def __init__(self, base: Optional[Path] = None) -> None:
        self._base = base or _base()
        self._base.mkdir(parents=True, exist_ok=True)

    # -- low-level ------------------------------------------------------
    def _charter_path(self, charter_id: str) -> Path:
        return self._base / f"{_check_id(charter_id, 'charter')}.charter.json"

    def _key_path(self, charter_id: str) -> Path:
        return self._base / f"{_check_id(charter_id, 'charter')}.key"

    def _log_path(self, charter_id: str) -> Path:
        return self._base / f"{_check_id(charter_id, 'charter')}.modlog.json"

    def _load_json(self, path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    def _write_json(self, path: Path, obj: Any) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=2, sort_keys=True))
        tmp.replace(path)

    def _get_key(self, charter_id: str, create: bool = False) -> bytes:
        p = self._key_path(charter_id)
        if p.exists():
            key = p.read_bytes()
        elif create:
            key = os.urandom(32)
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(key)
            try:
                os.chmod(p, 0o600)
            except OSError:
                pass
        else:
            raise CharterError(f"no founder key for charter {charter_id!r}")
        if len(key) < 16:
            raise CharterError("founder key corrupt (too short)")
        return key

    def _load_charter(self, charter_id: str) -> Dict[str, Any]:
        charter_id = _check_id(charter_id, "charter")
        doc = self._load_json(self._charter_path(charter_id), None)
        if doc is None:
            raise CharterError(f"unknown charter {charter_id!r}")
        return doc

    def _save_charter(self, doc: Dict[str, Any]) -> None:
        key = self._get_key(doc["id"])
        doc["updated_at"] = _now()
        body = {k: v for k, v in doc.items() if k != "signature"}
        doc["signature"] = _sign(key, body)
        self._write_json(self._charter_path(doc["id"]), doc)

    # -- charter lifecycle ----------------------------------------------
    def new(self, charter_id: str, community_id: str, founder: str,
            rules: Optional[List[str]] = None) -> Dict[str, Any]:
        charter_id = _check_id(charter_id, "charter")
        community_id = _check_id(community_id, "community")
        founder = founder.strip()
        if not founder:
            raise CharterError("founder must be non-empty")
        if self._charter_path(charter_id).exists():
            raise CharterError(f"charter {charter_id!r} already exists")
        self._get_key(charter_id, create=True)
        doc = {
            "id": charter_id,
            "community_id": community_id,
            "version": 1,
            "created_at": _now(),
            "rules": [{"id": f"r{i+1}", "text": r.strip(),
                       "added_in_version": 1, "retired_in_version": None}
                      for i, r in enumerate(rules or []) if r.strip()],
            "roles": [],
            "succession": {"founder": founder, "successors": [],
                           "trigger": "founder absence > 90 days"},
            "amendment": {"procedure": "proposal + 72h discussion, "
                                       "majority of moderators",
                          "quorum": 1},
            "history": [{"version": 1, "timestamp": _now(),
                         "changes": ["charter founded"],
                         "approvals_claimed": [founder]}],
        }
        self._save_charter(doc)
        self._write_json(self._log_path(charter_id), {"actions": [], "appeals": []})
        return doc

    def add_rule(self, charter_id: str, text: str) -> Dict[str, Any]:
        doc = self._load_charter(charter_id)
        text = text.strip()
        if not text:
            raise CharterError("rule text must be non-empty")
        rid = f"r{len(doc['rules']) + 1}"
        doc["rules"].append({"id": rid, "text": text,
                             "added_in_version": doc["version"],
                             "retired_in_version": None})
        self._save_charter(doc)
        return doc

    def retire_rule(self, charter_id: str, rule_id: str) -> Dict[str, Any]:
        doc = self._load_charter(charter_id)
        rule = next((r for r in doc["rules"] if r["id"] == rule_id), None)
        if rule is None:
            raise CharterError(f"unknown rule {rule_id!r}")
        rule["retired_in_version"] = doc["version"]
        self._save_charter(doc)
        return doc

    def add_role(self, charter_id: str, role_id: str, name: str,
                 permissions: Optional[List[str]] = None) -> Dict[str, Any]:
        doc = self._load_charter(charter_id)
        role_id = _check_id(role_id, "role")
        if any(r["id"] == role_id for r in doc["roles"]):
            raise CharterError(f"role {role_id!r} already exists")
        doc["roles"].append({"id": role_id, "name": name.strip() or role_id,
                             "permissions": list(permissions or [])})
        self._save_charter(doc)
        return doc

    def set_succession(self, charter_id: str, successors: List[str],
                       trigger: Optional[str] = None) -> Dict[str, Any]:
        doc = self._load_charter(charter_id)
        doc["succession"]["successors"] = [s.strip() for s in successors if s.strip()]
        if trigger:
            doc["succession"]["trigger"] = trigger.strip()
        self._save_charter(doc)
        return doc

    def set_amendment(self, charter_id: str, procedure: str,
                      quorum: int) -> Dict[str, Any]:
        doc = self._load_charter(charter_id)
        if quorum < 1:
            raise CharterError("quorum must be >= 1")
        doc["amendment"] = {"procedure": procedure.strip(), "quorum": quorum}
        self._save_charter(doc)
        return doc

    def amend(self, charter_id: str, changes: List[str],
              approvals: List[str]) -> Dict[str, Any]:
        """Bump the charter version. Approvals are RECORDED CLAIMS, not
        cryptographic proofs — the quorum check counts claimed approvers."""
        doc = self._load_charter(charter_id)
        changes = [c.strip() for c in changes if c.strip()]
        approvals = [a.strip() for a in approvals if a.strip()]
        if not changes:
            raise CharterError("amendment needs at least one change description")
        quorum = doc["amendment"]["quorum"]
        if len(set(approvals)) < quorum:
            raise CharterError(
                f"amendment needs {quorum} distinct approvals, got {len(set(approvals))}")
        doc["version"] += 1
        doc["history"].append({"version": doc["version"], "timestamp": _now(),
                               "changes": changes,
                               "approvals_claimed": sorted(set(approvals))})
        self._save_charter(doc)
        return doc

    def rotate_key(self, charter_id: str) -> Dict[str, Any]:
        """Rotate the founder key. Records the rotation in history — the
        trust gap (old key could have signed anything before rotation) is
        documented, not hidden."""
        doc = self._load_charter(charter_id)
        p = self._key_path(charter_id)
        p.unlink(missing_ok=True)
        self._get_key(charter_id, create=True)
        doc["history"].append({"version": doc["version"], "timestamp": _now(),
                               "changes": ["founder key rotated; charter re-signed"],
                               "approvals_claimed": []})
        self._save_charter(doc)
        return doc

    def verify(self, charter_id: str) -> bool:
        """Verify the charter's signature with its founder key."""
        doc = self._load_charter(charter_id)
        key = self._get_key(charter_id)
        body = {k: v for k, v in doc.items() if k != "signature"}
        stored = doc.get("signature", "")
        return hmac.compare_digest(_sign(key, body), stored)

    def get(self, charter_id: str) -> Dict[str, Any]:
        return self._load_charter(charter_id)

    def list(self) -> List[str]:
        return sorted(p.name[:-len(".charter.json")] for p in self._base.glob("*.charter.json"))

    def charter_checksum(self, charter_id: str) -> str:
        doc = self._load_charter(charter_id)
        body = {k: v for k, v in doc.items() if k != "signature"}
        return _sha256(_canonical(body))

    # -- mod action log ---------------------------------------------------
    def _load_log(self, charter_id: str) -> Dict[str, List[Dict[str, Any]]]:
        return self._load_json(self._log_path(charter_id), {"actions": [], "appeals": []})

    def mod_action(self, charter_id: str, moderator_id: str, action: str,
                   target_id: str, reason: str) -> Dict[str, Any]:
        self._load_charter(charter_id)  # validates existence
        if action not in _MOD_ACTIONS:
            raise CharterError(f"action must be one of {sorted(_MOD_ACTIONS)}")
        moderator_id, target_id, reason = (moderator_id.strip(), target_id.strip(),
                                          reason.strip())
        if not moderator_id:
            raise CharterError("moderator id must be non-empty")
        if not target_id:
            raise CharterError("target id must be non-empty")
        if not reason:
            raise CharterError("mod actions REQUIRE a reason — no silent moderation")
        log = self._load_log(charter_id)
        entry = {
            "id": _sha256(f"{charter_id}|{moderator_id}|{action}|{target_id}|{_now()}".encode())[:12],
            "moderator_id": moderator_id, "action": action, "target_id": target_id,
            "reason": reason, "timestamp": _now(),
        }
        log["actions"].append(entry)
        self._write_json(self._log_path(charter_id), log)
        return entry

    def appeal(self, charter_id: str, action_id: str, appellant_id: str,
               text: str) -> Dict[str, Any]:
        self._load_charter(charter_id)
        log = self._load_log(charter_id)
        if not any(a["id"] == action_id for a in log["actions"]):
            raise CharterError(f"unknown mod action {action_id!r}")
        text = text.strip()
        if not text:
            raise CharterError("appeal text must be non-empty")
        entry = {
            "id": _sha256(f"{charter_id}|appeal|{action_id}|{_now()}".encode())[:12],
            "action_id": action_id, "appellant_id": appellant_id.strip(),
            "text": text, "status": "open", "timestamp": _now(),
            "decided_by": None, "decision": None, "decided_at": None,
        }
        log["appeals"].append(entry)
        self._write_json(self._log_path(charter_id), log)
        return entry

    def decide_appeal(self, charter_id: str, appeal_id: str, decided_by: str,
                      decision: str, note: str = "") -> Dict[str, Any]:
        self._load_charter(charter_id)
        if decision not in ("upheld", "overturned"):
            raise CharterError("decision must be 'upheld' or 'overturned'")
        decided_by = decided_by.strip()
        if not decided_by:
            raise CharterError("decided_by must be non-empty")
        log = self._load_log(charter_id)
        ap = next((a for a in log["appeals"] if a["id"] == appeal_id), None)
        if ap is None:
            raise CharterError(f"unknown appeal {appeal_id!r}")
        if ap["status"] != "open":
            raise CharterError(f"appeal {appeal_id!r} already decided")
        ap["status"] = decision
        ap["decided_by"] = decided_by
        ap["decision"] = note.strip()
        ap["decided_at"] = _now()
        self._write_json(self._log_path(charter_id), log)
        return ap

    def mod_log(self, charter_id: str) -> List[Dict[str, Any]]:
        self._load_charter(charter_id)
        return self._load_log(charter_id)["actions"]

    def appeals(self, charter_id: str, only_open: bool = False) -> List[Dict[str, Any]]:
        self._load_charter(charter_id)
        aps = self._load_log(charter_id)["appeals"]
        return [a for a in aps if not only_open or a["status"] == "open"]

    # -- interop with levi.communities --------------------------------------
    def attach(self, charter_id: str, community_id: str) -> Dict[str, str]:
        """Write this charter's reference into the community's governance
        block (levi.communities). The community export then carries the
        charter pointer — governance travels with the community."""
        from levi.communities.model import CommunityStore  # one-directional interop
        doc = self._load_charter(charter_id)
        store = CommunityStore()
        community = store.get(community_id)  # raises if unknown
        ref = {"id": doc["id"], "version": str(doc["version"]),
               "checksum": self.charter_checksum(charter_id)}
        community.governance.charter_ref = ref
        store._write(community)
        return ref

    # -- export / import ------------------------------------------------------
    def export(self, charter_id: str, out_path: Path) -> Path:
        doc = self._load_charter(charter_id)
        log = self._load_log(charter_id)
        sections = {
            "charter": {k: v for k, v in doc.items()},
            "mod_log": log["actions"],
            "appeals": log["appeals"],
        }
        checksums = {n: _sha256(_canonical(sections[n])) for n in _SECTIONS}
        envelope = {
            "format": EXPORT_FORMAT,
            "format_version": EXPORT_VERSION,
            "exported_at": _now(),
            "charter_id": charter_id,
            "sections": sections,
            "checksums": checksums,
            "manifest": _sha256(_canonical(checksums)),
        }
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp.write_text(json.dumps(envelope, indent=2, sort_keys=True))
        tmp.replace(out_path)
        return out_path

    def import_charter(self, in_path: Path, as_id: Optional[str] = None) -> str:
        """Import a verified charter export. Fails closed on any mismatch.
        NOTE: the founder key is NOT in the export (it never leaves the
        founder's machine). Imported charters are re-keyed locally and
        marked as such in history — verify() after import attests the
        LOCAL key, not the original founder. We say so in the history."""
        try:
            envelope = json.loads(Path(in_path).read_text())
        except (json.JSONDecodeError, OSError) as exc:
            raise CharterError(f"cannot read export: {exc}")
        if envelope.get("format") != EXPORT_FORMAT:
            raise CharterError(f"not a LEVI charter export (format={envelope.get('format')!r})")
        if envelope.get("format_version") != EXPORT_VERSION:
            raise CharterError("unsupported charter export version")
        sections, checksums = envelope.get("sections"), envelope.get("checksums")
        if not isinstance(sections, dict) or not isinstance(checksums, dict):
            raise CharterError("export missing sections/checksums")
        for name in _SECTIONS:
            if name not in sections:
                raise CharterError(f"export missing section {name!r}")
            if checksums.get(name) != _sha256(_canonical(sections[name])):
                raise CharterError(f"checksum mismatch in section {name!r}: refused")
        if envelope.get("manifest") != _sha256(_canonical(checksums)):
            raise CharterError("manifest mismatch: checksum table altered")
        charter_id = as_id or envelope.get("charter_id") or ""
        charter_id = _check_id(charter_id, "charter")
        if self._charter_path(charter_id).exists():
            raise CharterError(f"charter {charter_id!r} already exists; import refused "
                               "rather than overwrite")
        doc = sections["charter"]
        doc["id"] = charter_id
        doc.pop("signature", None)
        doc["history"].append({
            "version": doc["version"], "timestamp": _now(),
            "changes": ["imported from portable export; re-keyed locally — "
                        "signature now attests the LOCAL founder key, not the origin key"],
            "approvals_claimed": [],
        })
        self._get_key(charter_id, create=True)
        self._save_charter(doc)
        self._write_json(self._log_path(charter_id),
                         {"actions": sections["mod_log"], "appeals": sections["appeals"]})
        return charter_id

    # -- display --------------------------------------------------------------
    def format_charter(self, charter_id: str) -> str:
        doc = self._load_charter(charter_id)
        sig_ok = self.verify(charter_id)
        lines = [f"=== Charter [{doc['id']}] v{doc['version']} "
                 f"for community '{doc['community_id']}' ===",
                 f"signature: {'VALID' if sig_ok else 'INVALID'} (founder key, HMAC-SHA256)",
                 f"succession: founder={doc['succession']['founder']} "
                 f"successors={','.join(doc['succession']['successors']) or '(none)'}",
                 f"amendment: {doc['amendment']['procedure']} (quorum {doc['amendment']['quorum']})",
                 "rules:"]
        for r in doc["rules"]:
            retired = f" [retired v{r['retired_in_version']}]" if r["retired_in_version"] else ""
            lines.append(f"  [{r['id']}] {r['text']}{retired}")
        lines.append("roles:")
        for r in doc["roles"]:
            lines.append(f"  [{r['id']}] {r['name']} perms={','.join(r['permissions']) or '(none)'}")
        lines.append(f"history: {len(doc['history'])} versions")
        return "\n".join(lines)

    def format_modlog(self, charter_id: str) -> str:
        actions = self.mod_log(charter_id)
        appeals = self.appeals(charter_id)
        lines = [f"=== Mod log [{charter_id}] — {len(actions)} actions, "
                 f"{len([a for a in appeals if a['status']=='open'])} open appeals ==="]
        for a in actions:
            lines.append(f"  [{a['id'][:8]}] {a['moderator_id']} {a['action']} "
                         f"{a['target_id']}: {a['reason'][:70]}")
        for ap in appeals:
            lines.append(f"  appeal [{ap['id'][:8]}] vs [{ap['action_id'][:8]}] "
                         f"by {ap['appellant_id']}: {ap['status']} — {ap['text'][:60]}")
        if not actions and not appeals:
            lines.append("  (empty)")
        return "\n".join(lines)
