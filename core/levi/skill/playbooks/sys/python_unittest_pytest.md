---
skill_id: sys_python_unittest_pytest
name: Python Testing with unittest and pytest
description: Writing tests that catch regressions: structure, fixtures, and what to assert.
risk: info
permissions: []
requires_confirmation: false
tags: [python, tooling]
version: 1.0.0
---
# Python Testing with unittest and pytest

## Purpose

Writing tests that catch regressions: structure, fixtures, and what to assert.

## Overview

Tests encode expected behavior so regressions announce themselves. unittest (stdlib) organizes tests in TestCase classes with assertEqual family methods and setUp/tearDown fixtures; pytest (third-party, the community default) lets plain functions assert directly and rewrites assertions to show values on failure. Either way the anatomy is arrange-act-assert: set up, do the thing, check the outcome. Test behavior, not implementation: assert on outputs and observable effects, not private internals, so refactoring does not break the suite. Fixtures build reusable setup; parametrize runs one test body over many inputs - the highest value-per-line construct in testing. Mock external boundaries (network, filesystem, clocks) with unittest.mock so tests are fast and deterministic; never let unit tests hit the real network. Name tests for the behavior ('rejects_negative_quantity'), keep them independent and order-free, and keep them fast - a slow suite does not get run. Coverage measures which lines ran, not which behaviors are correct; 100% coverage with weak assertions is theater. Run with python -m pytest; in CI, fail the build on test failure. A test you do not run is documentation at best.

## Quick reference

- Arrange-act-assert: setup, execute, verify.

- unittest: TestCase classes (stdlib). pytest: plain functions, rich asserts.

- Parametrize: one test body, many inputs - best value per line.

- Mock external boundaries (network, fs, clocks) with unittest.mock.

- Tests must be independent, order-free, and fast.

- Coverage != correctness: assert behaviors, not just lines.


## Worked example

pytest style: parametrize and tmp_path:

```
import pytest

def total(prices, tax_rate):
    if tax_rate < 0:
        raise ValueError('negative tax')
    return round(sum(prices) * (1 + tax_rate), 2)

@pytest.mark.parametrize('prices,rate,expected', [
    ([10.0], 0.0, 10.0),
    ([10.0, 20.0], 0.1, 33.0),
    ([], 0.2, 0.0),
])
def test_total(prices, rate, expected):
    assert total(prices, rate) == expected

def test_total_rejects_negative_tax():
    with pytest.raises(ValueError):
        total([10.0], -0.1)
```

- parametrize multiplies one test across input cases.

- pytest.raises asserts the error path, not just the happy path.

- Plain assert with rewritten introspection on failure.


## Common mistakes

- Tests that depend on execution order or shared mutable state.
  Fix: Each test sets up its own fixtures; random order should pass.

- Asserting implementation details (private methods, call counts).
  Fix: Assert observable behavior so refactors do not break the suite.


## Quick checks

Q: How many tests is enough?
A: Cover the contract: happy paths, boundaries (empty, zero, max), error paths, and the tricky branches. Diminishing returns set in past that; more valuable is keeping the suite fast so it actually runs.


Q: When should I mock vs use the real thing?
A: Mock at trust boundaries: network, filesystem, time, randomness - anything slow, flaky, or outside your control. Use the real thing for your own pure logic and in a smaller set of integration tests.


## Mental model

Tests are the guardrails on a mountain road: they do not drive the car (implementation), they just make sure it cannot silently go off the cliff it avoided yesterday. Parametrize is one guardrail design stamped out for every curve.
