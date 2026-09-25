"""Entrypoint tests: python -m levi.console (hermetic, no network).

The console refuses to run without an interactive terminal, so under
pytest (no tty) main() must return 1 with an explanation — it must
never hang on input().
"""

import pytest

from levi.console.__main__ import main


def test_help_exits_zero():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_refuses_noninteractive(capsys):
    # pytest stdin/stdout are not ttys: deterministic refusal, no hang
    assert main([]) == 1
    assert "interactive terminal" in capsys.readouterr().out
