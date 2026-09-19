"""The Forge computer — LEVI's operable machine.

A pure LEVI-native recreation of the sandbox computer: the terminal, the
filesystem, and the tool registry the operators invoke — all behind the
Plan→Preview→Permission→Execute→Verify→Receipt rail, deny-closed, every
action receipted.

What this is and isn't:

* It is NOT the code-execution sandbox (``levi.sandbox``): that runs
  interactive commands with inherited stdio and no receipts. The machine
  captures output, bounds it, and receipts everything.
* It is NOT the agent loop's tool registry (``levi.agent.tools``): that
  registry is coupled to the agent runtime. This one belongs to the Forge,
  stands alone, and refuses unknown tools outright.
* It is NOT a VM or container. The machine is a deny-closed working world:
  one root directory (``~/.levi/forge/machine/``), a persistent working
  directory, its own HOME, and no path ever escapes the root.

Lawful behavior:

* Terminal commands run with ``shell=False`` — a string command is split
  with ``shlex``; ``;``, ``&&`` and friends are literal characters, never
  control operators. Destructive patterns are denied at *plan* time.
* Filesystem writes to an existing path are *refused* until the operator
  has seen a unified-diff preview and granted explicit permission.
  Deletes go to a trash directory (recoverable), never straight to the void.
* Every tool call travels the rail (``levi.forge.rail`` over
  ``levi.policy.gates``). Unknown tools, unapproved proposals, and
  path escapes are deny-closed and the refusal is on the record.

This is an original, from-scratch implementation for LEVI.
Not artificial. Synthetic.
"""

from __future__ import annotations

import difflib
import hashlib
import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..policy.gates import ActionStatus, RiskLevel
from .rail import (
    DeniedError,
    NeedsApprovalError,
    Rail,
    RailError,
    jsonl_sink,
    machine_root,
)

ORIGIN = "levi-forge/computer"

#: Captured command output is bounded; the caller sees this much.
OUTPUT_LIMIT = 32_768
#: Default and maximum command timeouts (seconds).
DEFAULT_TIMEOUT = 30.0
MAX_TIMEOUT = 600.0
#: Filesystem reads are bounded per call.
READ_LIMIT = 200_000

#: Command shapes denied at plan time — even with consent. Substring match
#: over the joined command line, deliberately conservative.
_DENIED_PATTERNS = (
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd ",
    ":(){",
    ":(){ :|:& };:",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "/dev/sda",
    "/dev/nvme",
    "chmod -R 777 /",
)


class MachineError(Exception):
    """Base error for machine violations."""


class PathEscapeError(MachineError):
    """A path tried to leave the machine's working world."""


class OverwriteRefusedError(MachineError):
    """A write targeted an existing path without preview + permission."""


@dataclass
class ToolDef:
    """One operator-invokable tool: its risk, arg schema, and behavior."""

    name: str
    risk: RiskLevel
    blurb: str
    args: List[str]
    reversible: bool = True


# ---------------------------------------------------------------------------
# The machine
# ---------------------------------------------------------------------------


class Machine:
    """LEVI's operable computer, rooted at ``~/.levi/forge/machine/``."""

    def __init__(
        self,
        home: "str | Path | None" = None,
        *,
        rail: Optional[Rail] = None,
        actor: str = "operator",
    ) -> None:
        self.home = home
        self.root = machine_root(home)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.trash_dir = self.root / "trash"
        self.trash_dir.mkdir(exist_ok=True)
        self.rail = rail or Rail(
            receipt_sink=jsonl_sink(self.root / "receipts.jsonl"),
            actor=actor,
        )
        self.cwd = self.workspace  # persistent working directory
        # (rel-path, content-sha256) -> previewed replacement text.
        # overwrite/edit only accept content the operator has previewed.
        self._previews: Dict[tuple, str] = {}
        # proposal_id -> raw tool args (never shown to the operator; content
        # may be large). Stored beside the rail, not inside its artifacts.
        self._args: Dict[str, Dict[str, Any]] = {}
        self._tools: Dict[str, ToolDef] = {}
        self._register_tools()

    # -- paths: deny-closed ------------------------------------------------
    def _resolve(self, path: "str | Path") -> Path:
        """Resolve *path* inside the workspace. Escapes raise PathEscapeError."""
        rel = str(path or "").strip()
        if not rel:
            raise MachineError("path must not be empty")
        if os.path.isabs(rel):
            raise PathEscapeError(f"absolute paths are outside the machine: {rel!r}")
        target = (self.cwd / rel).resolve()
        # Contain within workspace (cwd itself always stays inside workspace).
        try:
            target.relative_to(self.workspace.resolve())
        except ValueError:
            raise PathEscapeError(
                f"path escapes the machine's working world: {rel!r}"
            ) from None
        return target

    def _machine_env(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.root),
            "LEVI_MACHINE": "1",
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        if extra:
            env.update({str(k): str(v) for k, v in extra.items()})
        return env

    # -- tool registry ------------------------------------------------------
    def _register_tools(self) -> None:
        defs = [
            ToolDef(
                "terminal.run",
                RiskLevel.MODERATE,
                "Run a command (no shell); output captured, timeout-bounded.",
                ["argv|cmd", "cwd?", "timeout?", "env?"],
                reversible=False,
            ),
            ToolDef("fs.list", RiskLevel.INFO, "List a directory.", ["path?"]),
            ToolDef(
                "fs.read",
                RiskLevel.INFO,
                "Read a UTF-8 text file.",
                ["path", "max_bytes?"],
            ),
            ToolDef(
                "fs.write",
                RiskLevel.LOW,
                "Write a NEW file. Existing paths are refused — preview first.",
                ["path", "content"],
            ),
            ToolDef(
                "fs.preview_write",
                RiskLevel.INFO,
                "Show the unified diff a write/overwrite/edit would apply. "
                "Writes nothing; required before overwriting.",
                ["path", "content"],
            ),
            ToolDef(
                "fs.overwrite",
                RiskLevel.HIGH,
                "Replace an existing file. Requires a matching preview and "
                "explicit operator approval.",
                ["path", "content", "overwrite"],
            ),
            ToolDef(
                "fs.edit",
                RiskLevel.HIGH,
                "Replace one exact-occurrence match. Requires a matching "
                "preview and explicit operator approval.",
                ["path", "old_text", "new_text"],
            ),
            ToolDef("fs.mkdir", RiskLevel.LOW, "Create directories.", ["path"]),
            ToolDef(
                "fs.delete",
                RiskLevel.HIGH,
                "Move a path to the machine trash (recoverable).",
                ["path"],
                reversible=True,
            ),
            ToolDef(
                "fs.restore",
                RiskLevel.LOW,
                "Restore a trash entry to its original path.",
                ["name"],
            ),
        ]
        for d in defs:
            self._tools[d.name] = d

    def describe_tools(self) -> List[Dict[str, Any]]:
        """The registry the operators invoke: name, risk, args, reversibility."""
        return [
            {
                "name": d.name,
                "risk": int(d.risk),
                "risk_name": d.risk.name,
                "blurb": d.blurb,
                "args": d.args,
                "reversible": d.reversible,
            }
            for d in self._tools.values()
        ]

    # -- rail entry points ---------------------------------------------------
    def propose(self, tool: str, args: Dict[str, Any]) -> str:
        """Plan + preview an action. Unknown tools are deny-closed.

        Returns the proposal id; the preview artifacts (command line, diff)
        are attached for the operator's permission decision.
        """
        tdef = self._tools.get(tool)
        if tdef is None:
            self.rail.deny_closed(
                tool=tool, reason=f"unknown tool {tool!r} — the registry is deny-closed"
            )
        assert tdef is not None  # deny_closed always raises
        handler = self._plan_handlers()[tool]
        description, artifacts, risk = handler(args)
        pid = self.rail.plan(
            tool=tool,
            description=description,
            risk=risk,
            reason=tdef.blurb,
            affected=["machine:" + tool],
            impact=artifacts.get("_impact", ""),
            reversible=tdef.reversible,
            artifacts={k: v for k, v in artifacts.items() if not k.startswith("_")},
        )
        self._args[pid] = dict(artifacts.get("_args", {}))
        return pid

    def preview(self, proposal_id: str) -> Dict[str, Any]:
        return self.rail.preview(proposal_id)

    def approve(self, proposal_id: str, note: str = "") -> None:
        self.rail.approve(proposal_id, note=note)

    def deny(self, proposal_id: str, note: str = "") -> None:
        self.rail.deny(proposal_id, note=note)

    def permit(self, proposal_id: str):
        """Auto-approve INFO/LOW; higher risks await the operator."""
        return self.rail.permit(proposal_id)

    def run(self, proposal_id: str) -> Dict[str, Any]:
        """Execute an approved proposal: verify, then receipt. Returns the receipt."""
        tool = self._tool_of(proposal_id)
        fn, verify = self._run_handlers()[tool]
        receipt = self.rail.execute(proposal_id, lambda: fn(proposal_id), verify=verify)
        out = {
            "receipt_id": receipt.id,
            "outcome": receipt.outcome,
            "verified": receipt.verified,
            "details": receipt.details,
        }
        return out

    def do(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Full rail pass for auto-approvable tools (INFO/LOW).

        Raises :class:`NeedsApprovalError` when the operator must decide —
        the proposal id is in the error; approve it, then call ``run(pid)``.
        """
        pid = self.propose(tool, args)
        decided = self.permit(pid)
        if decided.status == ActionStatus.AWAITING_PERMISSION:
            raise NeedsApprovalError(
                f"{tool} needs explicit operator approval (proposal {pid})"
            )
        return self.run(pid)

    def _tool_of(self, proposal_id: str) -> str:
        pending = self.rail.policy._pending.get(proposal_id)
        if pending is None:
            raise RailError(f"run: unknown proposal {proposal_id!r}")
        # description was stored as "[tool] rest"
        desc = pending.description
        if desc.startswith("["):
            return desc[1:].split("]", 1)[0]
        raise RailError(f"run: cannot determine tool for proposal {proposal_id!r}")

    # -- plan handlers: description + preview artifacts + risk ----------------
    def _plan_handlers(
        self,
    ) -> Dict[str, Callable[[Dict[str, Any]], "tuple[str, Dict[str, Any], RiskLevel]"]]:
        return {
            "terminal.run": self._plan_terminal,
            "fs.list": self._plan_fs_list,
            "fs.read": self._plan_fs_read,
            "fs.write": self._plan_fs_write,
            "fs.preview_write": self._plan_fs_preview,
            "fs.overwrite": self._plan_fs_overwrite,
            "fs.edit": self._plan_fs_edit,
            "fs.mkdir": self._plan_fs_mkdir,
            "fs.delete": self._plan_fs_delete,
            "fs.restore": self._plan_fs_restore,
        }

    def _run_handlers(self):
        return {
            "terminal.run": (self._run_terminal, self._verify_terminal),
            "fs.list": (self._run_fs_list, None),
            "fs.read": (self._run_fs_read, None),
            "fs.write": (self._run_fs_write, self._verify_fs_write),
            "fs.preview_write": (self._run_fs_preview, None),
            "fs.overwrite": (self._run_fs_overwrite, self._verify_fs_write),
            "fs.edit": (self._run_fs_edit, self._verify_fs_write),
            "fs.mkdir": (self._run_fs_mkdir, self._verify_fs_mkdir),
            "fs.delete": (self._run_fs_delete, self._verify_fs_delete),
            "fs.restore": (self._run_fs_restore, self._verify_fs_restore),
        }

    # -- terminal -------------------------------------------------------------
    @staticmethod
    def _argv_of(args: Dict[str, Any]) -> List[str]:
        if "argv" in args and args["argv"] is not None:
            argv = args["argv"]
            if not isinstance(argv, (list, tuple)) or not argv:
                raise MachineError("terminal.run: 'argv' must be a non-empty list")
            return [str(a) for a in argv]
        cmd = str(args.get("cmd") or "").strip()
        if not cmd:
            raise MachineError("terminal.run: 'argv' or 'cmd' is required")
        # No shell, ever: split with shlex so metacharacters stay literal.
        return shlex.split(cmd)

    @staticmethod
    def _timeout_of(args: Dict[str, Any]) -> float:
        timeout = args.get("timeout", DEFAULT_TIMEOUT)
        try:
            timeout = float(timeout)
        except (TypeError, ValueError):
            raise MachineError("terminal.run: 'timeout' must be numeric") from None
        if timeout <= 0 or timeout > MAX_TIMEOUT:
            raise MachineError(
                f"terminal.run: 'timeout' must be in (0, {MAX_TIMEOUT:g}]"
            )
        return timeout

    def _plan_terminal(self, args):
        argv = self._argv_of(args)
        joined = " ".join(argv)
        for pat in _DENIED_PATTERNS:
            if pat in joined:
                self.rail.deny_closed(
                    tool="terminal.run",
                    reason=f"destructive pattern denied at plan time: {pat!r}",
                )
        cwd_arg = args.get("cwd")
        run_cwd = self._resolve(cwd_arg) if cwd_arg else self.cwd
        if not run_cwd.is_dir():
            raise MachineError(f"terminal.run: cwd is not a directory: {cwd_arg!r}")
        timeout = self._timeout_of(args)
        artifacts = {
            "argv": argv,
            "command": joined,
            "cwd": str(run_cwd.relative_to(self.workspace)),
            "timeout": timeout,
            "_impact": f"runs `{joined}` in {run_cwd}, up to {timeout:g}s",
            "_args": {"env": args.get("env")},
        }
        return f"run `{joined}`", artifacts, RiskLevel.MODERATE

    def _run_terminal(self, proposal_id: str):
        art = self.rail._artifacts[proposal_id]
        argv, timeout = art["argv"], art["timeout"]
        run_cwd = self.workspace / art["cwd"]
        env_extra = self._pending_args(proposal_id).get("env")
        started = time.time()
        try:
            proc = subprocess.run(
                argv,
                shell=False,
                cwd=str(run_cwd),
                env=self._machine_env(
                    env_extra if isinstance(env_extra, dict) else None
                ),
                capture_output=True,
                text=True,
                timeout=timeout,
                errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or "") + (exc.stderr or "")
            details = {
                "argv": argv,
                "timeout": timeout,
                "elapsed": round(time.time() - started, 3),
                "output": self._trunc(out),
                "timed_out": True,
            }
            return f"timed out after {timeout:g}s", details
        elapsed = round(time.time() - started, 3)
        out = (proc.stdout or "") + (proc.stderr or "")
        details = {
            "argv": argv,
            "returncode": proc.returncode,
            "elapsed": elapsed,
            "output": self._trunc(out),
            "timed_out": False,
        }
        summary = f"exit {proc.returncode} in {elapsed}s"
        return summary, details

    @staticmethod
    def _verify_terminal(details):
        if details.get("timed_out"):
            return False, "command timed out"
        rc = details.get("returncode")
        return (rc == 0, f"exit code {rc}")

    @staticmethod
    def _trunc(text: str) -> str:
        if len(text) > OUTPUT_LIMIT:
            return (
                text[:OUTPUT_LIMIT] + f"\n…[truncated {len(text) - OUTPUT_LIMIT} chars]"
            )
        return text

    def _pending_args(self, proposal_id: str) -> Dict[str, Any]:
        # Raw tool args live beside the rail (they may carry file content);
        # preview artifacts shown to the operator live in the rail.
        return self._args.get(proposal_id, {})

    # -- filesystem -------------------------------------------------------------
    def _plan_fs_list(self, args):
        target = self._resolve(args.get("path", "."))
        rel = self._rel(target)
        return (
            f"list {rel}",
            {"path": rel, "_impact": f"reads directory {rel}"},
            RiskLevel.INFO,
        )

    def _run_fs_list(self, proposal_id: str):
        target = self._resolve(self.rail._artifacts[proposal_id]["path"])
        if not target.is_dir():
            raise MachineError(f"fs.list: not a directory: {target}")
        entries = []
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            st = child.stat()
            entries.append(
                {
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                }
            )
        return f"{len(entries)} entries in {self._rel(target)}", {"entries": entries}

    def _plan_fs_read(self, args):
        target = self._resolve(args.get("path"))
        rel = self._rel(target)
        return (
            f"read {rel}",
            {"path": rel, "_impact": f"reads file {rel}"},
            RiskLevel.INFO,
        )

    def _run_fs_read(self, proposal_id: str):
        target = self._resolve(self.rail._artifacts[proposal_id]["path"])
        if not target.is_file():
            raise MachineError(f"fs.read: no such file: {target}")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise MachineError(f"fs.read: not UTF-8 text: {target}") from None
        if len(text) > READ_LIMIT:
            text = text[:READ_LIMIT] + f"\n…[truncated {len(text) - READ_LIMIT} chars]"
        return f"read {len(text)} chars from {self._rel(target)}", {"content": text}

    def _diff(self, target: Path, new_text: str) -> str:
        old = target.read_text(encoding="utf-8") if target.is_file() else ""
        if old == new_text:
            return "(no changes)"
        diff = difflib.unified_diff(
            old.splitlines(),
            new_text.splitlines(),
            fromfile="a/" + self._rel(target),
            tofile="b/" + self._rel(target),
            lineterm="",
        )
        body = "\n".join(diff)
        if len(body) > 8000:
            body = body[:8000] + "\n…[diff truncated]"
        return body or "(no changes)"

    def _plan_fs_write(self, args):
        target = self._resolve(args.get("path"))
        if "content" not in args:
            raise MachineError("fs.write: 'content' is required")
        if target.exists():
            raise OverwriteRefusedError(
                f"fs.write: {self._rel(target)} already exists — writes never "
                "overwrite. Run fs.preview_write, get operator approval, then "
                "fs.overwrite."
            )
        content = str(args["content"])
        rel = self._rel(target)
        artifacts = {
            "path": rel,
            "bytes": len(content.encode("utf-8")),
            "_impact": f"creates {rel} ({len(content)} chars)",
            "_args": {"content": content},
        }
        return f"write new file {rel}", artifacts, RiskLevel.LOW

    def _run_fs_write(self, proposal_id: str):
        art = self.rail._artifacts[proposal_id]
        target = self._resolve(art["path"])
        content = self._pending_args(proposal_id)["content"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {self._rel(target)}", {
            "path": art["path"],
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
        }

    @staticmethod
    def _verify_fs_write(details):
        return ("sha256" in details, "sha256 recorded")

    def _plan_fs_preview(self, args):
        target = self._resolve(args.get("path"))
        if "content" not in args:
            raise MachineError("fs.preview_write: 'content' is required")
        content = str(args["content"])
        rel = self._rel(target)
        key = (rel, hashlib.sha256(content.encode("utf-8")).hexdigest())
        self._previews[key] = content
        diff = self._diff(target, content)
        exists = target.exists()
        artifacts = {
            "path": rel,
            "diff": diff,
            "exists": exists,
            "_impact": f"{'replaces' if exists else 'creates'} {rel}",
        }
        return f"preview write to {rel}", artifacts, RiskLevel.INFO

    def _run_fs_preview(self, proposal_id: str):
        art = self.rail._artifacts[proposal_id]
        return f"previewed {art['path']} (nothing written)", {
            "path": art["path"],
            "diff": art["diff"],
            "exists": art["exists"],
        }

    def _require_preview(self, rel: str, content: str) -> None:
        key = (rel, hashlib.sha256(content.encode("utf-8")).hexdigest())
        if key not in self._previews:
            raise OverwriteRefusedError(
                f"no matching preview for {rel} — run fs.preview_write with "
                "exactly this content first, then get operator approval"
            )

    def _plan_fs_overwrite(self, args):
        target = self._resolve(args.get("path"))
        if not target.is_file():
            raise MachineError(
                f"fs.overwrite: no such file {self._rel(target)} — use fs.write for new files"
            )
        if "content" not in args:
            raise MachineError("fs.overwrite: 'content' is required")
        if args.get("overwrite") is not True:
            raise MachineError(
                "fs.overwrite: refusing — pass overwrite=True explicitly to confirm"
            )
        content = str(args["content"])
        rel = self._rel(target)
        self._require_preview(rel, content)
        artifacts = {
            "path": rel,
            "diff": self._diff(target, content),
            "_impact": f"REPLACES {rel}",
            "_args": {"content": content},
        }
        return f"overwrite {rel}", artifacts, RiskLevel.HIGH

    def _run_fs_overwrite(self, proposal_id: str):
        art = self.rail._artifacts[proposal_id]
        target = self._resolve(art["path"])
        content = self._pending_args(proposal_id)["content"]
        target.write_text(content, encoding="utf-8")
        self._previews.pop(
            (art["path"], hashlib.sha256(content.encode("utf-8")).hexdigest()), None
        )
        return f"overwrote {self._rel(target)}", {
            "path": art["path"],
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
        }

    def _plan_fs_edit(self, args):
        target = self._resolve(args.get("path"))
        if not target.is_file():
            raise MachineError(f"fs.edit: no such file: {self._rel(target)}")
        old_text = args.get("old_text")
        new_text = args.get("new_text")
        if old_text is None or new_text is None:
            raise MachineError("fs.edit: 'old_text' and 'new_text' are required")
        old_text, new_text = str(old_text), str(new_text)
        if not old_text:
            raise MachineError("fs.edit: 'old_text' must not be empty")
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise MachineError(f"fs.edit: cannot read: {exc}") from None
        count = text.count(old_text)
        if count == 0:
            raise MachineError("fs.edit: 'old_text' not found in file")
        if count > 1:
            raise MachineError(
                f"fs.edit: 'old_text' occurs {count} times; it must occur "
                "exactly once (narrow the match)"
            )
        replaced = text.replace(old_text, new_text, 1)
        rel = self._rel(target)
        self._require_preview(rel, replaced)
        artifacts = {
            "path": rel,
            "diff": self._diff(target, replaced),
            "_impact": f"edits {rel} (one exact match replaced)",
            "_args": {"replaced": replaced},
        }
        return f"edit {rel}", artifacts, RiskLevel.HIGH

    def _run_fs_edit(self, proposal_id: str):
        art = self.rail._artifacts[proposal_id]
        target = self._resolve(art["path"])
        replaced = self._pending_args(proposal_id)["replaced"]
        target.write_text(replaced, encoding="utf-8")
        self._previews.pop(
            (art["path"], hashlib.sha256(replaced.encode("utf-8")).hexdigest()), None
        )
        return f"edited {self._rel(target)}", {
            "path": art["path"],
            "sha256": hashlib.sha256(replaced.encode()).hexdigest(),
        }

    def _plan_fs_mkdir(self, args):
        target = self._resolve(args.get("path"))
        rel = self._rel(target)
        return (
            f"mkdir {rel}",
            {"path": rel, "_impact": f"creates directory {rel}"},
            RiskLevel.LOW,
        )

    def _run_fs_mkdir(self, proposal_id: str):
        target = self._resolve(self.rail._artifacts[proposal_id]["path"])
        target.mkdir(parents=True, exist_ok=True)
        return f"created {self._rel(target)}", {"path": self._rel(target)}

    @staticmethod
    def _verify_fs_mkdir(details):
        return (True, "mkdir is idempotent")

    def _plan_fs_delete(self, args):
        target = self._resolve(args.get("path"))
        if not target.exists():
            raise MachineError(f"fs.delete: no such path: {self._rel(target)}")
        rel = self._rel(target)
        artifacts = {
            "path": rel,
            "_impact": f"moves {rel} to the machine trash (recoverable via fs.restore)",
        }
        return f"delete {rel} → trash", artifacts, RiskLevel.HIGH

    def _run_fs_delete(self, proposal_id: str):
        art = self.rail._artifacts[proposal_id]
        target = self._resolve(art["path"])
        stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
        safe = target.name.replace("/", "_")
        dest = self.trash_dir / f"{stamp}__{safe}"
        i = 0
        while dest.exists():
            i += 1
            dest = self.trash_dir / f"{stamp}__{safe}.{i}"
        target.rename(dest)
        (dest.parent / (dest.name + ".origin")).write_text(
            art["path"], encoding="utf-8"
        )
        return f"trashed {art['path']}", {
            "path": art["path"],
            "trash_name": dest.name,
        }

    @staticmethod
    def _verify_fs_delete(details):
        return ("trash_name" in details, "trash entry recorded")

    def _plan_fs_restore(self, args):
        name = str(args.get("name") or "").strip()
        if not name or "/" in name or name.startswith("."):
            raise MachineError("fs.restore: 'name' must be a trash entry name")
        entry = self.trash_dir / name
        if not entry.exists():
            raise MachineError(f"fs.restore: no such trash entry: {name!r}")
        origin_file = self.trash_dir / (name + ".origin")
        origin = (
            origin_file.read_text(encoding="utf-8").strip()
            if origin_file.exists()
            else name
        )
        artifacts = {
            "name": name,
            "origin": origin,
            "_impact": f"restores trash entry {name} to {origin}",
        }
        return f"restore {name}", artifacts, RiskLevel.LOW

    def _run_fs_restore(self, proposal_id: str):
        art = self.rail._artifacts[proposal_id]
        entry = self.trash_dir / art["name"]
        target = self._resolve(art["origin"])
        if target.exists():
            raise MachineError(
                f"fs.restore: {self._rel(target)} already exists — move it aside first"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        entry.rename(target)
        origin_file = self.trash_dir / (art["name"] + ".origin")
        if origin_file.exists():
            origin_file.unlink()
        return f"restored {art['origin']}", {"path": art["origin"]}

    @staticmethod
    def _verify_fs_restore(details):
        return ("path" in details, "restore recorded")

    # -- helpers ---------------------------------------------------------------
    def _rel(self, target: Path) -> str:
        try:
            return str(target.resolve().relative_to(self.workspace.resolve()))
        except ValueError:
            return str(target)


def open_machine(home: "str | Path | None" = None, **kwargs) -> Machine:
    """Open the Forge computer (creates ``~/.levi/forge/machine/`` on first use)."""
    return Machine(home, **kwargs)
