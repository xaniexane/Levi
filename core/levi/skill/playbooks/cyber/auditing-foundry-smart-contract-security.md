# Auditing Smart Contract Security with Foundry

## Purpose

Use the Foundry toolchain (`forge`, `cast`, `anvil`) to perform a structured security
audit of Ethereum/EVM smart contracts: compile, test, fuzz, and simulate contracts to find
vulnerabilities before deployment or as part of a pre-launch review.

## When to use

- Pre-deployment security review of a smart contract or protocol upgrade.
- Auditing a forked or inherited codebase (DeFi forks inherit DeFi bugs).
- Reproducing a reported vulnerability against a local fork of mainnet state.
- Continuous security testing in CI for an on-chain codebase.

See also: analyzing-ethereum-smart-contract-vulnerabilities.md

## Prerequisites

- Written authorization and a defined scope: repository/contract addresses in bounds, and
  whether mainnet forking is permitted.
- The contract source code (auditing bytecode-only is a different, harder engagement —
  confirm which you have).
- Foundry installed (`foundryup`), plus a mainnet/testnet RPC endpoint if fork testing is
  in scope.
- Threat model: what the contract holds (funds, governance power, privileged roles) and
  who the untrusted actors are.

## Procedure

1. **Set up and compile.**
   - Run `forge build` and resolve all warnings — warnings about unused returns, shadowing,
     or unchecked calls are audit leads, not noise.
   - Record the solc version actually used (`forge --version` shows the bundled solc) and
     confirm it matches the project's pinned version.

2. **Map the attack surface.**
   - List every `external`/`public` function, who can call it (access control modifiers),
     and what value or state it moves.
   - Identify privileged roles (`owner`, `admin`, multisig), upgradeability proxies, and
     external calls to untrusted contracts.

3. **Review access control first.**
   - For each state-changing function, verify the modifier actually restricts to the
     intended role; check initializers (`initializer` on proxies) can't be front-run.
   - Confirm role adminship isn't a single EOA where a multisig was promised.

4. **Run the existing test suite.**
   - Execute `forge test` and read failures as findings about the code's own assumptions.
   - Check coverage with `forge coverage` — uncovered privileged functions are where bugs
     hide.

5. **Fuzz the invariants.**
   - Write invariant tests (`forge test` with `invariant_` handlers) for properties like
     "total supply equals sum of balances" or "no user can withdraw more than deposited."
   - Run extended fuzz campaigns (`forge test --fuzz-runs 10000` or higher on
     high-value targets); a broken invariant is a confirmed vulnerability class.

6. **Simulate against forked state.**
   - Use `forge test --fork-url <RPC>` or `anvil --fork-url <RPC>` to test the contract
     against real mainnet state and real token contracts.
   - Reproduce reported issues by scripting the exact transaction sequence in a test —
     this is the standard of proof for the report.

7. **Check the classic vulnerability patterns.**
   - Reentrancy (checks-effects-interactions violations, `call` before state updates),
     price-oracle manipulation, access-control gaps, integer issues in pre-0.8 or
     `unchecked` blocks, `tx.origin` authentication, unbounded loops (gas griefing),
     and unsafe delegatecall/proxy patterns.
   - For each, write a proof-of-concept test that demonstrates the impact in wei/terms
     the owner understands.

8. **Review dependencies and configuration.**
   - Audit pinned dependency versions, OpenZeppelin upgrade patterns, and deployment
     scripts (`forge script`) — misconfigured deploy scripts have lost funds.
   - Check `cast` for on-chain verification: `cast code <address>` and constructor args
     match the audited source.

9. **Static analysis pass.**
   - Run Slither (separate tool, pairs naturally with Foundry output) and triage every
     finding; then manually review what static analysis can't see (economic logic, oracle
     assumptions).
   - Do not report raw Slither output as findings — confirm each one with a test.

10. **Write the report.**
    - Each finding: title, severity, affected contract/function, proof-of-concept test,
      impact in concrete terms, and a specific code-level recommendation.
    - Include the exact commit hash audited, solc version, and test commands so the team
      can reproduce everything.

## Key tools & commands

- `forge build`, `forge test`, `forge coverage`, `forge script` — compile, test, coverage,
  deploy.
- `forge test --fork-url <RPC_URL>` / `anvil --fork-url <RPC_URL>` — mainnet fork testing
  and local simulation.
- `cast call|send|code|storage` — inspect and interact with deployed contracts.
- Slither (`slither .`) — static analysis triage input, not final findings.
- `forge fmt` and `solc` warnings — hygiene that surfaces real issues.

## Expected outputs

- Attack surface map: external functions × access control × value at risk.
- Proof-of-concept tests reproducing each confirmed vulnerability.
- Findings with severity, concrete impact, and code-level remediation.
- Reproducibility record: commit hash, solc version, forge version, fork block number.

## Pitfalls

- Auditing the wrong commit — always pin and record the exact hash; code moves fast.
- Fork tests at "latest" block that can't be reproduced later — pin `--fork-block-number`.
- Reporting fuzzer crashes without a minimized, deterministic proof-of-concept.
- Ignoring deployment scripts and proxy admin keys — the contract can be perfect and the
  deployment still compromised.
- Test-only RPC endpoints with different state than mainnet invalidating fork results.

## References

- Foundry Book (Paradigm): forge/cast/anvil reference.
- Solidity documentation: security considerations.
- MITRE-adjacent: smart contracts map loosely to CWE entries — CWE-841 (reentrancy
  behavior), CWE-284 (improper access control), CWE-330/331 (randomness).
- Trail of Bits / Consensys smart contract best-practices guides (public).

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
