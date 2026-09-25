"""FidoNet echomail: federated moderation without a platform.

Origin: in February 1986 Jeff Rush's tosser/scanner turned local BBS public
forums into networked conferences — local messages were bundled, compressed,
attached to netmail, and unpacked into the same forum on every participating
board. First echoes: SYSOP, TECH, then GAYNET, CLANG; Thomas Kenny's
Echolist catalogued hundreds from January 1987; traffic hit 8MB+ of
compressed messages per day by the early 90s. Each echo had a volunteer
moderator and a written charter; enforcement was social (warn, shun,
delink), not algorithmic. Offline composition slowed flame velocity and
produced longer, more considered posts. The anarchist constitution scaled to
35,000 nodes through coordinators, not employees.

What it is in LEVI: an Echo federation. Create an echo with a written
charter (including banned words) and a named moderator; post messages
(offline-composed, stored); bundle/unbundle message batches for
store-and-forward transport; enforce the charter through a moderation state
machine that escalates warn -> shun -> delink with no skipped steps.

Honesty label: USEFUL PATTERN — the charter + escalating social
enforcement + store-and-forward bundles are the real echomail mechanisms;
this is one federation in memory, not a 35,000-node network.

Deny-closed inputs: empty or duplicate echo names, empty charters or
moderators, posts to unknown echoes, empty bodies, charter violations,
posts from shunned or delinked users, malformed or echo-mismatched
bundles, and moderation actions that skip escalation steps all raise
ValueError.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

__all__ = [
    "Echo",
    "Message",
    "EchoFederation",
    "MEMBER",
    "WARNED",
    "SHUNNED",
    "DELINKED",
    "BUNDLE_MAGIC",
]

MEMBER = "member"
WARNED = "warned"
SHUNNED = "shunned"
DELINKED = "delinked"
_ESCALATION = (MEMBER, WARNED, SHUNNED, DELINKED)
BUNDLE_MAGIC = "FIDOBUNDLE/1"


@dataclass
class Message:
    id: str
    echo: str
    seq: int
    author: str
    body: str


@dataclass
class Echo:
    name: str
    charter: str
    moderator: str
    banned_words: tuple[str, ...] = ()
    messages: list[Message] = field(default_factory=list)
    standing: dict[str, str] = field(default_factory=dict)  # user -> status


class EchoFederation:
    """Federated echoes: charters, bundles, and social enforcement."""

    def __init__(self) -> None:
        self._echoes: dict[str, Echo] = {}

    def _require_echo(self, name: str) -> Echo:
        echo = self._echoes.get(name)
        if echo is None:
            raise ValueError(f"unknown echo: {name!r}")
        return echo

    @staticmethod
    def _require_user(user: str) -> str:
        if not isinstance(user, str) or not user.strip():
            raise ValueError("user name must be a non-empty string")
        return user.strip()

    def create_echo(
        self,
        name: str,
        charter: str,
        moderator: str,
        banned_words: tuple[str, ...] = (),
    ) -> Echo:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("echo name must be a non-empty string")
        name = name.strip()
        if name in self._echoes:
            raise ValueError(f"duplicate echo: {name!r}")
        if not isinstance(charter, str) or not charter.strip():
            raise ValueError(f"echo {name!r}: charter must be non-empty")
        moderator = self._require_user(moderator)
        for word in banned_words:
            if not isinstance(word, str) or not word.strip():
                raise ValueError("banned words must be non-empty strings")
        echo = Echo(
            name=name,
            charter=charter.strip(),
            moderator=moderator,
            banned_words=tuple(w.strip().lower() for w in banned_words),
        )
        self._echoes[name] = echo
        return echo

    def echoes(self) -> list[str]:
        return list(self._echoes)

    # -- posting (offline composition, stored on post) ---------------------
    def post(self, echo_name: str, author: str, body: str) -> Message:
        echo = self._require_echo(echo_name)
        author = self._require_user(author)
        if not isinstance(body, str) or not body.strip():
            raise ValueError("message body must be non-empty")
        body = body.strip()
        standing = echo.standing.get(author, MEMBER)
        if standing in (SHUNNED, DELINKED):
            raise ValueError(f"{author!r} is {standing} in {echo_name!r}: cannot post")
        lowered = body.lower()
        for word in echo.banned_words:
            if word in lowered:
                raise ValueError(
                    f"charter violation in {echo_name!r}: banned word {word!r}"
                )
        msg = Message(
            id=uuid.uuid4().hex[:12],
            echo=echo_name,
            seq=len(echo.messages),
            author=author,
            body=body,
        )
        echo.messages.append(msg)
        return msg

    # -- store-and-forward bundles ------------------------------------------
    def bundle(self, echo_name: str, since: int = 0) -> str:
        echo = self._require_echo(echo_name)
        if since < 0:
            raise ValueError("since must be >= 0")
        payload = {
            "magic": BUNDLE_MAGIC,
            "echo": echo_name,
            "messages": [
                {"id": m.id, "seq": m.seq, "author": m.author, "body": m.body}
                for m in echo.messages
                if m.seq >= since
            ],
        }
        return json.dumps(payload)

    def unbundle(self, bundle: str, echo_name: str) -> int:
        """Unpack a bundle into an echo; returns messages imported."""
        echo = self._require_echo(echo_name)
        try:
            payload = json.loads(bundle)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"malformed bundle: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("magic") != BUNDLE_MAGIC:
            raise ValueError("malformed bundle: bad magic")
        if payload.get("echo") != echo_name:
            raise ValueError(
                f"bundle is for echo {payload.get('echo')!r}, not {echo_name!r}"
            )
        raw = payload.get("messages")
        if not isinstance(raw, list):
            raise ValueError("malformed bundle: messages must be a list")
        seen = {m.id for m in echo.messages}
        imported = 0
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("malformed bundle: bad message entry")
            for key in ("id", "author", "body"):
                if not item.get(key):
                    raise ValueError(f"malformed bundle: message missing {key!r}")
            if item["id"] in seen:
                continue  # already have it: store-and-forward dedupes
            echo.messages.append(
                Message(
                    id=item["id"],
                    echo=echo_name,
                    seq=len(echo.messages),
                    author=item["author"],
                    body=item["body"],
                )
            )
            seen.add(item["id"])
            imported += 1
        return imported

    # -- moderation: the charter enforcement state machine ------------------
    def status(self, echo_name: str, user: str) -> str:
        echo = self._require_echo(echo_name)
        return echo.standing.get(self._require_user(user), MEMBER)

    def _step(self, echo_name: str, user: str, target: str) -> str:
        """Escalate exactly one rung: warn -> shun -> delink."""
        echo = self._require_echo(echo_name)
        user = self._require_user(user)
        current = echo.standing.get(user, MEMBER)
        want = _ESCALATION.index(target)
        have = _ESCALATION.index(current)
        if want == have:
            raise ValueError(f"{user!r} is already {current} in {echo_name!r}")
        if want != have + 1:
            raise ValueError(
                f"charter enforcement is stepwise: {user!r} is {current}, "
                f"cannot jump to {target} (warn -> shun -> delink)"
            )
        echo.standing[user] = target
        return target

    def warn(self, echo_name: str, user: str) -> str:
        return self._step(echo_name, user, WARNED)

    def shun(self, echo_name: str, user: str) -> str:
        return self._step(echo_name, user, SHUNNED)

    def delink(self, echo_name: str, user: str) -> str:
        return self._step(echo_name, user, DELINKED)

    def pardon(self, echo_name: str, user: str) -> str:
        """Step one rung back down the ladder (delinked -> shunned -> ...)."""
        echo = self._require_echo(echo_name)
        user = self._require_user(user)
        current = echo.standing.get(user, MEMBER)
        if current == MEMBER:
            raise ValueError(f"{user!r} is in good standing: nothing to pardon")
        stepped = _ESCALATION[_ESCALATION.index(current) - 1]
        echo.standing[user] = stepped
        return stepped
