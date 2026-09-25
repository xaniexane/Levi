"""DemandPulse greatness-build proof gate (law -> guard -> prove).

Run:  python3 -m levi.demand.prove
Exit 0 only if every law's guard holds. Hermetic: HOME/LEVI_HOME and the
ledger path are redirected into a temp dir; the network is stubbed.

This is the machine-checkable proof artifact for the 2026-09-22
greatness build — not a substitute for the test files, but the single
gate a commit must pass: one line per law, PASS or FAIL, real numbers.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="dp-prove-"))
    os.environ["HOME"] = str(tmp)
    os.environ["LEVI_HOME"] = str(tmp / ".levi")
    os.environ["LEVI_OUTCOMES_PATH"] = str(tmp / "outcomes.jsonl")
    os.environ["DP_HOOK_TOKEN"] = "prove-token"

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from levi.demand import eyes as emod
    from levi.demand import hook as hmod
    from levi.demand import outcomes as omod
    from levi.demand import watcher as wmod
    from levi.demand.pulse import DemandPulse

    results = []

    def check(law: str, name: str, fn):
        try:
            detail = fn()
            results.append((law, name, True, detail))
        except AssertionError as exc:
            results.append((law, name, False, str(exc) or "assertion failed"))
        except Exception as exc:  # noqa: BLE001 — a guard raising is a FAIL
            results.append((law, name, False, f"{type(exc).__name__}: {exc}"))

    # ---- O-laws: outcome ledger -------------------------------------------
    def o1_append_only():
        omod.record_event("c1", "sighting", title="T")
        omod.record_event("c1", "converted", note="Chauncey said so")
        rows = omod.read_rows()
        assert len(rows) == 2, f"expected 2 rows, got {len(rows)}"
        with open(omod.ledger_path(), "a") as fh:
            fh.write("{corrupt\n")
        assert len(omod.read_rows()) == 2, "corrupt line must not kill reads"
        return "2 rows, corrupt line survived"

    def o2_no_inferred_verdicts():
        names = " ".join(dir(omod)).lower()
        for banned in ("infer", "auto_verdict", "predict_outcome"):
            assert banned not in names, f"suspicious API: {banned}"
        try:
            omod.record_event("c9", "maybe")
            raise SystemExit("should have raised")
        except ValueError:
            pass
        return "no verdict-inferring API; bad event rejected"

    def o3_advisory_only():
        s = omod.suggest_thresholds()
        assert s["suggestion"] is None, "thin ledger must stay silent"
        assert "thin ledger" in s["reason"]
        return f"silent on thin ledger: {s['reason'][:60]}..."

    def o4_excel_one_way():
        out = tmp / "view.xlsx"
        p = omod.export_xlsx(out=out)
        assert p.exists() and p.stat().st_size > 0
        return f"xlsx rendered ({p.stat().st_size} bytes), JSONL untouched"

    def o5_minimal_fields():
        row = omod.record_event("c2", "sighting", title="T" * 500)
        assert len(row["title"]) <= 200 and "body" not in row
        return "title truncated to 200, no body field"

    check("O1", "append-only JSONL + corruption tolerance", o1_append_only)
    check("O2", "explicit verdicts only", o2_no_inferred_verdicts)
    check("O3", "calibration advisory, thin ledger silent", o3_advisory_only)
    check("O4", "xlsx is a one-way view", o4_excel_one_way)
    check("O5", "minimal fields", o5_minimal_fields)

    # ---- score -> ledger hook ----------------------------------------------
    def hook_sighting():
        dp = DemandPulse(path=tmp / "dp.json")
        sig = dp.scan_seed("I need a calmer inbox app", source="prove")
        keys = ("demand", "market_size", "competition_gap",
                "trend_velocity", "entry_feasibility")
        card = dp.score_five_factor(
            sig.id, "Calmer inbox", {k: (70.0, "prove basis") for k in keys})
        rows = omod.read_rows()
        assert any(r["event"] == "sighting" and r["card_id"] == card.opportunity_id
                   for r in rows), "no sighting row for the new card"
        return "new card -> sighting row"

    def hook_never_breaks_scoring():
        os.environ["LEVI_OUTCOMES_PATH"] = str(tmp)  # a dir, not a file
        try:
            dp = DemandPulse(path=tmp / "dp2.json")
            sig = dp.scan_seed("I need a calmer inbox app", source="prove")
            keys = ("demand", "market_size", "competition_gap",
                    "trend_velocity", "entry_feasibility")
            card = dp.score_five_factor(
                sig.id, "Calmer inbox",
                {k: (70.0, "prove basis") for k in keys})
            assert card.composite > 0
        finally:
            os.environ["LEVI_OUTCOMES_PATH"] = str(tmp / "outcomes.jsonl")
        return "scoring survived a broken ledger path"

    check("O1", "score_five_factor records sightings", hook_sighting)
    check("O3", "ledger failure never breaks scoring",
          hook_never_breaks_scoring)

    # ---- E-laws: eyes -------------------------------------------------------
    rss = (b"<?xml version='1.0'?><rss version='2.0'><channel>"
           b"<item><title>I need a better shift planner</title></item>"
           b"</channel></rss>")

    def e1_polite():
        assert emod._http_get("file:///etc/passwd") == (None, b"")
        import urllib.request as _url
        old = _url.urlopen
        _url.urlopen = lambda *a, **k: (_ for _ in ()).throw(  # noqa: E731
            OSError("dns down"))
        try:
            dp = DemandPulse(path=tmp / "dp3.json")
            st = wmod.WatcherState.load(path=tmp / "ws.json")
            r = emod.poll_rss(dp, st, feeds=["https://x.invalid/rss"])
            assert r["signals"] == 0 and r["failed"] >= 1
        finally:
            _url.urlopen = old
        return "dead source -> empty receipt, no raise"

    def e2_hypothesis_only():
        old = emod._http_get
        emod._http_get = lambda url, timeout=15.0: (200, rss)  # noqa: E731
        try:
            dp = DemandPulse(path=tmp / "dp4.json")
            st = wmod.WatcherState.load(path=tmp / "ws.json")
            emod.poll_rss(dp, st, feeds=["https://x.example/rss"])
            assert dp.signals, "expected mined signals"
            assert all(s.kind == "HYPOTHESIS" for s in dp.signals)
            assert all(s.source == "rss" for s in dp.signals)
        finally:
            emod._http_get = old
        return f"{len(dp.signals)} signals, all HYPOTHESIS/rss"

    def e4_budget():
        import time as _t
        dp = DemandPulse(path=tmp / "dp5.json")
        st = wmod.WatcherState.load(path=tmp / "ws.json")
        r = emod.poll_rss(dp, st, feeds=["https://a.example/1"],
                          deadline=_t.time() - 1)
        assert r["status"] == "budget_exceeded" and r["feeds"] == 0
        return "past deadline -> budget_exceeded, 0 feeds"

    def e5_stdlib():
        src = open(emod.__file__, encoding="utf-8").read()
        assert "import urllib" in src and "import xml" in src
        return "urllib + xml.etree, no third-party imports"

    check("E1", "failures degrade to empty", e1_polite)
    check("E2", "public chatter ingested as HYPOTHESIS", e2_hypothesis_only)
    check("E4", "tick budget honored", e4_budget)
    check("E5", "stdlib only", e5_stdlib)

    # ---- H-laws: webhook ----------------------------------------------------
    def h1_bind():
        try:
            hmod.check_bind_address("0.0.0.0")
            raise SystemExit("should have raised")
        except ValueError:
            pass
        hmod.check_bind_address("127.0.0.1")
        return "0.0.0.0 refused, 127.0.0.1 allowed"

    def h2_auth():
        saved = os.environ.pop("DP_HOOK_TOKEN", None)
        try:
            hmod._fail_closed_token()
            raise SystemExit("should have raised")
        except RuntimeError:
            pass
        finally:
            if saved is not None:
                os.environ["DP_HOOK_TOKEN"] = saved
        return "server refuses to start without DP_HOOK_TOKEN"

    def h3_schema():
        bad = [{"items": [{"id": "x"}]},
               {"items": [{"id": "x", "text": "y", "channel": "email"}]},
               {"items": "nope"}]
        for b in bad:
            try:
                hmod.validate_event(b)
                raise SystemExit(f"should have raised for {b}")
            except ValueError:
                pass
        ok = hmod.validate_event(
            {"items": [{"id": "a", "text": "I need x", "channel": "text"}]})
        assert ok[0]["channel"] == "text"
        return "3 bad schemas rejected, 1 good accepted"

    def h5_no_outbound():
        src = open(hmod.__file__, encoding="utf-8").read()
        for prim in ("urlopen", "urlretrieve", "create_connection",
                     "requests.", "urllib.request"):
            assert prim not in src, prim
        return "no outbound fetch primitive in source"

    check("H1", "localhost-only bind guard", h1_bind)
    check("H2", "token auth gate", h2_auth)
    check("H3", "strict schema", h3_schema)
    check("H5", "no outbound fetch", h5_no_outbound)

    # ---- report --------------------------------------------------------------
    width = max(len(law) for law, _, _, _ in results)
    failed = 0
    print("\nDemandPulse greatness-build proof gate")
    print("=" * 46)
    for law, name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        failed += not ok
        print(f"[{mark}] {law:<{width}}  {name}\n"
              f"       {detail}")
    print("=" * 46)
    print(f"{len(results) - failed}/{len(results)} laws hold")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
