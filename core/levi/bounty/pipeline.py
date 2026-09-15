"""Recon orchestration: enum -> probe -> content -> store.

``run_recon(domain)`` is the single entry point. The scope gate runs at
entry (via check_scope in every stage — enum, probe, content each gate
independently, defense in depth). Returns a run report dict; every
finding stored carries the scope entry that authorized it.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from levi.bounty import content as content_mod
from levi.bounty import enum as enum_mod
from levi.bounty import probe as probe_mod
from levi.bounty.scope import ScopeStore, check_scope, normalize_domain
from levi.bounty.store import FindingStore


def run_recon(
    domain: str,
    store: Optional[ScopeStore] = None,
    findings: Optional[FindingStore] = None,
    ports: Optional[List[int]] = None,
    delay: float = 0.5,
) -> Dict[str, object]:
    """Run the full recon pipeline against an in-scope domain.

    Raises ScopeError before any network touch if the domain is not enrolled.
    """
    scope = store or ScopeStore()
    fstore = findings or FindingStore()
    scope_entry = check_scope(domain, scope)  # gate at entry
    target = normalize_domain(domain)
    started_at = datetime.now(timezone.utc).isoformat()

    report: Dict[str, object] = {
        "domain": target,
        "scope": scope_entry,
        "started_at": started_at,
        "subdomains": [],
        "hosts_probed": 0,
        "findings_new": 0,
        "findings_total": 0,
        "errors": [],
    }
    seen_ids: List[str] = []

    def _add(tgt: str, kind: str, detail: str, evidence: str = "") -> None:
        finding, is_new = fstore.add(tgt, scope_entry, kind, detail, evidence)
        seen_ids.append(finding.id)
        if is_new:
            report["findings_new"] += 1  # type: ignore[operator]

    try:
        subs = enum_mod.enumerate_subdomains(
            target, store=scope, delay=delay
        )
    except Exception as exc:  # resolvable errors never crash a run
        report["errors"].append(f"enum: {exc}")
        subs = []
    report["subdomains"] = [s["subdomain"] for s in subs]

    hosts = [target] + [s["subdomain"] for s in subs]
    for s in subs:
        _add(
            s["subdomain"], "subdomain", f"resolves to {', '.join(s['ips'])}",
            evidence=f"source={s['source']}",
        )

    page_bodies: Dict[str, str] = {}
    for host in hosts:
        try:
            facts = probe_mod.probe_host(host, store=scope, ports=ports, delay=delay)
        except Exception as exc:
            report["errors"].append(f"probe {host}: {exc}")
            continue
        report["hosts_probed"] += 1  # type: ignore[operator]
        for port in facts["open_ports"]:
            _add(host, "open_port", f"tcp/{port} open")
        for label, hf in facts["http"].items():  # type: ignore[union-attr]
            tech = "; ".join(hf.get("tech", []))  # type: ignore[union-attr]
            detail = f"{label} -> {hf.get('status')}"  # type: ignore[union-attr]
            if hf.get("title"):  # type: ignore[union-attr]
                detail += f" title={hf['title']!r}"  # type: ignore[index]
            if tech:
                detail += f" [{tech}]"
            _add(host, "http_service", detail)
            # stash one body for JS harvesting (re-fetch is wasteful;
            # page_bodies expects url->html; probe doesn't return bodies,
            # so content.py fetches the page itself when given none)
        tls = facts.get("tls") or {}
        if tls:
            _add(
                host, "tls_cert",
                f"subject={tls.get('subject', '?')} not_after={tls.get('not_after', '?')}",
                evidence=f"issuer={tls.get('issuer', '?')}",
            )

    try:
        content = content_mod.collect_content(
            target, store=scope, page_bodies=page_bodies
        )
    except Exception as exc:
        report["errors"].append(f"content: {exc}")
        content = {"archived_urls": [], "js_files": []}

    for url in content.get("archived_urls", []):  # type: ignore[union-attr]
        _add(target, "archived_url", url[:300])
    for js in content.get("js_files", []):  # type: ignore[union-attr]
        for ep in js.get("endpoints", [])[:20]:  # type: ignore[union-attr]
            _add(target, "js_endpoint", f"{js['js_url'][:120]} -> {ep}")  # type: ignore[index]
        for exp in js.get("possible_exposures", []):  # type: ignore[union-attr]
            _add(
                target, "possible_exposure",
                f"{exp} pattern in {js['js_url'][:120]}",  # type: ignore[index]
                evidence="verify manually — pattern match only, never tested",
            )

    fstore.record_run(target, started_at, seen_ids)
    report["findings_total"] = len(seen_ids)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    return report


def run_monitor(
    store: Optional[ScopeStore] = None,
    findings: Optional[FindingStore] = None,
    ports: Optional[List[int]] = None,
    delay: float = 0.5,
) -> Dict[str, object]:
    """Recon every enrolled scope; report only what's new since last time."""
    scope = store or ScopeStore()
    fstore = findings or FindingStore()
    per_domain: Dict[str, Dict[str, object]] = {}
    for dom in scope.list():
        try:
            per_domain[dom] = run_recon(
                dom, store=scope, findings=fstore, ports=ports, delay=delay
            )
        except Exception as exc:
            per_domain[dom] = {"domain": dom, "error": str(exc)}
    new = fstore.new_since_last_run()
    return {"domains": per_domain, "new_findings": [f.to_dict() for f in new]}
