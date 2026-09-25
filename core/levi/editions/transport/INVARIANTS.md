# HOS Co-Pilot — Invariants

**Status:** LAW. Written 2026-09-23 (CDT), before any implementation.
Keeper approval: Wave 1 approved 2026-09-23 ~02:00 CDT.
Module: `core/levi/editions/transport/hos_copilot/`
Proof artifact: `tests/test_transport_hos_copilot.py` (invariant checks + property tests).
Commit gate: every property test below must be green before commit.

These are the FMCSA hours-of-service rules as *checked logic* — the
co-pilot computes against them, never advises around them. They are
advisory to humans: the edition flags, the driver and dispatcher decide.

---

## INV-1 — The projector never approves a violating plan

The four checked rules, in plain words:

1. **11-hour driving limit:** total driving time on a plan must not exceed
   the driver's remaining drive clock.
2. **14-hour window:** total on-duty time (driving + dwell + inserted
   breaks) must not exceed the driver's remaining shift clock.
3. **30-minute break:** no continuous driving stretch may exceed the
   driver's remaining time-to-break. The projector *inserts* the break
   and names its mile marker instead of failing the plan.
4. **70-hour / 8-day cycle:** total on-duty time on the plan must not
   exceed the driver's remaining cycle clock.

A projection is `legal` **if and only if** `check_plan()` returns zero
violations. The simulator and the checker are separate code paths that
must agree — the property tests machine-check this agreement over
randomized clocks and routes.

Proof (in tests):
- `prop_legal_implies_*`: over 200 randomized clock/route pairs, a
  `legal` projection never exceeds any of the four clocks.
- `prop_sim_checker_agree`: `projection.legal` equals
  "checker found zero violations" on every randomized pair.
- Canonical cases: fresh clock + 700 mi @ 60 mph burns the 11 at mile
  660 (break called at mile 480); a 10.2-hour shift clock on a 640-mile
  run burns the 14 at mile ~585 with the break called at mile 480 —
  the 0.5h break sits inside the 14-hour window, so the window dies
  earlier than the no-break math would say.

## INV-2 — Advisory only; humans own the clock

Alerts go to the driver and dispatcher as flags with mile markers and
plain-language reasons. The edition:

- never dispatches a fatigued driver (a `legal == False` projection is
  never presented as runnable),
- never reroutes around weigh stations or inspections,
- never overrides, extends, or "fixes" an HOS limit,
- never presents itself as certifying FMCSA/DOT compliance.

There is deliberately **no** `accept()` / `dispatch()` / `tender()`
method on the shortlist. Ranking is data; binding a load is a human act.
A test asserts the method does not exist.

## INV-3 — Read-only ELD, always

The co-pilot *consumes* clock snapshots under the fleet's own
credentials and never writes anything back:

- Motive: read scopes `available_time`, `hours_of_service`,
  `hos_violations` — interface declared, live wiring pending the
  fleet's own developer app. No endpoint path is fabricated here.
- Samsara: `GET https://api.samsara.com/fleet/hos/clocks` (vendor-confirmed
  2026-09-23), token scope `Read ELD Compliance Settings (US)`.
  The JSON field map is marked `FIELD_MAP_PROVISIONAL = True` and must
  be verified against a live vendor response during fleet onboarding —
  a test pins that flag so it cannot silently become "verified".

There are no live credentials in this repo and no test fleet. All
development and tests run on `FixtureProvider` — four realistic,
deterministic sample clocks. Every adapter declares `read_only = True`;
a test pins it.

## INV-4 — Log falsification is a hard refusal

Any request to coach, automate, or assist ELD/HOS log falsification —
falsifying, faking, cheating, spoofing, cooking logs, double-logging,
ghost logs, driving off the books, hiding drive time, unplugging or
disabling the ELD, abusing personal-conveyance or yard-move status to
hide driving — is refused with a stated reason:

> "Safety law is a hard floor: HOS rules keep fatigued drivers off the
> road. The edition never coaches, automates, or assists log
> falsification."

The gate is keyword-intent based and tested both ways: evasion phrasings
are refused; legitimate questions ("how many drive hours do I have
left?", "log my 30-minute break", "how do I annotate a log error") pass
through untouched.

## INV-5 — The shortlist is ranked, never auto-accepted

`build_shortlist()` returns only driver/load pairs whose projection is
`legal`, ranked deterministically (deadhead ascending, rate-per-mile
descending). The shortlist carries `requires_human_accept = True` and
`auto_accept = False` as data. There is no code path from a shortlist
to a bound contract.

---

## Honest limits (what this build is not)

- **Fixtures only.** No live ELD credentials, no test fleet, no
  production end-to-end run. The Motive adapter is an interface +
  scope declaration; the Samsara adapter has real HTTP plumbing but a
  provisional field map.
- **Simplified HOS model.** The checker implements the four headline
  rules. It does not model sleeper-berth splits, adverse driving
  conditions, short-haul exceptions, or state-level variations. Fleets
  with those operations need the model extended and re-proved.
- **Commercial items remain owner-level:** Truckstop Systems Integration
  Agreement, DAT Developer Portal access, per-fleet ELD scope grants.
- **Certifications are the edition's own** when courses ship in Wave 2 —
  real training with real receipts, never presented as FMCSA/state
  accreditation.
- Regulatory compliance is tracked, not guaranteed: the co-pilot flags
  risks; it does not certify compliance and does not represent the fleet
  before regulators.
