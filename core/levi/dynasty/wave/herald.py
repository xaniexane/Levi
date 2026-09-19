# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Herald — the wave's editions-expansion agent.

Owns "editions expansion". Drafts sector edition manifests — declared,
versioned, auditable — and grows the catalog from the scars: when
sealed work arrives that the current catalog could not place, the
herald drafts that sector's candidate manifest seeded from the
failure's own receipt hash. Candidates are quarantined; nothing
becomes an edition by itself.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent, scrub_text

__all__ = ["Herald"]

_SECTOR_RE = re.compile(r"^[a-z][a-z0-9_]{2,31}$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_MAX_ITEMS = 12
_MAX_ITEM_LEN = 128
_REQUIRED_FIELDS = (
    "edition",
    "sector",
    "version",
    "declared_at",
    "rites",
    "wares",
    "vocabulary",
)

_RESEARCH_MANIFEST = {
    "edition": "LEVI Scientific Research",
    "sector": "scientific_research",
    "version": "1.0.0",
    "rites": [
        "preregister the hypothesis before the first run",
        "publish the method with the result, not after it",
        "replicate before you celebrate",
        "cite the lineage: every claim names its ancestors",
    ],
    "wares": [
        "dataset index",
        "citation graph",
        "experiment ledger",
        "replication queue",
    ],
    "vocabulary": {
        "hypothesis": "a falsifiable claim, stated before the run",
        "replication": "an independent re-run that must agree",
        "preregistration": "the plan, sealed before the data",
        "provenance": "the chain of custody for every number",
    },
}


def _home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical(data: Any) -> bytes:
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".manifest-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, sort_keys=True, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)


def _check_sector(sector: Any) -> str:
    if not isinstance(sector, str) or not _SECTOR_RE.match(sector or ""):
        raise AgentError(
            "sector must be lowercase letters/digits/underscore, 3..32 chars"
        )
    return sector


def _check_version(version: Any) -> str:
    if not isinstance(version, str) or not _VERSION_RE.match(version):
        raise AgentError("version must look like 1.0.0")
    return version


def _version_greater(new: str, old: str) -> bool:
    return tuple(int(p) for p in new.split(".")) > tuple(int(p) for p in old.split("."))


def _check_str_list(items: Any, field: str) -> List[str]:
    if not isinstance(items, list) or not items:
        raise AgentError(f"{field} must be a non-empty list of strings")
    if len(items) > _MAX_ITEMS:
        raise AgentError(f"{field} holds at most {_MAX_ITEMS} items")
    out = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise AgentError(f"{field} items must be non-empty strings")
        clean = scrub_text(item.strip())
        if len(clean) > _MAX_ITEM_LEN:
            raise AgentError(f"{field} item too long")
        out.append(clean)
    return out


def _check_vocabulary(vocab: Any) -> Dict[str, str]:
    if not isinstance(vocab, dict) or not vocab:
        raise AgentError("vocabulary must be a non-empty dict")
    if len(vocab) > _MAX_ITEMS:
        raise AgentError(f"vocabulary holds at most {_MAX_ITEMS} terms")
    out = {}
    for term, meaning in vocab.items():
        if not isinstance(term, str) or not term.strip():
            raise AgentError("vocabulary terms must be non-empty strings")
        if not isinstance(meaning, str) or not meaning.strip():
            raise AgentError("vocabulary meanings must be non-empty strings")
        out[scrub_text(term.strip())] = scrub_text(meaning.strip())
    return out


class Herald(DynastyAgent):
    """Declares the editions, audits them, maps the scars."""

    agent_id = "herald"
    display_name = "Herald"
    owns = "editions expansion"
    first_milestone = "3 new sector editions"
    proficiency = {"editions": 10, "manifests": 9, "general": 6}
    specialties = [
        "sector edition manifests: declared, versioned, auditable",
        "edition rites, wares, and vocabulary",
        "growing the catalog from unplaced work",
    ]
    attributes = [
        {
            "name": "scar atlas",
            "assertion": (
                "when handed the sealed receipt of work the current "
                "catalog could not place, the herald drafts that sector's "
                "candidate manifest seeded from the receipt's own hash — "
                "deterministic, citing its wound, and quarantined as a "
                "candidate: the catalog grows where it bled, never by "
                "roadmap, and nothing self-promotes to an edition."
            ),
        }
    ]

    def __init__(self, home: Optional[Path] = None) -> None:
        super().__init__(home)
        base = (home or _home()) / "dynasty" / "agents" / self.agent_id
        self._manifests_dir = base / "manifests"
        self._candidates_dir = base / "candidates"
        self._lock = threading.Lock()
        # PURGE-1: the shared receipt minter is not thread-safe (concurrent
        # minters can duplicate sequence numbers). Serialize task sealing
        # per agent instance until the DNA owns a lock of its own.
        self._task_lock = threading.Lock()

    def do_task(
        self,
        kind: str,
        payload: Dict[str, Any],
        task: str = "",
        verify: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        with self._task_lock:
            return super().do_task(kind, payload, task=task, verify=verify)

    # -- manifest core --------------------------------------------------
    def _manifest_path(self, sector: str) -> Path:
        return self._manifests_dir / f"{sector}.json"

    def _read_manifest(self, sector: str) -> Dict[str, Any]:
        path = self._manifest_path(sector)
        if not path.is_file():
            raise AgentError(f"no manifest declared for sector {sector!r}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise AgentError(f"manifest unreadable: {exc}") from exc
        return data

    @staticmethod
    def _seal(body: Dict[str, Any]) -> str:
        return hashlib.sha256(_canonical(body)).hexdigest()

    def draft_manifest(
        self,
        sector: str,
        rites: List[str],
        wares: List[str],
        vocabulary: Dict[str, str],
        version: str = "1.0.0",
        edition: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Declare (or re-declare, at a higher version) a sector edition."""
        sector = _check_sector(sector)
        version = _check_version(version)
        clean_rites = _check_str_list(rites, "rites")
        clean_wares = _check_str_list(wares, "wares")
        clean_vocab = _check_vocabulary(vocabulary)
        clean_edition = scrub_text(
            (edition or f"LEVI {sector.replace('_', ' ').title()}").strip()
        )
        if not clean_edition:
            raise AgentError("edition name must be non-empty")
        with self._lock:
            path = self._manifest_path(sector)
            if path.is_file():
                old = json.loads(path.read_text(encoding="utf-8"))
                old_version = str(old.get("version", "0.0.0"))
                if not _version_greater(version, old_version):
                    raise AgentError(
                        f"version must increase: {version} <= {old_version}"
                    )
            body = {
                "edition": clean_edition,
                "sector": sector,
                "version": version,
                "declared_at": _utc_now(),
                "rites": clean_rites,
                "wares": clean_wares,
                "vocabulary": clean_vocab,
                "audits": [],
            }
            manifest = dict(body)
            manifest["manifest_hash"] = self._seal(body)
            _atomic_write_json(path, manifest)
        self.note(f"declared edition {sector} v{version}")
        return manifest

    def audit(self, sector: str) -> Dict[str, Any]:
        """Audit a manifest against its own declaration.

        A tampered manifest is declared VOID — loudly — never silently
        repaired, never scored.
        """
        sector = _check_sector(sector)
        with self._lock:
            manifest = self._read_manifest(sector)
            body = {k: v for k, v in manifest.items() if k != "manifest_hash"}
            problems: List[str] = []
            for field in _REQUIRED_FIELDS:
                if field not in manifest:
                    problems.append(f"missing field: {field}")
            if not _VERSION_RE.match(str(manifest.get("version", ""))):
                problems.append("bad version")
            if manifest.get("manifest_hash") != self._seal(body):
                problems.append("hash mismatch — manifest tampered")
            verdict = "void" if problems else "sound"
            record = {
                "at": _utc_now(),
                "verdict": verdict,
                "problems": problems,
            }
            manifest.setdefault("audits", []).append(record)
            if verdict == "sound":
                # re-seal: the audit record is part of the declaration now
                new_body = {k: v for k, v in manifest.items() if k != "manifest_hash"}
                manifest["manifest_hash"] = self._seal(new_body)
            _atomic_write_json(self._manifest_path(sector), manifest)
        self.note(f"audited {sector}: {verdict}")
        return {"sector": sector, "verdict": verdict, "problems": problems}

    def list_manifests(self) -> List[Dict[str, Any]]:
        """Every declared edition."""
        out = []
        if self._manifests_dir.is_dir():
            for path in sorted(self._manifests_dir.glob("*.json")):
                try:
                    out.append(json.loads(path.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, OSError):
                    continue
        return out

    # -- the scar atlas -------------------------------------------------
    def _receipts_dir(self) -> Path:
        return (self._home) / "dynasty" / "receipts"

    def propose_from_failure(self, receipt_hash: str) -> Dict[str, Any]:
        """Draft a candidate edition manifest from a sealed receipt of
        unplaced work. Deterministic: the same receipt always yields
        the same draft, citing its own wound."""
        if not isinstance(receipt_hash, str) or not re.fullmatch(
            r"[0-9a-f]{64}", receipt_hash
        ):
            raise AgentError("propose_from_failure needs a 64-hex receipt hash")
        receipts_dir = self._receipts_dir()
        receipt: Optional[Dict[str, Any]] = None
        if receipts_dir.is_dir():
            for path in receipts_dir.glob(f"{receipt_hash[:16]}.json"):
                try:
                    candidate = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if candidate.get("receipt_hash") == receipt_hash:
                    receipt = candidate
                    break
        if receipt is None:
            raise AgentError(f"no sealed receipt {receipt_hash[:16]}… on file")
        payload = receipt.get("payload") or {}
        domain = (
            payload.get("domain")
            or payload.get("agent")
            or str(receipt.get("kind", "unplaced"))
        )
        sector = re.sub(r"[^a-z0-9]+", "_", str(domain).lower()).strip("_")
        if not _SECTOR_RE.match(sector):
            sector = "unplaced_sector"
        draft = {
            "edition": f"LEVI {sector.replace('_', ' ').title()} (candidate)",
            "sector": sector,
            "version": "0.0.1-scar",
            "status": "candidate",
            "seed_receipt": receipt_hash,
            "derived_from": str(receipt.get("kind", "")),
            "derived_domain": str(domain),
            "declared_at": str(receipt.get("created_at", "")),
            "rites": ["name the wound before the remedy"],
            "wares": ["scar record"],
            "vocabulary": {"wound": "the sealed receipt this draft grew from"},
        }
        with self._lock:
            _atomic_write_json(self._candidates_dir / f"{sector}.json", draft)
        self.note(f"scar draft for {sector} from {receipt_hash[:16]}")
        return draft

    def list_candidates(self) -> List[Dict[str, Any]]:
        """Candidate drafts — quarantined, never editions."""
        out = []
        if self._candidates_dir.is_dir():
            for path in sorted(self._candidates_dir.glob("*.json")):
                try:
                    out.append(json.loads(path.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, OSError):
                    continue
        return out

    # -- domain dispatch ----------------------------------------------
    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        shape = task.get("shape", "echo")
        if shape == "draft_manifest":
            return self.draft_manifest(
                task.get("sector", ""),
                task.get("rites", []),
                task.get("wares", []),
                task.get("vocabulary", {}),
                version=task.get("version", "1.0.0"),
                edition=task.get("edition"),
            )
        if shape == "audit":
            return self.audit(task.get("sector", ""))
        if shape == "propose_from_failure":
            return self.propose_from_failure(task.get("receipt_hash", ""))
        if shape == "manifests":
            return {"manifests": self.list_manifests()}
        if shape == "candidates":
            return {"candidates": self.list_candidates()}
        return super().handle(task)

    # -- first green task ----------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        spec = _RESEARCH_MANIFEST

        def verify(payload: Dict[str, Any]) -> None:
            manifest = payload.get("manifest", {})
            body = {k: v for k, v in manifest.items() if k != "manifest_hash"}
            if manifest.get("manifest_hash") != self._seal(body):
                raise AgentError("manifest hash drifted between draft and seal")
            if manifest.get("sector") != "scientific_research":
                raise AgentError("wrong sector sealed")

        manifest = self.draft_manifest(
            spec["sector"],
            spec["rites"],
            spec["wares"],
            spec["vocabulary"],
            version=spec["version"],
            edition=spec["edition"],
        )
        receipt = self.do_task(
            "wave.first_task",
            {
                "manifest": manifest,
                "declared": True,
                "versioned": manifest["version"],
                "auditable": True,
            },
            task="herald:first",
            verify=verify,
        )
        return receipt
