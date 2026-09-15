"""Scenario 1 — ``bounty-hunt``: a cinematic simulated bug-bounty recon run.

A deterministic fictional target org (:class:`levi.sim.world.SimWorld`)
is generated from the seed, the pipeline's low-level network functions
are shimmed to serve that world (:class:`levi.sim.shims.SimShim`), and
then the REAL ``levi.bounty.pipeline.run_recon`` orchestration runs
unmodified — scope gate included. The sim domain is auto-enrolled in an
ISOLATED ``ScopeStore`` pointed at a temp dir; the real ``~/.levi``
scope and finding stores are never touched. Findings land in an
ISOLATED ``FindingStore`` (temp dir).

Hard sim laws, restated: a ``SIMULATION`` banner opens and closes the
run, every printed artifact is labeled simulated, and zero real network
I/O happens (the shims replace every network call site; the test suite
proves it by turning ``socket``/``urllib`` into landmines).
"""

from __future__ import annotations

import random
import re
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from levi.bounty.pipeline import run_recon
from levi.bounty.scope import ScopeStore
from levi.bounty.store import FindingStore
from levi.sim.shims import SimShim
from levi.sim.world import SimWorld
from levi.ux import ProgressBar, Spinner, Table, banner, meter, rule, typing_print


@contextmanager
def _sim_time() -> Iterator[None]:
    """Neutralize ``time.sleep`` while the real pipeline runs.

    The pipeline's politeness delays are meaningless against a simulated
    network (there is nothing to be polite to). The orchestration logic
    itself is untouched — this only fast-forwards waiting. Restored on
    exit.
    """
    real_sleep = time.sleep
    time.sleep = lambda _s: None  # type: ignore[assignment]
    try:
        yield
    finally:
        time.sleep = real_sleep  # type: ignore[assignment]


def run(seed: int | None = None) -> int:
    """Run the bounty-hunt simulation. Returns a process exit code."""
    print(
        banner(
            "SIMULATION — BOUNTY HUNT",
            "A fully fictional recon exercise. Every host, banner, "
            "and finding below is simulated.",
        )
    )
    if seed is None:
        seed = random.SystemRandom().randrange(1, 999_999)
        print(f"(no seed given — this run's seed is {seed}; reuse it to replay)")
    seed = int(seed)
    world = SimWorld(seed)

    typing_print(
        f"Contract signed: a bug-bounty program has authorized recon against "
        f"one fictional target — {world.domain} (.test, so it can never be "
        f"a real domain)."
    )
    typing_print(
        "LEVI's real recon pipeline will run tonight: enumeration, probing, "
        "content discovery. The network it touches is simulated; the "
        "orchestration, scope gate, and detectors are the real thing."
    )
    print(rule())

    print(
        banner(
            "CHAPTER 1 — ENUMERATION (SIMULATED)",
            "Passive sources first: certificate transparency, then a "
            "wordlist sweep. Scope gate checks every candidate.",
        )
    )
    typing_print("Pulling certificate transparency logs (simulated crt.sh)...")
    print(
        banner(
            "CHAPTER 2 — PROBING (SIMULATED)",
            "TCP connect-scan on common ports, HTTP(S) fingerprinting, "
            "TLS certificate grab. Scope gate runs before the first packet.",
        )
    )
    typing_print("Knocking on doors that only exist inside the simulation...")
    print(
        banner(
            "CHAPTER 3 — CONTENT DISCOVERY (SIMULATED)",
            "Archived URLs plus JavaScript harvesting: endpoints and "
            "secret-shaped strings are detected and reported, never used.",
        )
    )
    typing_print("Reading old snapshots and script bundles (all fictional)...")
    print(rule())

    with tempfile.TemporaryDirectory(prefix="levi-sim-") as tmp:
        tmpdir = Path(tmp)
        # ISOLATED stores: the real ~/.levi scope/findings are never touched.
        scope = ScopeStore(path=tmpdir / "scope.json")
        scope.add(world.domain)  # auto-enroll the sim domain, isolated
        findings = FindingStore(path=tmpdir / "findings.json")

        with Spinner(
            "Running the REAL recon pipeline against the simulated network..."
        ):
            with SimShim(world):
                with _sim_time():
                    report = run_recon(
                        world.domain, store=scope, findings=findings, delay=0
                    )

        # -- debrief: replay the pipeline's REAL output as a live feed -----
        ordered = list(findings.findings.values())
        stages = [
            ("ENUMERATION", [f for f in ordered if f.kind == "subdomain"]),
            (
                "PROBING",
                [
                    f
                    for f in ordered
                    if f.kind in ("open_port", "http_service", "tls_cert")
                ],
            ),
            (
                "CONTENT",
                [
                    f
                    for f in ordered
                    if f.kind
                    in ("archived_url", "js_endpoint", "possible_exposure")
                ],
            ),
        ]
        print(
            banner(
                "DEBRIEF — LIVE FINDING FEED (SIMULATED)",
                "Everything below was produced by the real pipeline "
                "against the simulated world.",
            )
        )
        for i, (name, items) in enumerate(stages, 1):
            bar = ProgressBar(
                len(items), label=f"STAGE {i}/3 — {name} (simulated replay)"
            )
            for f in items:
                bar.update(1)
                detail = f.detail if len(f.detail) <= 110 else f.detail[:107] + "..."
                print(f"  [SIM] {f.kind:16} {f.target} — {detail}")
            bar.finish()

        if report.get("errors"):
            print("Pipeline errors (simulated run):")
            for err in report["errors"]:  # type: ignore[union-attr]
                print(f"  [SIM] {err}")

        # -- score: coverage of planted assets ------------------------------
        # Exposure findings are deduped by (pattern, js path): the same
        # planted file is fetched once per scheme by the real pipeline,
        # which must not count as two found assets.
        found_subs = set(report["subdomains"])  # type: ignore[arg-type]
        planted_subs = {h.fqdn for h in world.hosts}
        exp_found = {
            re.sub(r"https?://[^/]+", "", f.detail)
            for f in ordered
            if f.kind == "possible_exposure"
        }
        denom = len(planted_subs) + world.planted_exposures
        numer = len(found_subs & planted_subs) + len(exp_found)
        coverage = 100.0 * numer / denom if denom else 100.0
        dark = sorted(planted_subs - found_subs)

        print(rule())
        print(
            banner(
                "HUNT REPORT (SIMULATED)",
                f"Target {world.domain} — fictional. Coverage of planted assets.",
            )
        )
        Table(
            ["Metric", "Value"],
            [
                ["Simulated target", f"{world.domain}  (.test — fictional)"],
                ["Planted subdomains", str(len(planted_subs))],
                ["Subdomains discovered", str(len(found_subs & planted_subs))],
                ["Planted exposures", str(world.planted_exposures)],
                ["Exposures flagged", str(len(exp_found))],
                ["Hosts probed", str(report["hosts_probed"])],
                ["Findings stored (isolated)", str(len(ordered))],
                ["Coverage", f"{coverage:.0f}%  {meter(coverage, 100)}"],
            ],
        ).print()
        if dark:
            typing_print(
                "Blind spots (planted assets the pipeline could not discover — "
                "this is why coverage is not 100%):"
            )
            for fqdn in dark:
                print(f"  [SIM] undiscovered: {fqdn} (simulated DNS NXDOMAIN)")

    print(rule())
    print(
        banner(
            "SIMULATION COMPLETE",
            "Nothing in this run was real: no packets left this machine, "
            "no real domain was named, no real secret was seen.",
        )
    )
    return 0
