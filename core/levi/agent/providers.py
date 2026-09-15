"""Chat/tool-calling provider chain for the LEVI agentic loop (``levi agent run``).

DIVISION OF LABOR (do not collapse):

- ``core/levi/model/abstraction.py`` is the canonical **GENERATION** router
  (``ModelRouter`` / ``ModelProvider``): prose and story generation. Its
  ``OllamaProvider`` performs local model discovery for generation
  workloads.
- This module is the canonical **CHAT/TOOL-CALLING** provider chain for the
  agentic loop: multi-turn chat that can emit structured tool calls. It is
  a different interface (tool calls), not a second generation router.

Nothing is imported from ``model.abstraction`` — the dependency direction
is kept clean on purpose. Ollama discovery is not reimplemented here: the
``OpenAICompatibleProvider`` covers local servers (Ollama at
``http://localhost:11434/v1``, vLLM, ...) via the ``LEVI_OPENAI_BASE_URL``
override with zero code change.

Selection is offline-first: explicit preference flag > ``LEVI_PROVIDER``
env var > ``LocalProvider`` default. A preferred provider that is not
available falls back to ``LocalProvider`` (honestly — the loop can always
report which provider it ended up with via ``ChatResponse.provider``).

Stdlib only: ``urllib`` for HTTP. No SDK dependencies, no new third-party
imports in ``core/levi``.

Tool argument shapes the ``LocalProvider`` planner emits (reconciled with
the real handler keys in :mod:`levi.agent.tools` — the handler is the
source of truth; the planner must emit exactly these keys):

- ``file_write``:  ``{"path": str, "content": str}``
- ``file_read``:   ``{"path": str}``
- ``shell_exec``:  ``{"cmd": str}``            (handler reads ``args["cmd"]``)
- ``memory_write``: ``{"text": str}``          (handler treats ``text`` as an
  alias for ``content`` and defaults a missing ``name`` to ``"scratch"``)
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Contract (built against by the agentic-loop worker)
# ---------------------------------------------------------------------------


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None        # tool name for role="tool"
    tool_call_id: str | None = None


@dataclass
class ProviderToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ChatResponse:
    text: str = ""
    tool_calls: list[ProviderToolCall] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    latency_ms: float = 0.0
    error: str | None = None


class ChatProvider(ABC):
    name: str  # class attr

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def chat(self, messages: list[ChatMessage], tools: list[dict]) -> ChatResponse:
        # tools: list of {"name":..., "description":..., "parameters": {...}}
        ...


# ---------------------------------------------------------------------------
# LocalProvider — deterministic offline tool-use planner
# ---------------------------------------------------------------------------


class LocalProvider(ChatProvider):
    """Deterministic offline tool-use planner.

    Always available; makes the agentic loop useful with no network. Pure
    rule-based planning: the task is inferred from the user message(s) and
    the plan's progress is derived entirely from the message history (prior
    tool results appear as ``role="tool"`` messages). No hidden instance
    state, so the output is deterministic per conversation.

    Supported intents: file tasks (create/write/read files), shell command
    execution, and memory notes. Unclear tasks get a clarification reply
    with no tool calls. Tool calls are only ever emitted for tools present
    in the ``tools`` argument.
    """

    name = "local"

    _NUMBER_WORDS = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }

    def is_available(self) -> bool:
        return True

    # -- public entry point -------------------------------------------------

    def chat(self, messages: list[ChatMessage], tools: list[dict]) -> ChatResponse:
        t0 = time.perf_counter()
        available = {
            t["name"] for t in tools
            if isinstance(t, dict) and t.get("name")
        }
        called = self._called_tools(messages)
        task = self._task_text(messages)

        if not task.strip():
            return self._finish(
                t0,
                "I didn't get a task to work on. Tell me what you'd like me "
                "to do — for example, create a file, run a command, or "
                "remember a note.",
            )

        intent, params = self._classify(task)
        if intent is None:
            return self._finish(
                t0,
                "I'm not sure what you're asking me to do. I can work with "
                "files (create, write, read), run shell commands, or save "
                "notes to memory. Could you describe the task more "
                "concretely?",
            )

        for tool_name, args in self._plan(intent, params):
            if tool_name in called:
                continue
            if tool_name not in available:
                return self._finish(
                    t0,
                    "I understand the task, but the '%s' tool is not "
                    "available in this session, so I can't carry it out. "
                    "No action was taken." % tool_name,
                )
            call = ProviderToolCall(
                id="local-%d" % (len(called) + 1),
                name=tool_name,
                arguments=args,
            )
            return self._finish(t0, "", [call])

        return self._finish(t0, self._summary(intent, params, called, messages))

    # -- history / state derivation (no instance state) ---------------------

    @staticmethod
    def _finish(t0: float, text: str,
                tool_calls: list[ProviderToolCall] | None = None) -> ChatResponse:
        return ChatResponse(
            text=text,
            tool_calls=tool_calls or [],
            model="local",
            provider="local",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )

    @staticmethod
    def _called_tools(messages: list[ChatMessage]) -> list[str]:
        """Tool names already executed, in order, derived from tool results."""
        return [m.name for m in messages if m.role == "tool" and m.name]

    @staticmethod
    def _task_text(messages: list[ChatMessage]) -> str:
        user_texts = [m.content for m in messages if m.role == "user" and m.content]
        if user_texts:
            return user_texts[0]
        return ""

    # -- intent classification ----------------------------------------------

    def _classify(self, task: str) -> tuple[str | None, dict]:
        """Return (intent, params); intent None means 'unclear, clarify'."""
        memory = self._classify_memory(task)
        if memory is not None:
            return "memory", memory
        file_plan = self._classify_file(task)
        if file_plan is not None:
            return "file", file_plan
        shell = self._classify_shell(task)
        if shell is not None:
            return "shell", shell
        return None, {}

    @staticmethod
    def _classify_memory(task: str) -> dict | None:
        m = re.search(
            r"(?:remember|note down|jot down|save to memory)\s+(?:that\s+)?(.+?)[.!?\s]*$",
            task, re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return None
        text = m.group(1).strip()
        return {"text": text} if text else None

    def _classify_file(self, task: str) -> dict | None:
        low = task.lower()
        path = self._extract_path(task)
        if path is None:
            return None
        needs_write = any(k in low for k in ("create", "write", "save", "make", "update"))
        needs_read = "read" in low
        if not (needs_write or needs_read):
            return None
        count = self._extract_line_count(low)
        quoted = re.findall(r'"([^"]+)"', task) + re.findall(r"'([^']+)'", task)
        lines = [q for q in quoted if q.strip()][:count]
        while len(lines) < count:
            lines.append("Line %d" % (len(lines) + 1))
        return {
            "path": path,
            "lines": lines,
            "needs_write": needs_write,
            "needs_read": needs_read,
        }

    @staticmethod
    def _extract_path(task: str) -> str | None:
        m = re.search(r"([A-Za-z0-9_.\-]+\.[A-Za-z0-9]+)", task)
        if m:
            return m.group(1)
        m = re.search(r"(\w[\w\-]*)\s+file", task, re.IGNORECASE)
        if m:
            return m.group(1).lower() + ".txt"
        return None

    def _extract_line_count(self, low: str) -> int:
        m = re.search(r"(\d+)\s+lines?", low)
        if m:
            return max(1, min(50, int(m.group(1))))
        for word, n in self._NUMBER_WORDS.items():
            if re.search(r"\b%s\s+lines?\b" % word, low):
                return n
        return 3

    @staticmethod
    def _classify_shell(task: str) -> dict | None:
        low = task.lower()
        if re.search(r"\blist\b.*\bfiles?\b", low) or re.search(r"^ls\b", low.strip()):
            return {"command": "ls"}
        m = re.search(
            r"(?:run|execute)\s+(?:the\s+command\s+)?[`\"']?([^`\"'\n.!?;]+)",
            task, re.IGNORECASE,
        )
        if m:
            command = m.group(1).strip()
            if command:
                return {"command": command}
        return None

    # -- planning ------------------------------------------------------------

    @staticmethod
    def _plan(intent: str, params: dict) -> list[tuple[str, dict]]:
        if intent == "file":
            steps: list[tuple[str, dict]] = []
            if params.get("needs_write"):
                steps.append((
                    "file_write",
                    {"path": params["path"],
                     "content": "\n".join(params["lines"])},
                ))
            if params.get("needs_read"):
                steps.append(("file_read", {"path": params["path"]}))
            return steps
        if intent == "memory":
            return [("memory_write", {"text": params["text"]})]
        if intent == "shell":
            # Key must match the shell_exec handler's real key ("cmd"), not
            # a guessed synonym — see the module docstring reconciliation.
            return [("shell_exec", {"cmd": params["command"]})]
        return []

    # -- honest final summary -------------------------------------------------

    def _summary(self, intent: str, params: dict, called: list[str],
                 messages: list[ChatMessage]) -> str:
        results = {}
        for m in messages:
            if m.role == "tool" and m.name:
                results[m.name] = m.content or ""
        if intent == "file":
            path = params["path"]
            parts = []
            if "file_write" in called:
                parts.append("wrote %d line(s) to %s"
                             % (len(params["lines"]), path))
            if "file_read" in called:
                parts.append("read %s back" % path)
            text = "Done: " + " and ".join(parts) + "."
            read_back = results.get("file_read", "").strip()
            if read_back:
                text += " Contents read: %r." % read_back[:200]
            return text
        if intent == "memory":
            return "Done: saved the note to memory: %r." % params["text"][:200]
        if intent == "shell":
            out = results.get("shell_exec", "").strip()
            text = "Done: ran `%s`." % params["command"]
            if out:
                text += " Output: %r." % out[:200]
            return text
        return "Done."


# ---------------------------------------------------------------------------
# OpenAICompatibleProvider — cloud OpenAI OR any OpenAI-compatible endpoint
# ---------------------------------------------------------------------------


class OpenAICompatibleProvider(ChatProvider):
    """POST ``{base_url}/chat/completions`` with OpenAI function calling.

    ``base_url`` comes from ``LEVI_OPENAI_BASE_URL`` (default
    ``https://api.openai.com/v1``), so the same code talks to cloud
    OpenAI, a local Ollama (``http://localhost:11434/v1``), or vLLM with
    zero code change. Bearer auth from ``LEVI_OPENAI_API_KEY``; the model
    from ``LEVI_OPENAI_MODEL`` (default ``gpt-4o-mini``).

    ``is_available()`` is True when a key is set OR the base URL was
    explicitly overridden (a local server may need no key). Errors are
    surfaced honestly in ``ChatResponse.error`` — ``chat()`` never raises
    and never fakes a response. HTTP timeout: 60s.
    """

    name = "openai"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o-mini"
    TIMEOUT_S = 60

    def _config(self) -> tuple[str, str, bool, str]:
        key = os.environ.get("LEVI_OPENAI_API_KEY", "")
        base_url = os.environ.get("LEVI_OPENAI_BASE_URL", self.DEFAULT_BASE_URL)
        overridden = "LEVI_OPENAI_BASE_URL" in os.environ
        model = os.environ.get("LEVI_OPENAI_MODEL", self.DEFAULT_MODEL)
        return key, base_url.rstrip("/"), overridden, model

    def is_available(self) -> bool:
        key, _base_url, overridden, _model = self._config()
        return bool(key) or overridden

    def chat(self, messages: list[ChatMessage], tools: list[dict]) -> ChatResponse:
        t0 = time.perf_counter()
        key, base_url, _overridden, model = self._config()

        def finish(text="", tool_calls=None, error=None) -> ChatResponse:
            return ChatResponse(
                text=text,
                tool_calls=tool_calls or [],
                model=model,
                provider=self.name,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                error=error,
            )

        if not messages:
            return finish(error="no messages provided")

        payload: dict = {
            "model": model,
            "messages": [self._to_openai_message(m, i) for i, m in enumerate(messages)],
        }
        if tools:
            payload["tools"] = [
                {"type": "function",
                 "function": {"name": t["name"],
                              "description": t.get("description", ""),
                              "parameters": t.get("parameters", {})}}
                for t in tools if isinstance(t, dict) and t.get("name")
            ]
            payload["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = "Bearer " + key
        req = urllib.request.Request(
            base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers=headers,
        )

        try:
            resp = urllib.request.urlopen(req, timeout=self.TIMEOUT_S)
            try:
                status = resp.getcode() if hasattr(resp, "getcode") else getattr(resp, "status", 200)
                raw = resp.read()
            finally:
                try:
                    resp.close()
                except Exception:
                    pass
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", "replace")[:500]
            except Exception:
                body = ""
            return finish(error="HTTP %s: %s" % (e.code, body or e.reason))
        except urllib.error.URLError as e:
            return finish(error="network error: %s" % e.reason)
        except Exception as e:  # timeout etc.
            return finish(error="request failed: %s: %s"
                          % (type(e).__name__, e))

        if status and status >= 400:
            return finish(error="HTTP %s: %s"
                          % (status, raw.decode("utf-8", "replace")[:500]))

        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as e:
            return finish(error="invalid JSON response: %s" % e)

        try:
            message = data["choices"][0]["message"]
            text = message.get("content") or ""
            calls = []
            for i, tc in enumerate(message.get("tool_calls") or []):
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                calls.append(ProviderToolCall(
                    id=tc.get("id") or "call-%d" % i,
                    name=fn.get("name", ""),
                    arguments=args if isinstance(args, dict) else {},
                ))
        except (KeyError, IndexError, TypeError) as e:
            return finish(error="unexpected response shape: %s" % e)

        return finish(text=text, tool_calls=calls)

    @staticmethod
    def _to_openai_message(m: ChatMessage, i: int) -> dict:
        if m.role == "tool":
            return {
                "role": "tool",
                "content": m.content,
                "tool_call_id": m.tool_call_id or m.name or "call-%d" % i,
            }
        return {"role": m.role, "content": m.content}


# ---------------------------------------------------------------------------
# AnthropicProvider — api.anthropic.com/v1/messages
# ---------------------------------------------------------------------------


class AnthropicProvider(ChatProvider):
    """POST ``https://api.anthropic.com/v1/messages`` with tool use.

    API key from ``LEVI_ANTHROPIC_API_KEY`` (``x-api-key`` header),
    ``anthropic-version: 2023-06-01`` header, model from
    ``LEVI_ANTHROPIC_MODEL`` (default ``claude-sonnet-4-20250514``).
    Tools are converted to the Anthropic tool schema; ``tool_use`` blocks
    are parsed back into ``ProviderToolCall``. Errors surface honestly in
    ``ChatResponse.error``. HTTP timeout: 60s.
    """

    name = "anthropic"
    URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    TIMEOUT_S = 60
    MAX_TOKENS = 1024

    def _config(self) -> tuple[str, str]:
        return (os.environ.get("LEVI_ANTHROPIC_API_KEY", ""),
                os.environ.get("LEVI_ANTHROPIC_MODEL", self.DEFAULT_MODEL))

    def is_available(self) -> bool:
        key, _model = self._config()
        return bool(key)

    def chat(self, messages: list[ChatMessage], tools: list[dict]) -> ChatResponse:
        t0 = time.perf_counter()
        key, model = self._config()

        def finish(text="", tool_calls=None, error=None) -> ChatResponse:
            return ChatResponse(
                text=text,
                tool_calls=tool_calls or [],
                model=model,
                provider=self.name,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                error=error,
            )

        if not messages:
            return finish(error="no messages provided")
        if not key:
            return finish(error="LEVI_ANTHROPIC_API_KEY is not set")

        system, conv = self._to_anthropic_messages(messages)
        payload: dict = {
            "model": model,
            "max_tokens": self.MAX_TOKENS,
            "messages": conv,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [
                {"name": t["name"],
                 "description": t.get("description", ""),
                 "input_schema": t.get("parameters", {"type": "object"})}
                for t in tools if isinstance(t, dict) and t.get("name")
            ]

        req = urllib.request.Request(
            self.URL,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": self.API_VERSION,
            },
        )

        try:
            resp = urllib.request.urlopen(req, timeout=self.TIMEOUT_S)
            try:
                status = resp.getcode() if hasattr(resp, "getcode") else getattr(resp, "status", 200)
                raw = resp.read()
            finally:
                try:
                    resp.close()
                except Exception:
                    pass
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", "replace")[:500]
            except Exception:
                body = ""
            return finish(error="HTTP %s: %s" % (e.code, body or e.reason))
        except urllib.error.URLError as e:
            return finish(error="network error: %s" % e.reason)
        except Exception as e:
            return finish(error="request failed: %s: %s"
                          % (type(e).__name__, e))

        if status and status >= 400:
            return finish(error="HTTP %s: %s"
                          % (status, raw.decode("utf-8", "replace")[:500]))

        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as e:
            return finish(error="invalid JSON response: %s" % e)

        try:
            texts, calls = [], []
            for block in data.get("content", []):
                btype = block.get("type")
                if btype == "text":
                    texts.append(block.get("text", ""))
                elif btype == "tool_use":
                    args = block.get("input") or {}
                    calls.append(ProviderToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=args if isinstance(args, dict) else {},
                    ))
        except (AttributeError, TypeError) as e:
            return finish(error="unexpected response shape: %s" % e)

        return finish(text="".join(texts), tool_calls=calls)

    @staticmethod
    def _to_anthropic_messages(messages: list[ChatMessage]) -> tuple[str, list[dict]]:
        system_parts, conv = [], []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            elif m.role == "tool":
                conv.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id or m.name or "unknown",
                        "content": m.content,
                    }],
                })
            elif m.role == "assistant":
                conv.append({"role": "assistant", "content": m.content})
            else:
                conv.append({"role": "user", "content": m.content})
        return "\n".join(system_parts), conv


# ---------------------------------------------------------------------------
# Selection — explicit flag > LEVI_PROVIDER env > local-first default
# ---------------------------------------------------------------------------


_PROVIDER_CLASSES = {
    "local": LocalProvider,
    "openai": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
}


def provider_names() -> list[str]:
    """Names of all known chat providers, in preference order."""
    return ["local", "openai", "anthropic"]


def select_provider(preference: str | None = None) -> ChatProvider:
    """Pick a chat provider: flag > ``LEVI_PROVIDER`` env > local default.

    A preferred provider that is not available falls back to
    ``LocalProvider`` (offline-first); unknown names also fall back to
    local rather than failing.
    """
    name = (preference or os.environ.get("LEVI_PROVIDER") or "local").strip().lower()
    cls = _PROVIDER_CLASSES.get(name)
    if cls is None or cls is LocalProvider:
        return LocalProvider()
    provider = cls()
    if not provider.is_available():
        return LocalProvider()
    return provider
