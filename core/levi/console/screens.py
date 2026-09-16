"""Screen handlers for the LEVI interactive console.

Each screen is a small function ``screen_*() -> None`` that drives one
menu-driven workflow by calling existing LEVI module functions — the
console adds no capabilities of its own:

- :func:`screen_security_browser` — pages/searches/shows the offline
  security knowledge catalog via :mod:`levi.knowledge.security.catalog`.
- :func:`screen_bounty_recon` — enrolls a scope and runs
  :func:`levi.bounty.pipeline.run_recon` with a live finding feed.
- :func:`screen_demand_digest` — renders :class:`levi.demand.pulse.DemandPulse`
  status and five-factor score cards.

The :data:`SCREENS` registry maps a stable key to ``(title, handler)``.
The menu loop in :mod:`levi.console.app` renders whatever is registered,
so future passes can plug in finance/agent/news screens by:

1. writing a ``screen_*() -> None`` handler in this module (keep it small;
   put prompting-free logic in :mod:`levi.console.helpers`),
2. adding one line to :data:`SCREENS`::

       SCREENS["finance"] = ("Finance", screen_finance)

No other file needs to change. Handlers must never block on ``input()``
when the session is non-interactive — the top-level ``run()`` guard in
:mod:`levi.console.app` rejects non-TTY sessions before any screen runs.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from levi.bounty.pipeline import run_recon
from levi.bounty.scope import ScopeError, ScopeStore, normalize_domain
from levi.bounty.store import FindingStore
from levi.console.helpers import (
    STAGE_LABELS,
    browser_command,
    paginate,
    resolve_view_arg,
    search_domains,
    stage_for_kind,
    tier_color,
)
from levi.demand.pulse import DemandPulse
from levi.ux import (
    ProgressBar,
    Table,
    banner,
    clear_status_line,
    color,
    confirm,
    menu,
    meter,
    pause_for_key,
    status_line,
)

PAGE_SIZE = 15


# ---------------------------------------------------------------------------
# Security index browser
# ---------------------------------------------------------------------------


def _load_domains():
    """Load the security catalog; return None with a clean message on failure."""
    from levi.knowledge.security.catalog import CatalogError, load_catalog

    try:
        return load_catalog().domains
    except CatalogError as exc:
        print(f"Security index unavailable: {exc}")
        print("Restore core/levi/knowledge/security/catalog.json and try again.")
    except OSError as exc:
        print(f"Security index unavailable (read error): {exc}")
    return None


def _print_domain(domain) -> None:
    print(banner(domain.name, f"security domain · {domain.id}"))
    print(str(domain.defensive_summary) + "\n")
    if domain.attack_relevant and domain.attack_profile:
        print(
            color("-- attack profile (threat knowledge, not instructions) --", dim=True)
        )
        print(str(domain.attack_profile) + "\n")
    print(color("-- detection --", dim=True))
    print(str(domain.detection_notes) + "\n")
    print(color("-- hardening --", dim=True))
    print(str(domain.hardening_notes) + "\n")
    print(color("-- key concepts --", dim=True))
    print("  " + ", ".join(str(c) for c in domain.key_concepts) + "\n")
    print(color("-- reference --", dim=True))
    print(f"  {domain.reference}")


def screen_security_browser() -> None:
    """Page, search and inspect the 81-domain offline security index."""
    domains = _load_domains()
    if domains is None:
        pause_for_key()
        return
    if not domains:
        print("The security index is empty.")
        pause_for_key()
        return

    filtered: List = list(domains)
    page = 1
    while True:
        page_items, total_pages = paginate(filtered, page, PAGE_SIZE)
        page = min(page, max(total_pages, 1))
        offset = (page - 1) * PAGE_SIZE
        rows = [[str(offset + i + 1), d.id, d.name] for i, d in enumerate(page_items)]
        print(banner("Security index", f"{len(filtered)} of {len(domains)} domains"))
        Table(["#", "id", "name"], rows).print()
        print(
            f"Page {page}/{max(total_pages, 1)} · "
            "[n]ext [p]rev [s]earch [c]lear [v]iew <n|id> [b]ack"
        )
        action, arg = browser_command(input("> ").strip())
        if action == "back":
            return
        if action == "next":
            page = min(page + 1, max(total_pages, 1))
        elif action == "prev":
            page = max(page - 1, 1)
        elif action == "clear":
            filtered, page = list(domains), 1
        elif action == "search":
            query = input("Search query (blank clears): ").strip()
            filtered = search_domains(domains, query)
            page = 1
            if not filtered:
                print(f"No security domains match {query!r}.")
        elif action == "view":
            domain = resolve_view_arg(domains, page_items, arg)
            if domain is None:
                print(f"Nothing to show for {arg!r} — use the row # or a domain id.")
                continue
            _print_domain(domain)
            pause_for_key()
        else:
            print("Unknown command — n/p/s/c/v/b.")


# ---------------------------------------------------------------------------
# Bounty recon
# ---------------------------------------------------------------------------


class _LiveFindingStore(FindingStore):
    """FindingStore that reports each landing to a callback (live feed).

    ``on_finding(finding, is_new)`` fires after the store accepts the
    finding, so the console can drive a status line and stage progress
    without adding any capability beyond :mod:`levi.bounty.store`.
    """

    def __init__(self, on_finding: Callable, path=None):
        super().__init__(path=path)
        self._on_finding = on_finding

    def add(self, target, scope, kind, detail, evidence=""):  # type: ignore[override]
        finding, is_new = super().add(target, scope, kind, detail, evidence)
        try:
            self._on_finding(finding, is_new)
        except Exception:
            pass  # the feed must never break the run
        return finding, is_new


def _enroll_scope(store: ScopeStore) -> str | None:
    """Prompt for a domain, validate it, enroll it. Returns the domain or None."""
    raw = input("Domain to enroll (blank cancels): ").strip()
    if not raw:
        return None
    try:
        domain = normalize_domain(raw)
    except ValueError as exc:
        print(f"Cannot enroll: {exc}")
        return None
    store.add(domain)
    print(
        f"Enrolled {color(domain, fg='green', bold=True)} — recon is authorized for it and its subdomains."
    )
    return domain


def _run_recon_with_feed(domain: str) -> None:
    bar = ProgressBar(total=len(STAGE_LABELS), label=f"recon: {STAGE_LABELS[0]}")
    bar.set(1)
    reached = 0

    def on_finding(finding, _is_new):
        nonlocal reached
        stage = stage_for_kind(finding.kind)
        if stage > reached:
            reached = stage
            bar.label = f"recon: {STAGE_LABELS[stage]}"
            bar.set(stage + 1)
        status_line(f"[{finding.kind}] {finding.target}: {finding.detail[:72]}")

    live = _LiveFindingStore(on_finding)
    try:
        report = run_recon(domain, findings=live)
    except ScopeError as exc:
        bar.finish()
        clear_status_line()
        print(f"Scope refused: {exc}")
        print("Enroll the domain first — recon only runs inside an enrolled scope.")
        pause_for_key()
        return
    except Exception as exc:  # run_recon degrades internally; this is the last resort
        bar.finish()
        clear_status_line()
        print(f"Recon failed before it could start: {exc}")
        pause_for_key()
        return
    bar.finish()
    clear_status_line()

    findings = list(live.findings.values())
    print(banner("Recon results", domain))
    print(
        f"subdomains={len(report.get('subdomains', []))}  "
        f"hosts_probed={report.get('hosts_probed', 0)}  "
        f"findings_new={report.get('findings_new', 0)}  "
        f"findings_total={len(findings)}"
    )
    if findings:
        rows = [[f.kind, f.target, f.detail[:80]] for f in findings]
        Table(["kind", "target", "detail"], rows).print()
    else:
        print("(no findings)")
    errors = report.get("errors") or []
    if errors:
        print(color("\n-- errors --", fg="yellow", bold=True))
        for err in errors:
            print(f"  ! {err}")
    pause_for_key()


def screen_bounty_recon() -> None:
    """Pick an enrolled scope (or enroll one) and run the recon pipeline."""
    store = ScopeStore()
    while True:
        if not store.domains:
            print(banner("Bounty recon", "no scopes enrolled"))
            print(
                "Recon only runs against enrolled bug-bounty scopes.\n"
                "Enroll a domain you are authorized to test — LEVI will\n"
                "refuse anything outside the enrolled scope."
            )
            if confirm("Enroll a scope now?", default=True):
                if _enroll_scope(store):
                    continue
            return

        options = list(store.domains) + ["Enroll new scope", "Back"]
        choice = menu(options, prompt="Recon target")
        if choice is None or choice == len(options) - 1:
            return
        if choice == len(options) - 2:
            _enroll_scope(store)
            continue
        domain = store.domains[choice]
        if confirm(f"Run recon against {domain}?", default=True):
            _run_recon_with_feed(domain)


# ---------------------------------------------------------------------------
# Demand digest
# ---------------------------------------------------------------------------


def screen_demand_digest() -> None:
    """Show DemandPulse status and the top five-factor score cards."""
    pulse = DemandPulse()
    print(banner("Demand digest", "opportunity intelligence"))
    print(pulse.format_status())
    cards = pulse.top_score_cards(5)
    if not cards:
        print("No score cards yet — score one with: levi demand --five-factor ...")
        pause_for_key()
        return
    rows = []
    for c in cards:
        bar = meter(c.composite, 100)
        tier = color(c.tier, fg=tier_color(c.tier), bold=True)
        flag = color(" ALERT", fg="red", bold=True) if c.alert else ""
        rows.append([f"{c.composite:6.2f}", bar, tier + flag, c.title])
    Table(["score", "meter", "tier", "title"], rows).print()
    print("\nScores are HYPOTHESIS until verified OBSERVED in corpus.")
    pause_for_key()


# ---------------------------------------------------------------------------
# SCREENS registry — the extension point
# ---------------------------------------------------------------------------

#: Menu registry: key -> (title shown in the main menu, handler function).
#: Add future screens (finance, agent, news, ...) here; the menu loop in
#: :mod:`levi.console.app` renders and dispatches them with no other changes.
SCREENS: Dict[str, Tuple[str, Callable[[], None]]] = {
    "security": ("Security index browser", screen_security_browser),
    "bounty": ("Bounty recon", screen_bounty_recon),
    "demand": ("Demand digest", screen_demand_digest),
}
