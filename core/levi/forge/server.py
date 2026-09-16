"""LEVI Forge server — smart-HTTP git hosting + repo web UI, stdlib only.

DESIGN CHOICE (see docs/FORGE.md): Forge does NOT reimplement the git
pack protocol. It implements the *HTTP framing* of the git smart-HTTP
protocol and shells out to the stock git binary for everything else:

- ``GET /<name>.git/info/refs?service=git-upload-pack`` →
  ``git upload-pack --advertise-refs``
- ``POST /<name>.git/git-upload-pack`` →
  ``git upload-pack --stateless-rpc`` (request body on stdin)
- same pair for ``git-receive-pack``

This is the exact protocol stock ``git clone``/``push``/``pull`` speak to
GitHub over HTTPS — so every stock git client works against Forge with no
plugins, no extensions, no new tooling. Forge's code only parses the URL,
validates the repo name, frames pkt-lines, and pipes bytes.

The same server also serves a minimal repo browser UI under ``/forge/``
(plain HTML, no JS framework, no build step).
"""

from __future__ import annotations

import html
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import browse
from .gitx import GitError, run_git
from .home import forge_home, validate_name
from .repos import list_repos, repo_dir, repo_exists

_SERVICES = {
    "git-upload-pack": {
        "advertise_arg": "--advertise-refs",
        "binary": "upload-pack",
        "adv_ctype": "application/x-git-upload-pack-advertisement",
        "res_ctype": "application/x-git-upload-pack-result",
    },
    "git-receive-pack": {
        "advertise_arg": "--http-backend-info-refs",
        "binary": "receive-pack",
        "adv_ctype": "application/x-git-receive-pack-advertisement",
        "res_ctype": "application/x-git-receive-pack-result",
    },
}


def _pkt_line(data: bytes) -> bytes:
    return ("%04x" % (len(data) + 4)).encode() + data


def _service_header(service: str) -> bytes:
    return _pkt_line(("# service=%s\n" % service).encode()) + b"0000"


class ForgeHandler(BaseHTTPRequestHandler):
    server_version = "LEVI-Forge/1"
    protocol_version = "HTTP/1.1"

    # -- plumbing ------------------------------------------------------

    @property
    def _home(self):
        return self.server.forge_home  # set by serve()

    def _send(self, code: int, ctype: str, body: bytes, extra=None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD" and body:
            self.wfile.write(body)

    def _text(self, code: int, msg: str, ctype="text/plain; charset=utf-8") -> None:
        self._send(code, ctype, msg.encode("utf-8"))

    def _repo_name(self, raw: str):
        """Validate the repo component of a URL path. None -> invalid."""
        if raw.endswith(".git"):
            raw = raw[: -len(".git")]
        try:
            return validate_name(raw)
        except ValueError:
            return None

    # -- smart HTTP ----------------------------------------------------

    def _git_advertise(self, name: str, service: str) -> None:
        cfg = _SERVICES[service]
        try:
            out = run_git(
                [cfg["binary"], cfg["advertise_arg"], str(repo_dir(self._home, name))]
            ).stdout
        except GitError as e:
            self._text(500, "forge: git failed: %s" % e)
            return
        self._send(200, cfg["adv_ctype"], _service_header(service) + out)

    def _git_rpc(self, name: str, service: str) -> None:
        cfg = _SERVICES[service]
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length > 0 else b""
        try:
            out = run_git(
                [cfg["binary"], "--stateless-rpc", str(repo_dir(self._home, name))],
                input=body,
            ).stdout
        except GitError as e:
            self._text(500, "forge: git failed: %s" % e)
            return
        self._send(200, cfg["res_ctype"], out)

    # -- routing -------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")

        # /<name>.git/info/refs?service=git-upload-pack|git-receive-pack
        if len(parts) == 3 and parts[1] == "info" and parts[2] == "refs":
            name = self._repo_name(parts[0])
            service = parse_qs(parsed.query).get("service", [None])[0]
            if name is None or not repo_exists(self._home, name):
                self._text(404, "forge: no such repo")
                return
            if service not in _SERVICES:
                self._text(400, "forge: unknown service %r" % service)
                return
            self._git_advertise(name, service)
            return

        # /forge/... web UI
        if parts[0] == "forge":
            self._ui(parts[1:], parse_qs(parsed.query))
            return

        if parsed.path == "/" or parsed.path == "":
            self._send(
                302, "text/plain", b"",
                {"Location": "/forge/"},
            )
            return
        self._text(404, "forge: not found")

    def do_POST(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 2 and parts[1] in _SERVICES:
            name = self._repo_name(parts[0])
            if name is None or not repo_exists(self._home, name):
                self._text(404, "forge: no such repo")
                return
            self._git_rpc(name, parts[1])
            return
        self._text(404, "forge: not found")

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, fmt, *args):  # keep stdout clean; server logs via CI
        pass

    # -- web UI --------------------------------------------------------

    def _ui(self, parts, query):
        if not parts or parts == [""]:
            self._ui_index()
            return
        name = self._repo_name(parts[0])
        if name is None or not repo_exists(self._home, name):
            self._text(404, "forge: no such repo")
            return
        page = parts[1] if len(parts) > 1 else ""
        if page in ("", "tree", "blob"):
            self._ui_repo(name, query, page or "tree")
        elif page == "log":
            self._ui_log(name, query)
        elif page == "issues":
            self._ui_issues(name)
        elif page == "prs":
            self._ui_prs(name)
        elif page == "ci":
            self._ui_ci(name)
        else:
            self._text(404, "forge: no such page")

    def _page(self, title: str, body: str) -> None:
        self._text(
            200,
            "<!DOCTYPE html><html><head><meta charset=utf-8>"
            "<title>%s — LEVI Forge</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:60em;margin:2em auto;"
            "padding:0 1em;background:#0b0e14;color:#d6deeb}a{color:#7cc7ff}"
            "pre{background:#11151d;padding:1em;overflow:auto;border-radius:6px}"
            "code{background:#11151d;padding:0 .3em;border-radius:3px}"
            "table{border-collapse:collapse}td,th{padding:.4em .8em;border:1px solid #222a38}"
            ".meta{color:#8a93a6;font-size:.9em}.sha{font-family:monospace;font-size:.85em}"
            "h1,h2{color:#f0f4fa}</style></head>"
            "<body><p><a href=/forge/>⟰ forge</a></p>%s</body></html>"
            % (html.escape(title), body),
            "text/html; charset=utf-8",
        )

    def _ui_index(self):
        rows = []
        for r in list_repos(self._home):
            try:
                commits = browse.log(self._home, r["name"], limit=1)
                n_commits = "≥1" if commits else "0"
            except GitError:
                n_commits = "0"
            rows.append(
                "<tr><td><a href=/forge/%s/>%s</a></td>"
                "<td>%s</td><td>%s</td><td>%s</td></tr>"
                % (r["name"], html.escape(r["name"]),
                   html.escape(r["description"] or "—"),
                   html.escape(r["default_branch"] or "—"), n_commits)
            )
        body = (
            "<h1>LEVI Forge</h1>"
            "<p class=meta>local-first code home · everything here lives on this "
            "machine · nothing leaves localhost unless you push it</p>"
            "<table><tr><th>repo</th><th>description</th><th>branch</th>"
            "<th>commits</th></tr>%s</table>" % "".join(rows)
        )
        self._page("repos", body)

    def _ui_repo(self, name, query, page):
        path = (query.get("path") or [""])[0].strip("/")
        esc = html.escape
        try:
            if page == "blob":
                content = browse.read_file(self._home, name, path=path)
                main = "<h2>%s</h2><pre>%s</pre>" % (esc(path), esc(content))
            else:
                entries = browse.tree(self._home, path=path)
                rows = []
                if path:
                    parent = "/".join(path.split("/")[:-1])
                    rows.append(
                        '<li><a href="/forge/%s/tree?path=%s">..</a></li>'
                        % (name, parent)
                    )
                for e in entries:
                    sub = (path + "/" + e["name"]).strip("/")
                    if e["type"] == "tree":
                        rows.append(
                            '<li>📁 <a href="/forge/%s/tree?path=%s">%s</a></li>'
                            % (name, sub, esc(e["name"])))
                    else:
                        rows.append(
                            '<li>📄 <a href="/forge/%s/blob?path=%s">%s</a></li>'
                            % (name, sub, esc(e["name"])))
                main = "<h2>%s</h2><ul>%s</ul>" % (esc("/" + path if path else "/"), "".join(rows))
        except GitError as e:
            main = "<p class=meta>error: %s</p>" % esc(str(e))
        readme = browse.find_readme(self._home, name)
        readme_html = ""
        if readme and page != "blob":
            try:
                text = browse.read_file(self._home, name, path=readme)
                if readme.lower().endswith(".md"):
                    readme_html = "<h2>README</h2>" + browse.render_markdown(text)
                else:
                    readme_html = "<h2>README</h2><pre>%s</pre>" % esc(text)
            except GitError:
                pass
        try:
            commits = browse.log(self._home, name, limit=5)
            clog = "".join(
                "<li><span class=sha>%s</span> %s <span class=meta>%s · %s</span></li>"
                % (c["sha"][:8], esc(c["subject"]), esc(c["author"]), esc(c["date"][:10]))
                for c in commits
            )
        except GitError:
            clog = "<li class=meta>no commits yet</li>"
        self._page(
            name,
            "<h1>%s</h1>"
            "<p><a href=/forge/%s/log>history</a> · "
            "<a href=/forge/%s/issues>issues</a> · "
            "<a href=/forge/%s/prs>pull requests</a> · "
            "<a href=/forge/%s/ci>CI</a></p>"
            "%s%s<ul>%s</ul>"
            % (esc(name), name, name, name, name, main, readme_html, clog),
        )

    def _ui_log(self, name, query):
        try:
            limit = max(1, min(200, int((query.get("limit") or ["30"])[0])))
        except ValueError:
            limit = 30
        try:
            commits = browse.log(self._home, name, limit=limit)
            rows = "".join(
                "<tr><td class=sha>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                % (html.escape(c["sha"][:12]), html.escape(c["subject"]),
                   html.escape(c["author"]), html.escape(c["date"][:16]))
                for c in commits
            )
        except GitError as e:
            rows = "<tr><td colspan=4>%s</td></tr>" % html.escape(str(e))
        self._page(
            name + " history",
            "<h1><a href=/forge/%s/>%s</a> — history</h1>"
            "<table><tr><th>sha</th><th>subject</th><th>author</th><th>date</th></tr>%s</table>"
            % (name, html.escape(name), rows),
        )

    def _ui_issues(self, name):
        from . import issues as _issues

        rows = "".join(
            "<tr><td>#%d</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (i["id"], html.escape(i["title"]), i["state"],
               ", ".join(html.escape(l) for l in i.get("labels", [])))
            for i in _issues.list_issues(self._home, name)
        )
        self._page(
            name + " issues",
            "<h1><a href=/forge/%s/>%s</a> — issues</h1>"
            "<table><tr><th>#</th><th>title</th><th>state</th><th>labels</th></tr>%s</table>"
            % (name, html.escape(name), rows),
        )

    def _ui_prs(self, name):
        from . import prs as _prs

        rows = "".join(
            "<tr><td>#%d</td><td>%s</td><td class=sha>%s → %s</td><td>%s</td></tr>"
            % (p["id"], html.escape(p["title"]),
               html.escape(p["head"]), html.escape(p["base"]), p["state"])
            for p in _prs.list_prs(self._home, name)
        )
        self._page(
            name + " pull requests",
            "<h1><a href=/forge/%s/>%s</a> — pull requests</h1>"
            "<table><tr><th>#</th><th>title</th><th>head → base</th><th>state</th></tr>%s</table>"
            % (name, html.escape(name), rows),
        )

    def _ui_ci(self, name):
        from . import ci as _ci

        try:
            pipe = _ci.load_pipeline(self._home, name)
            steps = "".join(
                "<li>%s — <span class=sha>%s</span></li>"
                % (html.escape(s.get("name", "?")),
                   html.escape(s.get("run", "")))
                for s in pipe.get("steps", [])
            )
            runs = "".join(
                "<tr><td class=sha>%s</td><td>%s</td><td>%s</td></tr>"
                % (html.escape(r.get("id", "")),
                   "PASS" if r.get("ok") else "FAIL",
                   html.escape(r.get("started", "")))
                for r in _ci.list_runs(self._home, name)
            )
        except (GitError, ValueError) as e:
            steps, runs = "<li>%s</li>" % html.escape(str(e)), ""
        self._page(
            name + " CI",
            "<h1><a href=/forge/%s/>%s</a> — CI</h1>"
            "<h2>pipeline</h2><ul>%s</ul>"
            "<h2>runs</h2><table><tr><th>run</th><th>result</th><th>started</th></tr>%s</table>"
            "<p class=meta>runs on this machine only · no minute metering · no cloud</p>"
            % (name, html.escape(name), steps, runs),
        )


class ForgeServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, home, bind: str = "127.0.0.1", port: int = 8741):
        self.forge_home = forge_home(home)
        super().__init__((bind, port), ForgeHandler)


def serve(home=None, bind: str = "127.0.0.1", port: int = 8741) -> ForgeServer:
    """Create (do NOT start) the server. Call ``serve_forever()`` to run."""
    if bind not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(
            "forge serves localhost only (got %r) — code never leaves this machine" % bind
        )
    return ForgeServer(home, bind=bind, port=port)


def serve_forever(home=None, bind: str = "127.0.0.1", port: int = 8741) -> None:
    srv = serve(home, bind=bind, port=port)
    addr = srv.server_address
    print("LEVI Forge serving at http://%s:%d/  (localhost only — nothing leaves this machine)"
          % (addr[0], addr[1]))
    print("clone: git clone http://%s:%d/<name>.git" % (addr[0], addr[1]))
    print("browse: http://%s:%d/forge/" % (addr[0], addr[1]))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
