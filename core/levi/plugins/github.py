"""GitHub connector — the one live plugin wired end-to-end (blueprint §5.4).

Auth: personal access token (classic or fine-grained) read ONLY from the
``LEVI_GITHUB_TOKEN`` env var. The token is never logged, never printed,
and never written to disk — it travels in memory from the env var to the
``Authorization`` header of a single request.

Transport: stdlib ``urllib`` against ``https://api.github.com`` (the
stable GitHub REST API). The kernel stays stdlib-only per blueprint §1.1.

Read operations run as soon as the credential is present. Write
operations (issues, comments) inherit ``requires_confirmation=True``
from the registry — §1.5, no per-feature override, no exceptions.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from .registry import (
    Capability,
    Connector,
    ConnectorAPIError,
    InvalidParams,
    Operation,
    Transport,
    register_connector,
)

API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"
USER_AGENT = "levi-plugin/1.0"
TIMEOUT_SECONDS = 20

_SLUG = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _slug(value: Any, what: str) -> str:
    """Validate a GitHub owner/repo slug so params can never inject path
    segments or query strings into the request URL."""
    text = str(value or "").strip()
    if not _SLUG.match(text):
        raise InvalidParams(
            f"invalid {what} {text!r}: use only letters, digits, '.', "
            "'-', '_' — nothing was sent."
        )
    return text


def _positive_int(value: Any, what: str) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise InvalidParams(
            f"invalid {what} {value!r}: expected a positive integer — nothing was sent."
        ) from None
    if number <= 0:
        raise InvalidParams(
            f"invalid {what} {value!r}: expected a positive integer — nothing was sent."
        )
    return number


#: GitHub API payload limits: issue titles truncate at ~256 chars, and
#: issue/comment bodies cap at 65536. Validate before transport so an
#: oversized payload fails here, not mid-request.
_MAX_ISSUE_TITLE = 256
_MAX_BODY_CHARS = 65536


def _bounded_str(value: Any, what: str, limit: int) -> str:
    """A text param that must fit the GitHub API limit."""
    text = str(value or "").strip()
    if len(text) > limit:
        raise InvalidParams(
            f"invalid {what}: {len(text)} chars exceeds the GitHub limit of "
            f"{limit} — shorten it; nothing was sent."
        )
    return text


class GitHubConnector(Connector):
    id = "github"
    display_name = "GitHub"
    credential_env_var = "LEVI_GITHUB_TOKEN"

    capabilities = (
        Capability("read.user", "Read the authenticated user's profile"),
        Capability("read.repo", "Read public/private repo metadata"),
        Capability(
            "write.issue",
            "Create issues on repos the token can access",
            write=True,
        ),
        Capability(
            "write.comment",
            "Comment on issues the token can access",
            write=True,
        ),
    )

    operations = (
        Operation("whoami", "Return the authenticated GitHub user", params=()),
        Operation(
            "get_repo",
            "Return metadata for owner/repo",
            params=("owner", "repo"),
        ),
        Operation(
            "create_issue",
            "Open an issue on owner/repo",
            write=True,
            params=("owner", "repo", "title"),
        ),
        Operation(
            "create_comment",
            "Comment on an issue of owner/repo",
            write=True,
            params=("owner", "repo", "issue_number", "body"),
        ),
    )

    # requires_confirmation is forced to True by the registry because this
    # connector exposes write capabilities — no per-feature override,
    # no exceptions. Stated explicitly here so the rule is visible at the
    # call site that needs it most.
    requires_confirmation = True

    # -- transport (stdlib urllib, wired) ---------------------------------

    def _call_api(self, method: str, path: str, token: str, body: Any = None) -> Any:
        data = None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": API_VERSION,
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            API_BASE + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            # Report the remote status honestly; never echo the credential.
            detail = ""
            try:
                payload = json.loads(exc.read().decode("utf-8") or "{}")
                detail = str(payload.get("message", "")).strip()
            except (ValueError, UnicodeDecodeError):
                detail = ""
            suffix = f": {detail}" if detail else ""
            raise ConnectorAPIError(
                f"GitHub API error {exc.code}{suffix} — nothing was applied."
            ) from None
        except urllib.error.URLError as exc:
            raise ConnectorAPIError(
                f"GitHub transport error: {exc.reason} — nothing was sent."
            ) from None
        try:
            return json.loads(raw) if raw.strip() else {}
        except ValueError:
            raise ConnectorAPIError(
                "GitHub returned a non-JSON response — nothing was applied."
            ) from None

    # -- operations --------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        token: str,
        body: Any,
        transport: Transport | None,
    ) -> Any:
        if transport is not None:
            return transport(method, path, token, body)
        return self._call_api(method, path, token, body)

    def perform(
        self,
        operation: str,
        params: dict[str, Any],
        token: str,
        transport: Transport | None,
    ) -> Any:
        missing = [
            name
            for name in next(o for o in self.operations if o.name == operation).params
            if not str(params.get(name, "")).strip()
        ]
        if missing:
            raise InvalidParams(
                f"missing required params for {operation!r}: "
                f"{', '.join(missing)} — nothing was sent."
            )

        if operation == "whoami":
            user = self._request("GET", "/user", token, None, transport)
            return {
                "login": user.get("login"),
                "name": user.get("name"),
                "id": user.get("id"),
            }

        if operation == "get_repo":
            owner = _slug(params["owner"], "owner")
            repo = _slug(params["repo"], "repo")
            data = self._request(
                "GET", f"/repos/{owner}/{repo}", token, None, transport
            )
            return {
                "full_name": data.get("full_name"),
                "description": data.get("description"),
                "private": data.get("private"),
                "stars": data.get("stargazers_count"),
                "default_branch": data.get("default_branch"),
            }

        if operation == "create_issue":
            owner = _slug(params["owner"], "owner")
            repo = _slug(params["repo"], "repo")
            body = {
                "title": _bounded_str(params["title"], "title", _MAX_ISSUE_TITLE),
                "body": _bounded_str(params.get("body", ""), "body", _MAX_BODY_CHARS),
            }
            data = self._request(
                "POST", f"/repos/{owner}/{repo}/issues", token, body, transport
            )
            return {
                "number": data.get("number"),
                "url": data.get("html_url"),
                "state": data.get("state"),
            }

        if operation == "create_comment":
            owner = _slug(params["owner"], "owner")
            repo = _slug(params["repo"], "repo")
            number = _positive_int(params["issue_number"], "issue_number")
            body = {
                "body": _bounded_str(params["body"], "body", _MAX_BODY_CHARS),
            }
            data = self._request(
                "POST",
                f"/repos/{owner}/{repo}/issues/{number}/comments",
                token,
                body,
                transport,
            )
            return {
                "id": data.get("id"),
                "url": data.get("html_url"),
            }

        # Unreachable via execute() (unknown ops are rejected there), but
        # stay honest rather than returning a fabricated payload.
        raise InvalidParams(
            f"operation {operation!r} has no implementation — nothing was sent."
        )


register_connector(GitHubConnector)
