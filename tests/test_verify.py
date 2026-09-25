"""Hermetic tests for levi.verify — the pre-digital proof rituals."""

import subprocess
import sys

import pytest

from levi.verify import (
    VerificationReceipt,
    check_product,
    check_sum,
    crossfoot,
    dual_path,
    elevens,
    format_sigfigs,
    nines,
    sigfigs_in,
    to_sigfigs,
)


# -- casting out nines -------------------------------------------------------


def test_nines_basics():
    assert nines(9) == 0
    assert nines(18) == 0
    assert nines(12345) == 6
    assert nines(0) == 0


def test_nines_sign_is_cast_out_with_digits():
    assert nines(-27) == nines(27) == 0


def test_nines_rejects_non_int():
    with pytest.raises(TypeError):
        nines(True)
    with pytest.raises(TypeError):
        nines(1.5)


def test_check_sum_passes_on_correct():
    r = check_sum([123, 456], 579)
    assert isinstance(r, VerificationReceipt)
    assert r.ok and r.method == "cast-out-nines"


def test_check_sum_fails_on_digit_error():
    r = check_sum([123, 456], 580)
    assert not r.ok
    assert "digit-root" in r.detail


def test_nines_honest_limit_transposition_passes():
    # Documented limit: nines cannot see transpositions. 597 is 579 transposed.
    r = check_sum([123, 456], 597)
    assert r.ok  # the ritual is a net, not a proof — stated in the docstring


# -- casting out elevens ------------------------------------------------------


def test_elevens_basics():
    assert elevens(121) == 0  # 1-2+1
    assert elevens(12345) == 3  # 5-4+3-2+1
    assert 0 <= elevens(999999999) <= 10


def test_elevens_catches_transposition():
    assert elevens(12) != elevens(21)


def test_check_product_both_rituals_pass():
    receipts = check_product(12, 34, 408)
    assert len(receipts) == 2
    assert all(r.ok for r in receipts)
    assert {r.method for r in receipts} == {"cast-out-nines", "cast-out-elevens"}


def test_check_product_elevens_catches_transposed_claim():
    # 480 is 408 with digits swapped: nines is blind to it, elevens is not.
    receipts = check_product(12, 34, 480)
    by_method = {r.method: r for r in receipts}
    assert by_method["cast-out-nines"].ok
    assert not by_method["cast-out-elevens"].ok


def test_check_product_wrong_fails_both():
    receipts = check_product(12, 34, 409)
    assert not any(r.ok for r in receipts)


# -- crossfoot ----------------------------------------------------------------


def _good_table():
    # data 2x2, last row = column totals, last col = row totals, corner = grand
    return [
        [10, 20, 30],
        [40, 50, 90],
        [50, 70, 120],
    ]


def test_crossfoot_consistent_table_passes():
    r = crossfoot(_good_table())
    assert r.ok and r.method == "crossfoot"


def test_crossfoot_names_bad_row():
    bad = [row[:] for row in _good_table()]
    bad[1][2] = 91  # row 1 states a wrong total
    r = crossfoot(bad)
    assert not r.ok
    assert "row 1" in r.detail


def test_crossfoot_names_bad_column():
    bad = [row[:] for row in _good_table()]
    bad[2][0] = 51  # column 0 total is wrong
    r = crossfoot(bad)
    assert not r.ok
    assert "column 0" in r.detail


def test_crossfoot_bad_grand_total():
    bad = [row[:] for row in _good_table()]
    bad[2][2] = 121
    r = crossfoot(bad)
    assert not r.ok
    assert "grand total" in r.detail


def test_crossfoot_rejects_ragged_and_tiny():
    with pytest.raises(ValueError):
        crossfoot([[1, 2], [3]])
    with pytest.raises(ValueError):
        crossfoot([[1]])


def test_crossfoot_rejects_non_int_cells():
    with pytest.raises(TypeError):
        crossfoot([[1, 2.5, 3], [4, 5, 9], [5, 7, 12]])


# -- dual path -----------------------------------------------------------------


def test_dual_path_agreement():
    r = dual_path(lambda x: x + x, lambda x: 2 * x, 21)
    assert r.ok and r.method == "dual-path"


def test_dual_path_disagreement_fails():
    r = dual_path(lambda x: x + x, lambda x: x * x, 3)
    assert not r.ok
    assert "disagree" in r.detail


def test_dual_path_exception_is_recorded_not_raised():
    def boom(x):
        raise RuntimeError("kaput")

    r = dual_path(boom, lambda x: x, 1)
    assert not r.ok
    assert "raised" in r.detail and "RuntimeError" in r.detail


def test_dual_path_rejects_non_callables():
    with pytest.raises(TypeError):
        dual_path(42, lambda x: x, 1)


# -- honest precision -----------------------------------------------------------


def test_to_sigfigs_kills_false_precision():
    assert to_sigfigs(0.30000000000000004, 1) == 0.3
    assert to_sigfigs(12345, 2) == 12000.0
    assert to_sigfigs(0, 5) == 0.0


def test_to_sigfigs_rejects_bad_sig():
    with pytest.raises(ValueError):
        to_sigfigs(1.0, 0)


def test_format_sigfigs_exact_digits():
    assert format_sigfigs(0.3, 3) == "0.300"
    assert format_sigfigs(12345, 2) == "12000"
    assert format_sigfigs(5, 3) == "5.00"
    assert format_sigfigs(0, 2) == "0.0"


def test_sigfigs_in_counts():
    assert sigfigs_in("0.0300") == 3
    assert sigfigs_in("1200") == 2  # ambiguous trailing zeros not claimed
    assert sigfigs_in("1200.") == 4  # decimal point claims them
    assert sigfigs_in("0") == 1
    assert sigfigs_in("3.14159") == 6


def test_sigfigs_in_rejects_garbage():
    with pytest.raises(ValueError):
        sigfigs_in("abc")
    with pytest.raises(ValueError):
        sigfigs_in("")


# -- CLI ------------------------------------------------------------------------


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "levi.verify", *args],
        capture_output=True,
        text=True,
        cwd="/home/hatch/workspace/levi/core",
    )


def test_cli_check_sum_pass_and_fail():
    ok = _run_cli("check-sum", "123", "456", "--result", "579")
    assert ok.returncode == 0 and "PASS" in ok.stdout
    bad = _run_cli("check-sum", "123", "456", "--result", "580")
    assert bad.returncode == 1 and "FAIL" in bad.stdout


def test_cli_check_product():
    out = _run_cli("check-product", "12", "34", "--result", "408")
    assert out.returncode == 0


def test_cli_digit_root_and_sigfigs():
    out = _run_cli("digit-root", "12345")
    assert out.returncode == 0 and "nines: 6" in out.stdout
    out = _run_cli("sigfigs", "0.30000000000000004", "--sig", "1")
    assert out.returncode == 0 and out.stdout.strip() == "0.3"


def test_cli_malformed_input_is_exit_2():
    out = _run_cli("sigfigs", "1.5", "--sig", "0")
    assert out.returncode == 2
