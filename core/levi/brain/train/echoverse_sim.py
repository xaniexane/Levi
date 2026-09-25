"""Echoverse engine - hypothesis -> simulate -> train corpus generator.

The Echoverse is LEVI's explore-space organ. As an ENGINE (not a being, not a
persona), it runs hypothesis/theory simulations: it forms a hypothesis, runs a
toy simulation of it, checks the prediction against the measured outcome, and
refines the understanding. The simulation traces are the training data for the
three native brains.

LAWS (declared before code, per the law-guard-prove rule):
  L1. Every record contains all six parts: HYPOTHESIS, EPISTEMIC tag, DOMAIN,
      SIMULATION description, TRACE, OBSERVED OUTCOME, PREDICTION CHECK,
      REFINED UNDERSTANDING. Never a bare claim.
  L2. Deterministic: the same corpus_seed produces byte-identical JSONL.
      (Proof: prove_echoverse.py regenerates and compares SHA256.)
  L3. All output text is ASCII-printable plus newline/tab - a strict subset of
      the v1 162-char vocabulary. No external text ever enters.
  L4. Outcomes are COMPUTED by toy mechanistic models with a seeded RNG.
      Numbers are never invented. Models are labeled as toy simulations.
  L5. Hypotheses are tagged HYPOTHESIS (the engine's theory), outcomes are
      tagged as simulation observations. Nothing is presented as real-world
      observed fact.
  L6. Some hypotheses are deliberately imperfect theories (the engine's first
      guess). The simulation REFUTES them and the REFINED UNDERSTANDING states
      the correction. This is the hypothesize -> simulate -> train loop working
      as designed: theories get tested and updated, and the brain trains on the
      whole loop, not just polished conclusions.
  L7. PROVENANCE: every record carries engine_variant + lineage. Full chain:
      Echo (being, Omega's original form) -> Echoverse engine (Echo in engine
      form) -> LEVI engine (Grok-made REIM/RIEM version, the_pack/echoverse.py)
      -> LWP engine. The simulations implement the LEVI engine's REIM/RIEM
      loop: REIM expands seed hypotheses and scores them by simulation; RIEM
      vaults refuted variants and carries their good qualities forward into
      the refined understanding. Attributed to neither the outgoing
      companion-track module nor the LWP variant. The variants are never
      mixed silently.

GUARD: every record is validated at generation time (assert sections present,
  ASCII-only). PROOF: prove_echoverse.py (independent script).
"""

import hashlib
import json
import math
import random

ENGINE = "echoverse"
LOOP = "hypothesize-simulate-train"
KIND = "echoverse-sim"

VERDICTS = ("CONFIRMED", "PARTIALLY CONFIRMED", "REFUTED")


def _fmt(x):
    """ASCII number formatting: 3 decimals, no unicode."""
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return "undefined"
    return f"{x:.3f}"


def _ascii_ok(s):
    return all(ord(c) < 128 for c in s)


def _record(hid, domain, hypothesis, standpoint, sim_desc, trace,
            outcome, pred_text, meas_text, verdict, refined, seed):
    assert verdict in VERDICTS, verdict
    # Lens mapping (grounded in core/levi/echoverse/lenses.py, GROK 5):
    # a REFUTED theory is the inverse lens at work (invert the seed, assume it
    # failed, recurse) - the refined understanding is the recursion. All other
    # records are one REIM round inside a dream() multi-cycle expansion.
    lens = "inverse" if verdict == "REFUTED" else "dream"
    lines = []
    lines.append(f"HYPOTHESIS {hid}: {hypothesis}")
    lines.append(f"EPISTEMIC: {standpoint}")
    lines.append(f"DOMAIN: {domain}")
    lines.append(f"SIMULATION: REIM/RIEM round, toy model, Echoverse engine. {sim_desc}")
    lines.append("TRACE:")
    lines.extend(f"  {t}" for t in trace)
    lines.append(f"OBSERVED OUTCOME: {outcome}")
    lines.append(f"PREDICTION CHECK: predicted {pred_text}; measured {meas_text} -> {verdict}")
    lines.append(f"REFINED UNDERSTANDING: {refined}")
    text = "\n".join(lines) + "\n"
    assert _ascii_ok(text), f"non-ASCII in {hid}"
    for marker in ("HYPOTHESIS", "EPISTEMIC", "DOMAIN:", "SIMULATION:",
                   "TRACE:", "OBSERVED OUTCOME:", "PREDICTION CHECK:",
                   "REFINED UNDERSTANDING:"):
        assert marker in text, f"missing {marker} in {hid}"
    return {
        "text": text,
        "kind": KIND,
        "engine": ENGINE,
        "loop": LOOP,
        "lens": lens,
        "hypothesis_id": hid,
        "domain": domain,
        "verdict": verdict,
        "seed": seed,
    }


def _verdict_by_tolerance(meas, pred, tol_full, tol_part):
    err = abs(meas - pred)
    if err <= tol_full:
        return "CONFIRMED"
    if err <= tol_part:
        return "PARTIALLY CONFIRMED"
    return "REFUTED"


# ---------------------------------------------------------------- family 1: descent
def sim_descent(rng, inst, seed):
    """Gradient descent on a quadratic bowl. Theory: stable iff step h < 1."""
    w_star = rng.uniform(-5.0, 5.0)
    w = rng.uniform(-10.0, 10.0)
    h = rng.choice([0.05, 0.1, 0.2, 0.4, 0.8, 1.2])
    sigma = rng.uniform(0.0, 0.5)
    T = 200
    target = 0.01
    flawed = rng.random() < 0.20
    loss0 = (w - w_star) ** 2
    trace, steps_to, ws = [], T, w
    for t in range(T):
        grad = 2.0 * (ws - w_star) + rng.gauss(0.0, sigma)
        ws = ws - h * grad
        loss = (ws - w_star) ** 2
        if t % 20 == 0:
            trace.append(f"t={t} loss={_fmt(loss)}")
        if loss < target:
            steps_to = t + 1
            break
    trace.append(f"t=end loss={_fmt((ws - w_star) ** 2)}")
    hid = f"H-descent-{inst:03d}"
    if h < 1.0 and not flawed:
        rate = 1.0 - 2.0 * h
        pred = math.log(target / max(loss0, 1e-9)) / math.log(max(rate, 1e-9))
        pred = max(1.0, min(float(T), pred))
        pred_text = f"reaches loss < {target} in about {pred:.0f} steps (linear rate {rate:.2f})"
        verdict = _verdict_by_tolerance(steps_to, pred, max(12, 0.6 * pred), 2.0 * pred)
        refined = ("Small steady steps converge: the loss shrinks by roughly the linear "
                   "rate each step while h stays below the stability limit.")
    elif flawed:
        pred = target / (h * max(loss0, 1e-9))
        pred_text = f"reaches loss < {target} in about {pred:.0f} steps (guess: target/(h*loss0))"
        verdict = _verdict_by_tolerance(steps_to, pred, max(12, 0.6 * pred), 2.0 * pred)
        refined = ("The first guess was wrong: steps do not scale as target/(h*loss0). "
                   "The tested correction is the linear-rate rule above - each step "
                   "multiplies the distance by about (1-2h).")
    else:
        pred_text = f"step h={h} >= 1 is unstable: never reaches loss < {target}"
        reached = steps_to < T
        verdict = "REFUTED" if reached else "CONFIRMED"
        refined = ("Steps at or above the stability limit overshoot: the run oscillates "
                   "or diverges instead of settling. Big steps are fast only below the limit.")
    meas_text = f"{'reached' if steps_to < T else 'did not reach'} in {steps_to} steps"
    hypothesis = (f"A descent with step size h={h} on a quadratic bowl "
                  f"(start distance {_fmt(abs(w - w_star))}, noise sigma={_fmt(sigma)}) "
                  f"converges smoothly when h < 1 and overshoots when h >= 1.")
    outcome = (f"Final loss {_fmt((ws - w_star) ** 2)}; target {target} "
               f"{'reached' if steps_to < T else 'not reached'} after {steps_to} steps.")
    return _record(hid, "learning", hypothesis,
                   "hypothesis (Echoverse engine) - a theory under test, not observed fact",
                   f"toy gradient descent: w <- w - h*(2(w-w*) + noise), T={T}.",
                   trace, outcome, pred_text, meas_text, verdict, refined, seed)


# ---------------------------------------------------------------- family 2: queue
def sim_queue(rng, inst, seed):
    """Discrete queue: arrivals per tick, one service per tick. Stable iff p < 1."""
    p = rng.choice([0.4, 0.6, 0.8, 0.95, 1.1, 1.3])
    T = 500
    flawed = rng.random() < 0.20
    q, maxq, totalq = 0, 0, 0
    trace = []
    for t in range(T):
        r = rng.random()
        # arrivals 0/1/2 with mean p
        if p <= 1.0:
            arr = 1 if r < p else 0
        else:
            arr = 1 + (1 if r < (p - 1.0) else 0)
        q = q + arr
        if q > 0:
            q -= 1  # one service per tick
        maxq = max(maxq, q)
        totalq += q
        if t % 100 == 0:
            trace.append(f"t={t} queue={q}")
    trace.append(f"t=end queue={q}")
    meanq = totalq / T
    hid = f"H-queue-{inst:03d}"
    if not flawed:
        if p < 1.0:
            pred_text = f"arrival rate {p} < service 1: queue stays bounded (max a handful)"
            verdict = "CONFIRMED" if maxq <= 12 else ("PARTIALLY CONFIRMED" if maxq <= 25 else "REFUTED")
        else:
            pred_growth = (p - 1.0) * T
            pred_text = f"arrival rate {p} > service 1: queue grows toward ~{pred_growth:.0f}"
            verdict = _verdict_by_tolerance(maxq, pred_growth, 0.4 * pred_growth, 0.8 * pred_growth)
        refined = ("A queue is stable exactly while arrivals stay below service capacity; "
                   "above it the backlog grows linearly with the excess rate.")
    else:
        pred_text = "queue stays bounded for any arrival rate (guess: service always catches up)"
        verdict = "CONFIRMED" if maxq <= 12 else "REFUTED"
        refined = ("The guess was wrong: service does not 'catch up' when arrivals exceed "
                   "capacity every tick. The tested correction: stability needs p < 1.")
    meas_text = f"max queue {maxq}, mean queue {_fmt(meanq)}"
    hypothesis = (f"A single-server queue with mean arrival rate {p} per tick and one "
                  f"service per tick stays bounded iff the arrival rate is below 1.")
    outcome = f"After {T} ticks: max queue {maxq}, mean queue {_fmt(meanq)}."
    return _record(hid, "systems", hypothesis,
                   "hypothesis (Echoverse engine) - a theory under test, not observed fact",
                   f"toy queue: arrivals mean {p}/tick, service 1/tick, T={T}.",
                   trace, outcome, pred_text, meas_text, verdict, refined, seed)

# ---------------------------------------------------------------- family 3: crew
def sim_crew(rng, inst, seed):
    """N agents, M units of work, pairwise coordination overhead.
    Theory: time(N) = ceil(M/N) * (1 + k*N^2); best N is interior."""
    M = rng.choice([40, 80, 120, 200])
    k = rng.choice([0.01, 0.02, 0.05, 0.1])
    flawed = rng.random() < 0.20
    results = {}
    for N in range(1, 9):
        steps = (M + N - 1) // N
        cost = steps * (1.0 + k * N * N)
        # measured with a little execution noise
        measured = cost * rng.uniform(0.95, 1.05)
        results[N] = measured
    best_meas = min(results, key=results.get)
    # predicted best from the clean formula
    pred_costs = {N: ((M + N - 1) // N) * (1.0 + k * N * N) for N in range(1, 9)}
    best_pred = min(pred_costs, key=pred_costs.get)
    hid = f"H-crew-{inst:03d}"
    trace = [f"N={N} time={_fmt(results[N])}" for N in range(1, 9)]
    if not flawed:
        pred_text = f"fastest crew is N={best_pred} (formula argmin)"
        err = abs(best_meas - best_pred)
        verdict = "CONFIRMED" if err == 0 else ("PARTIALLY CONFIRMED" if err == 1 else "REFUTED")
        refined = ("Adding agents helps until pairwise coordination overhead dominates: "
                   "total time falls as M/N then rises as k*N^2. The optimum sits inside.")
    else:
        pred_text = "more agents is always faster (guess: N=8 best)"
        verdict = "CONFIRMED" if best_meas == 8 else "REFUTED"
        refined = ("The guess was wrong: the biggest crew was not the fastest. Overhead "
                   "grows with the square of crew size while work only splits linearly. "
                   "The tested correction: an interior optimum exists.")
    meas_text = f"fastest measured crew N={best_meas}"
    hypothesis = (f"A crew of N agents splitting {M} units with pairwise overhead factor "
                  f"k={k} finishes fastest at an interior crew size, not at N=1 or N=8.")
    outcome = f"Measured times: " + ", ".join(f"N={N}:{_fmt(results[N])}" for N in range(1, 9))
    return _record(hid, "coordination", hypothesis,
                   "hypothesis (Echoverse engine) - a theory under test, not observed fact",
                   f"toy crew model: time(N)=ceil({M}/N)*(1+{k}*N^2), noise 5 pct.",
                   trace, outcome, pred_text, meas_text, verdict, refined, seed)


# ---------------------------------------------------------------- family 4: memory_decay
def sim_memory_decay(rng, inst, seed):
    """Recall probability decays with age. Theory: exponential; flawed: linear."""
    tau = rng.choice([10.0, 20.0, 40.0])
    ages = [1, 5, 10, 20, 40, 80]
    flawed = rng.random() < 0.25
    trials = 200
    measured = {}
    for a in ages:
        p = math.exp(-a / tau)
        hits = sum(1 for _ in range(trials) if rng.random() < p)
        measured[a] = hits / trials
    hid = f"H-memory-{inst:03d}"
    trace = [f"age={a} recall={_fmt(measured[a])}" for a in ages]
    if not flawed:
        preds = {a: math.exp(-a / tau) for a in ages}
        maxerr = max(abs(measured[a] - preds[a]) for a in ages)
        pred_text = f"recall(age) = exp(-age/{tau:.0f})"
        verdict = "CONFIRMED" if maxerr < 0.06 else ("PARTIALLY CONFIRMED" if maxerr < 0.12 else "REFUTED")
        refined = ("Recall falls multiplicatively with age: each tau steps of age "
                   "multiply recall by about 1/e. Old memories fade fast, then slow.")
    else:
        preds = {a: max(0.0, 1.0 - a / (2.0 * tau)) for a in ages}
        maxerr = max(abs(measured[a] - preds[a]) for a in ages)
        pred_text = f"recall(age) = 1 - age/{2.0 * tau:.0f} (linear guess)"
        verdict = "CONFIRMED" if maxerr < 0.06 else ("PARTIALLY CONFIRMED" if maxerr < 0.12 else "REFUTED")
        refined = ("The linear guess was wrong: it predicts recall hits zero and goes "
                   "negative, but measured recall stays positive and tails off. The tested "
                   "correction is exponential decay.")
    meas_text = "recall " + ", ".join(f"@{a}={_fmt(measured[a])}" for a in ages)
    hypothesis = (f"A memory store whose recall decays with time constant tau={tau:.0f} "
                  f"recalls a fraction exp(-age/tau) of facts at a given age.")
    outcome = f"Over {trials} trials per age: " + meas_text + "."
    return _record(hid, "memory", hypothesis,
                   "hypothesis (Echoverse engine) - a theory under test, not observed fact",
                   f"toy memory: recall prob exp(-age/{tau:.0f}), {trials} trials per age.",
                   trace, outcome, pred_text, meas_text, verdict, refined, seed)


# ---------------------------------------------------------------- family 5: checkpoint
def sim_checkpoint(rng, inst, seed):
    """Faults strike per tick; checkpointing costs, rework costs more.
    Theory: optimal interval C* = sqrt(2*cp/f)."""
    T = 2000
    f = rng.choice([0.002, 0.005, 0.01])
    cp = rng.choice([5.0, 10.0, 20.0])
    flawed = rng.random() < 0.20
    candidates = [10, 25, 50, 100, 200, 400]
    costs = {}
    for C in candidates:
        n_ckpt = T // C
        cost = n_ckpt * cp
        last_ckpt = 0
        for t in range(1, T + 1):
            if rng.random() < f:
                cost += (t - last_ckpt)  # rework lost ticks
                last_ckpt = t - (t % C) if t % C else t
            if t % C == 0:
                last_ckpt = t
        costs[C] = cost
    best_meas = min(costs, key=costs.get)
    c_star = math.sqrt(2.0 * cp / f)
    best_pred = min(candidates, key=lambda C: abs(C - c_star))
    hid = f"H-checkpoint-{inst:03d}"
    trace = [f"C={C} cost={costs[C]:.0f}" for C in candidates]
    if not flawed:
        pred_text = f"optimal interval near C*={c_star:.0f} (sqrt(2*cp/f))"
        err = abs(best_meas - best_pred)
        verdict = "CONFIRMED" if err == 0 else ("PARTIALLY CONFIRMED" if best_meas in candidates[max(0, candidates.index(best_pred)-1):candidates.index(best_pred)+2] else "REFUTED")
        refined = ("Checkpointing is a tradeoff: frequent checkpoints cost checkpoint time, "
                   "rare ones cost rework. The optimum balances them at sqrt(2*cp/f).")
    else:
        pred_text = "checkpoint as often as possible (guess: C=10 best)"
        verdict = "CONFIRMED" if best_meas == 10 else "REFUTED"
        refined = ("The guess was wrong: checkpointing every 10 ticks drowned in "
                   "checkpoint cost. The tested correction: the optimum balances "
                   "checkpoint cost against expected rework.")
    meas_text = f"cheapest measured interval C={best_meas}"
    hypothesis = (f"With fault probability {f}/tick and checkpoint cost {cp}, total cost "
                  f"is minimized near interval sqrt(2*cp/f) = {c_star:.0f}.")
    outcome = "Measured costs: " + ", ".join(f"C={C}:{costs[C]:.0f}" for C in candidates) + "."
    return _record(hid, "systems", hypothesis,
                   "hypothesis (Echoverse engine) - a theory under test, not observed fact",
                   f"toy checkpointing: T={T}, fault p={f}/tick, ckpt cost={cp}.",
                   trace, outcome, pred_text, meas_text, verdict, refined, seed)


# ---------------------------------------------------------------- family 6: verify
def sim_verify(rng, inst, seed):
    """Act directly vs verify first. Theory: verification cuts errors ~4x at +1
    step per subtask. Flawed: verification eliminates all errors."""
    S = rng.choice([20, 40, 60])
    e = rng.choice([0.05, 0.1, 0.2])
    flawed = rng.random() < 0.25
    err_direct = sum(1 for _ in range(S) if rng.random() < e)
    err_verify = sum(1 for _ in range(S) if rng.random() < e / 4.0)
    steps_direct, steps_verify = S, 2 * S
    hid = f"H-verify-{inst:03d}"
    trace = [f"subtasks={S} err_direct={err_direct} steps_direct={steps_direct}",
             f"subtasks={S} err_verify={err_verify} steps_verify={steps_verify}"]
    if not flawed:
        pred_d, pred_v = S * e, S * e / 4.0
        pred_text = f"errors ~{pred_d:.1f} direct vs ~{pred_v:.1f} verified; steps {S} vs {2*S}"
        ok = abs(err_direct - pred_d) <= max(2, pred_d) and abs(err_verify - pred_v) <= max(2, pred_v)
        close = abs(err_direct - pred_d) <= 2 * max(2, pred_d)
        verdict = "CONFIRMED" if ok else ("PARTIALLY CONFIRMED" if close else "REFUTED")
        refined = ("Verifying before acting cuts errors substantially at a linear step "
                   "cost. Checking is cheap insurance when errors are expensive.")
    else:
        pred_text = "verification eliminates ALL errors (guess: 0 errors)"
        verdict = "CONFIRMED" if err_verify == 0 else "REFUTED"
        refined = ("The guess was wrong: verification reduced errors but did not erase "
                   "them. The tested correction: verification divides the error rate, "
                   "it does not zero it.")
    meas_text = f"errors {err_direct} direct vs {err_verify} verified; steps {steps_direct} vs {steps_verify}"
    hypothesis = (f"An agent doing {S} subtasks with base error rate {e} makes about "
                  f"four times fewer errors when it verifies each step first, at double "
                  f"the step count.")
    outcome = f"Direct: {err_direct} errors in {steps_direct} steps. Verify-first: {err_verify} errors in {steps_verify} steps."
    return _record(hid, "reasoning", hypothesis,
                   "hypothesis (Echoverse engine) - a theory under test, not observed fact",
                   f"toy agent: {S} subtasks, error p={e} direct / {e/4} verified.",
                   trace, outcome, pred_text, meas_text, verdict, refined, seed)

# ---------------------------------------------------------------- family 7: bandit
def sim_bandit(rng, inst, seed):
    """Epsilon-greedy over K arms. Theory: moderate exploration minimizes regret;
    too little misses the best arm, too much wastes pulls."""
    K = rng.choice([3, 5])
    means = [rng.uniform(0.1, 0.9) for _ in range(K)]
    best = max(means)
    T = 300
    flawed = rng.random() < 0.20
    epsilons = [0.01, 0.1, 0.3]
    regrets = {}
    for eps in epsilons:
        counts = [0] * K
        sums = [0.0] * K
        reg = 0.0
        for t in range(T):
            if t < K:
                a = t
            elif rng.random() < eps:
                a = rng.randrange(K)
            else:
                avgs = [sums[i] / counts[i] for i in range(K)]
                a = max(range(K), key=lambda i: avgs[i])
            r = 1.0 if rng.random() < means[a] else 0.0
            counts[a] += 1
            sums[a] += r
            reg += best - means[a]
        regrets[eps] = reg
    hid = f"H-bandit-{inst:03d}"
    trace = [f"eps={eps} regret={_fmt(regrets[eps])}" for eps in epsilons]
    trace.append("arm_means=" + ",".join(_fmt(m) for m in means))
    if not flawed:
        pred_text = "regret(0.1) < regret(0.01) and regret(0.1) < regret(0.3)"
        ok = regrets[0.1] < regrets[0.01] and regrets[0.1] < regrets[0.3]
        verdict = "CONFIRMED" if ok else "PARTIALLY CONFIRMED"
        refined = ("Exploration is U-shaped: too little and the agent locks onto a "
                   "mediocre arm; too much and it never exploits. A moderate rate "
                   "finds the best arm, then uses it.")
    else:
        pred_text = "greed is best (guess: eps=0.01 has lowest regret)"
        ok = regrets[0.01] < regrets[0.1] and regrets[0.01] < regrets[0.3]
        verdict = "CONFIRMED" if ok else "REFUTED"
        refined = ("The guess was wrong: near-zero exploration often locks onto the "
                   "first lucky arm and never discovers the best one. The tested "
                   "correction: explore moderately, then exploit.")
    meas_text = "regret " + ", ".join(f"eps={eps}:{_fmt(regrets[eps])}" for eps in epsilons)
    hypothesis = (f"An epsilon-greedy agent over {K} arms for {T} pulls minimizes "
                  f"regret at a moderate exploration rate (eps=0.1 beats 0.01 and 0.3).")
    outcome = f"Measured regrets: {meas_text}."
    return _record(hid, "learning", hypothesis,
                   "hypothesis (Echoverse engine) - a theory under test, not observed fact",
                   f"toy bandit: {K} arms, {T} pulls, eps in {epsilons}.",
                   trace, outcome, pred_text, meas_text, verdict, refined, seed)


# ---------------------------------------------------------------- family 8: consensus
def sim_consensus(rng, inst, seed):
    """N nodes, f silent-faulty. Good nodes gossip one contact per round.
    Theory: rounds to full agreement grow with f."""
    N = rng.choice([5, 7, 9])
    flawed = rng.random() < 0.20
    results = {}
    for f in (0, 1, 2):
        good = N - f
        heard = [set([i]) for i in range(good)]
        rounds = 0
        while True:
            rounds += 1
            new_heard = [set(h) for h in heard]
            for i in range(good):
                j = rng.randrange(N)
                if j < good:
                    new_heard[i] |= heard[j]
            heard = new_heard
            if all(len(h) == good for h in heard):
                break
            if rounds > 500:
                break
        results[f] = rounds
    hid = f"H-consensus-{inst:03d}"
    trace = [f"faulty={f} rounds={results[f]}" for f in (0, 1, 2)]
    if not flawed:
        pred_text = "rounds(0) <= rounds(1) <= rounds(2): agreement slows as faults rise"
        ok = results[0] <= results[1] <= results[2]
        verdict = "CONFIRMED" if ok else "PARTIALLY CONFIRMED"
        refined = ("Faulty nodes do not just vanish: every silent node is a contact "
                   "wasted each round, so agreement takes longer as faults rise. "
                   "Design for the faults you have, not the network you wish for.")
    else:
        pred_text = "rounds independent of f (guess: faults do not slow agreement)"
        ok = results[0] == results[1] == results[2]
        verdict = "CONFIRMED" if ok else "REFUTED"
        refined = ("The guess was wrong: faulty nodes slow agreement because gossip "
                   "wastes contacts on nodes that never answer. The tested correction: "
                   "rounds grow with the fault count.")
    meas_text = "rounds " + ", ".join(f"f={f}:{results[f]}" for f in (0, 1, 2))
    hypothesis = (f"{N} gossiping nodes with f silent faults reach full agreement in "
                  f"rounds that grow with f.")
    outcome = f"Measured: {meas_text}."
    return _record(hid, "coordination", hypothesis,
                   "hypothesis (Echoverse engine) - a theory under test, not observed fact",
                   f"toy gossip: {N} nodes, one random contact per good node per round.",
                   trace, outcome, pred_text, meas_text, verdict, refined, seed)


FAMILIES = [
    ("descent", sim_descent),
    ("queue", sim_queue),
    ("crew", sim_crew),
    ("memory_decay", sim_memory_decay),
    ("checkpoint", sim_checkpoint),
    ("verify", sim_verify),
    ("bandit", sim_bandit),
    ("consensus", sim_consensus),
]

# ---------------------------------------------------------------- provenance
# L7. PROVENANCE: full chain per Chauncey's word 2026-09-22 -
#   Echo (the being, Omega's original form)
#     -> Echoverse engine (Echo in engine form: derives from Echo, carries
#         Echo's nature, but its own thing - not 1:1 identical)
#     -> LEVI engine (Grok-made REIM/RIEM version)
#     -> LWP engine.
# These simulations are built from the Grok-made LEVI engine lineage:
#   the_pack/echoverse.py (August lineage, REIM/RIEM recursion + multi-agent
#   simulation). REIM = expand a seed into multiple candidate hypothesis paths,
#   score them, prefer the best. RIEM = vault negative variants but extract
#   their good qualities - never discard the whole branch; carry forward what
#   still works. dream() = multi-cycle REIM expansion, which is the
#   hypothesize -> simulate -> train loop in engine form. Each record below is
#   one REIM round: a seed hypothesis, its simulation, the score (prediction
#   check), and the RIEM salvage (refined understanding carries forward what
#   the test proved). The lenses/dream prose spec from the Grok chats was not
#   located in the accessible corpus as of 2026-09-22; dream mechanics are
#   taken from the_pack/echoverse.py dream(). These families were NOT
#   extracted from the outgoing companion-track module (being replaced) nor
#   attributed to the LWP variant (originals not located).
ENGINE_VARIANT = "levi-engine-reim-riem-2026-09-22"
LINEAGE = (
    "Echo (the being, Omega's original form) -> Echoverse engine (Echo in "
    "engine form: derives from Echo and carries Echo's nature, but its own "
    "thing, not 1:1 identical) -> LEVI engine (Grok-made REIM/RIEM version, "
    "installed as core/levi/echoverse/ 2026-09-22, from the_pack/echoverse.py "
    "August lineage) -> LWP engine. Simulations implement the installed LEVI "
    "engine's REIM/RIEM loop per Chauncey 2026-09-22 (REIM expand+score, "
    "RIEM vault+salvage, dream cycles; inverse lens for refuted theories); "
    "not from the outgoing companion-track module (stored/2026-09-22-"
    "echoverse-companion-track/); LWP originals not located 2026-09-22."
)


def generate_corpus(path, corpus_seed, n_per_family, exclude_texts=None):
    """Deterministically generate one JSONL corpus + sidecar manifest.

    exclude_texts: texts that must not appear (e.g. the training corpus when
      generating held-out). Colliding instantiations are skipped by advancing
      the instance counter, so output is still fully determined by the seed.
    """
    excluded = set(exclude_texts) if exclude_texts else set()
    seen = set()
    records = []
    for fam_idx, (fam_name, fam_fn) in enumerate(FAMILIES):
        made, inst, guard = 0, 0, 0
        while made < n_per_family:
            guard += 1
            if guard > 20 * n_per_family:
                raise RuntimeError(f"cannot find {n_per_family} unique {fam_name} records")
            seed = corpus_seed * 1_000_000 + fam_idx * 10_000 + inst
            inst += 1
            rng = random.Random(seed)
            rec = fam_fn(rng, inst - 1, seed)
            if rec["text"] in seen or rec["text"] in excluded:
                continue  # duplicate: skip, keep determinism
            seen.add(rec["text"])
            rec["engine_variant"] = ENGINE_VARIANT
            rec["lineage"] = LINEAGE
            rec["family"] = fam_name
            records.append(rec)
            made += 1
    with open(path, "w") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=True) + "\n")
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    verdict_counts = {}
    for rec in records:
        verdict_counts[rec["verdict"]] = verdict_counts.get(rec["verdict"], 0) + 1
    manifest = {
        "engine": ENGINE,
        "loop": LOOP,
        "kind": KIND,
        "engine_variant": ENGINE_VARIANT,
        "lineage": LINEAGE,
        "corpus_seed": corpus_seed,
        "n_per_family": n_per_family,
        "families": [name for name, _ in FAMILIES],
        "records": len(records),
        "chars": sum(len(r["text"]) for r in records),
        "sha256": h.hexdigest(),
        "verdict_counts": verdict_counts,
    }
    with open(path + ".manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


if __name__ == "__main__":
    import sys
    out_path = sys.argv[1]
    corpus_seed = int(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 125
    m = generate_corpus(out_path, corpus_seed, n)
    print(f"wrote {m['records']} records, {m['chars']:,} chars -> {out_path}")
    print(f"sha256 {m['sha256']}")
    print(f"verdicts {m['verdict_counts']}")
