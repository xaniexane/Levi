"""Entrypoint tests: python -m levi.knowledge (hermetic, no network)."""

import pytest

from levi.knowledge.__main__ import main


def test_help_exits_zero():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_atlas(capsys):
    assert main(["atlas", "--limit", "3"]) == 0
    assert "capability atlas" in capsys.readouterr().out


def test_security_list(capsys):
    assert main(["security", "--limit", "3"]) == 0
    assert "defensive domains" in capsys.readouterr().out


def test_security_one_domain(capsys):
    assert main(["security", "--domain", "android-security"]) == 0
    assert "Android Security" in capsys.readouterr().out


def test_security_unknown_domain_fails_closed(capsys):
    assert main(["security", "--domain", "nope-not-real"]) == 1


def test_news_cached_days(capsys):
    # read-only over the repo's checked-in news cache: no network
    assert main(["news"]) == 0
    assert "cached news days" in capsys.readouterr().out
