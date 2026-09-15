# Analyzing Ethereum Smart Contract Vulnerabilities

## Purpose

Smart contracts handle real value and, once deployed, are difficult to patch.
This playbook gives auditors and defenders a repeatable workflow for reviewing
Solidity contracts for the vulnerability classes that have historically caused
losses: reentrancy, access-control failures, unsafe external calls, and
economic/logic flaws. It is written for auditing code you are responsible for —
your own protocol, a dependency, or a contract under formal review.

## When to use

- Pre-deployment audit of a Solidity contract or upgrade.
- Triage of a bug report, audit finding, or post-incident review of an exploit.
- Reviewing a third-party contract your system will integrate with or hold funds in.

See also: auditing-foundry-smart-contract-security.md

## Prerequisites

- Written authorization / engagement scope defining which contracts, repos, and
  networks are in scope. Do not probe mainnet contracts you have no mandate to test.
- The full source tree (or verified source from Etherscan/Sourcify) pinned to a
  commit hash, plus the compiler version and optimizer settings used.
- A local toolchain: Foundry or Hardhat, Slither, and an isolated test network
  (Anvil) — never test exploit hypotheses against mainnet state.

## Procedure

1. Establish the baseline: record repo commit, `pragma solidity` version,
   compiler/optimizer settings, and whether the deployed bytecode matches the
   source (verify via Sourcify or Etherscan "verified" status).
2. Map the trust model: list all privileged roles (`owner`, `admin`, multisig),
   who can upgrade the proxy, and which functions move value. Flag any
   single-key control over funds.
3. Run static analysis first: `slither .` and triage findings by impact.
   Pay special attention to detectors for reentrancy, uninitialized state,
   and dangerous strict equality on balances.
4. Manually review every external call site:
   - Checks-Effects-Interactions ordering — state updates must precede calls.
   - Reentrancy guards on functions that call untrusted contracts or send ETH.
   - Return-value handling: low-level `.call()` must check success; prefer
     pull-payment (withdrawal) patterns over push.
5. Audit access control on each state-changing function: is there a modifier?
   Does `tx.origin` appear anywhere for authorization (it must not — use
   `msg.sender`)? Can `initialize()` be front-run or called twice on proxies?
6. Review arithmetic and logic: Solidity ≥0.8 reverts on overflow, but
   `unchecked` blocks, rounding in division, and precision loss in price math
   still cause loss. Trace token-decimal assumptions end to end.
7. Examine oracle and randomness dependencies: single-source price feeds,
   spot-price use vulnerable to flash-loan manipulation, and `block.timestamp`
   / `blockhash` used as randomness.
8. Check upgradeability hazards: storage-layout collisions between proxy and
   implementation, missing gap variables, and `delegatecall` into untrusted code.
9. Write targeted Foundry tests for each suspected issue, including fuzz tests
   over value-moving functions; confirm or kill each hypothesis with a failing
   test before reporting it.
10. For high-value contracts, run symbolic execution (`myth analyze`) on the
    flagged functions and review any reachable assertion violations.
11. Write findings with: location, impact, likelihood, a minimal proof-of-concept
    test, and a concrete remediation. Separate "funds at risk" from hygiene.

## Key tools & commands

- `slither <target>` — static analysis with 90+ detectors (reentrancy-eth,
  unchecked-transfer, tx-origin, uninitialized-state, etc.).
- `forge test` / `forge test --fuzz-runs 10000` — unit and fuzz testing.
- `anvil` — local Ethereum node for safe exploit-hypothesis testing.
- `myth analyze <contract.sol>` — symbolic execution for deep paths.
- `echidna` — property-based fuzzing for invariants (e.g., "total supply is
  conserved").
- `cast` — chain interaction and bytecode inspection from Foundry.
- SWC Registry (swcregistry.io) — standard weakness classification for findings.

## Expected outputs

- A findings report: each issue with severity, affected code, exploitability
  argument, PoC test, and remediation.
- A clean static-analysis baseline (remaining Slither notes acknowledged).
- Fuzz/invariant test suite covering value-moving functions.
- A sign-off note: compiler settings, verified-source match, and residual risks.

## Pitfalls

- Treating a clean Slither run as proof of safety — logic and economic flaws
  (oracle manipulation, bad incentives) are invisible to static analysis.
- Auditing source that does not match deployed bytecode; always verify the
  deployed contract first.
- Ignoring the proxy: vulnerabilities in upgrade/admin functions bypass every
  safeguard in the implementation contract.
- Testing hypotheses on mainnet or public testnets with real value flows —
  keep everything on Anvil until the finding is confirmed.
- `unchecked` blocks and inline assembly disable the compiler's safety nets;
  review them line by line.

## References

- SWC Registry (swcregistry.io) — smart contract weakness classification
- MITRE-adjacent: CWE-841 (reentrancy), CWE-284 (access control), CWE-829
  (untrusted code inclusion via delegatecall)
- ConsenSys Smart Contract Best Practices; Trail of Bits "Building Secure
  Contracts" checklist
- Slither documentation (github.com/crytic/slither), Foundry Book

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
