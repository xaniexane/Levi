"""CLI: levi service — the legion service-offering standard.

Any organ, or Levi in general, offers cyber and software-development
services through one pipeline: analyze -> quote -> deliver -> paid
-> showcase.
"""

from __future__ import annotations


def cmd_service(args):
    """levi service offer|analyze|quote|deliver|showcase|lift|teams

    offer PROVIDER TYPE TITLE --problem TEXT [--scope S] [--deadline D]
    analyze <offering-id> --subject S --summary S --finding F --evidence E
            [--severity low] [--confidence 0.8]   (repeat --finding/--evidence pairs)
    quote <offering-id> [--giant-price USD] [--strategy volume|margin]
    deliver <offering-id> --solution TEXT --evidence E [--confidence 0.8]
            [--verification TEXT]
    showcase <offering-id>
    lift <site-dir> [--with-team] [--pack P] [--no-quote] [--giant-price USD]
            [--strategy volume|margin]  (plus the lift attestation flags)
    teams <report-id> [--pack P] [--no-quote] [--giant-price USD]
            [--strategy volume|margin]
    list
    """
    from levi.services.offering import (
        SERVICE_TYPES,
        ServiceStore,
        attach_analysis,
        deliver_service,
        offer_service,
        quote_service,
        showcase_service,
    )

    cmd = getattr(args, "service_cmd", None) or "list"
    store = ServiceStore()

    if cmd == "list":
        items = store.list()
        if not items:
            print("No service offerings yet. Use: levi service offer ...")
            return
        for o in items:
            print(
                f"{o.offering_id} [{o.stage}] {o.provider}/{o.service_type}: {o.title}"
            )
        return

    if cmd == "offer":
        provider = getattr(args, "provider", "")
        stype = getattr(args, "service_type", "")
        title = getattr(args, "title", "")
        if stype not in SERVICE_TYPES:
            print(f"service_type must be one of: {', '.join(sorted(SERVICE_TYPES))}")
            return
        offering = offer_service(
            provider=provider,
            service_type=stype,
            title=title,
            problem=getattr(args, "problem", "") or "",
            scope=getattr(args, "scope", "") or "",
            deadline=getattr(args, "deadline", "") or "",
            client=getattr(args, "client", "") or "",
        )
        print(
            f"Offered: {offering.offering_id} [{offering.provider}/{offering.service_type}]"
        )
        print(f"Bounty: {offering.bounty_id} — next: analyze")
        return

    if cmd == "lift":
        from levi.services.site_lift import (
            AbsorbReturn,
            Compost,
            Graft,
            run_lift_program,
            save_report,
        )

        grafts = []
        for i, pattern in enumerate(getattr(args, "graft", None) or []):
            srcs = getattr(args, "gsource", None) or []
            notes = getattr(args, "gnote", None) or []
            grafts.append(
                Graft(
                    pattern=pattern,
                    source=srcs[i] if i < len(srcs) else "",
                    note=notes[i] if i < len(notes) else "",
                )
            )
        composts = []
        for i, failure in enumerate(getattr(args, "compost", None) or []):
            lessons = getattr(args, "clesson", None) or []
            composts.append(
                Compost(
                    failure=failure,
                    lesson=lessons[i] if i < len(lessons) else "",
                )
            )
        ar = None
        if any(
            getattr(args, k, "")
            for k in ("absorbed", "reversed", "improved", "returned")
        ):
            ar = AbsorbReturn(
                absorbed_from=getattr(args, "absorbed", "") or "",
                reversed_into=getattr(args, "reversed", "") or "",
                improvement=getattr(args, "improved", "") or "",
                returned_form=getattr(args, "returned", "") or "",
                unreplicable_note=getattr(args, "unreplicable", "") or "",
            )
        try:
            report = run_lift_program(
                getattr(args, "site_dir", ""),
                provider=getattr(args, "provider", "levi") or "levi",
                grafts=grafts,
                composts=composts,
                absorb_return=ar,
                showcase_summary=getattr(args, "showcase", "") or "",
            )
        except Exception as e:
            print(f"Lift refused: {e}")
            return
        save_report(report)
        for r in report.rounds:
            ok, total = r.score
            print(f"[{r.round_id}] {r.name}: {ok}/{total}")
            for c in r.checks:
                if not c.passed:
                    print(f"    ✗ {c.label} — {c.evidence}")
        print(
            "goal tally: "
            + ", ".join(
                f"{g}={report.goal_tally.get(g, 0)}"
                for g in ("bring", "retain", "intrigue", "income", "feature")
            )
        )
        print(f"report: {report.report_id}")
        if getattr(args, "with_team", False):
            try:
                match, offer = _team_from_report(report, args)
            except Exception as e:
                print(f"Team match refused: {e}")
                return
            _print_team(match, offer)
        return

    if cmd == "teams":
        from levi.services.site_lift import LiftError, load_report

        try:
            report = load_report(getattr(args, "report_id", ""))
        except LiftError as e:
            print(f"Unknown lift report: {e}")
            return
        if report is None:
            print(f"Unknown lift report {getattr(args, 'report_id', '')!r}")
            return
        try:
            match, offer = _team_from_report(report, args)
        except Exception as e:
            print(f"Team match refused: {e}")
            return
        _print_team(match, offer)
        return

    oid = getattr(args, "offering_id", "")
    offering = store.get(oid)
    if offering is None:
        print(f"Unknown offering {oid!r}")
        return

    if cmd == "analyze":
        findings = []
        raw_findings = getattr(args, "finding", None) or []
        raw_evidence = getattr(args, "evidence_a", None) or []
        raw_sev = getattr(args, "severity", None) or []
        for i, f in enumerate(raw_findings):
            findings.append(
                {
                    "finding": f,
                    "evidence": raw_evidence[i] if i < len(raw_evidence) else "",
                    "severity": raw_sev[i] if i < len(raw_sev) else "info",
                }
            )
        try:
            offering = attach_analysis(
                offering,
                subject=getattr(args, "subject", "") or offering.title,
                summary=getattr(args, "summary", "") or "",
                findings=findings,
                confidence=getattr(args, "confidence", None),
            )
        except Exception as e:
            print(f"Analysis refused: {e}")
            return
        print(f"Analyzed: {offering.offering_id} -> analysis {offering.analysis_id}")
        return

    if cmd == "quote":
        try:
            offering = quote_service(
                offering,
                giant_price=getattr(args, "giant_price", None),
                strategy=getattr(args, "strategy", "volume") or "volume",
                founder_commission=getattr(args, "commission", 0.0) or 0.0,
            )
        except Exception as e:
            print(f"Quote refused: {e}")
            return
        print(f"Quoted: {offering.offering_id} — next: deliver")
        return

    if cmd == "deliver":
        try:
            offering = deliver_service(
                offering,
                solution=getattr(args, "solution", "") or "",
                evidence=getattr(args, "evidence", None) or [],
                confidence=getattr(args, "confidence", None),
                verification=getattr(args, "verification", "") or "",
            )
        except Exception as e:
            print(f"Delivery refused: {e}")
            return
        print(f"Delivered: {offering.offering_id} — next: paid (through Cybrus)")
        return

    if cmd == "showcase":
        try:
            entry = showcase_service(offering)
        except Exception as e:
            print(f"Showcase refused: {e}")
            return
        print(f"Showcased: {entry.entry_id} — {entry.title}")
        return

    print(f"Unknown service command {cmd!r}")


def _team_from_report(report, args):
    """Match a lift report to a tailored team pack and assemble the
    report+crew offer. Returns (match, offer). Raises TeamError on a
    bad pack id, strategy, etc."""
    from levi.services.site_team_match import (
        assemble_offer,
        match_report,
        save_offer,
    )

    match = match_report(report, pack_id=getattr(args, "pack", None) or None)
    offer = assemble_offer(
        report,
        match,
        quote=not getattr(args, "no_quote", False),
        giant_price=getattr(args, "giant_price", None),
        strategy=getattr(args, "strategy", "volume") or "volume",
    )
    save_offer(offer)
    return match, offer


def _print_team(match, offer):
    """Print the crew recommendation + offer. Unmatched findings are
    printed, never dropped."""
    print(f"team pack: {match.pack_title} [{match.pack_id}]")
    for rc in match.coverage:
        fills = ", ".join(f.check_id for f in rc.findings) or "—"
        print(f"  {rc.role_title} [{rc.role_id}]: fills {fills}")
        for f in rc.findings:
            print(f"      • {f.label}")
    if match.unmatched:
        print("unmatched findings — no crew covers these:")
        for f in match.unmatched:
            print(f"  ✗ {f.check_id}: {f.label} — {f.evidence}")
    if offer.quote is not None:
        q = offer.quote
        print(
            f"quote (paper, not a charge): ${q['low_usd']:.2f}-${q['high_usd']:.2f} "
            f"recommended ${q['recommended_usd']:.2f}"
        )
    print(f"offer: {offer.offer_id}")
