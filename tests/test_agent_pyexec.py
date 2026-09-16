"""Tests for the agent tools added in the image-gen/agentic-automation wave:

* image_generate (local backend — deterministic, no network)
* python_exec (sandboxed execution: cwd jail, timeout, env scrub)

No network, no user HOME writes: HOME is monkeypatched to a tmp dir and
urllib is guarded to fail loudly if any call slips through.
"""

import pytest

from levi.agent.tools import ExecContext, build_default_registry


def _reg(tmp_path, **kwargs):
    kwargs.setdefault("workspace_root", tmp_path / "ws")
    kwargs.setdefault("memory_dir", tmp_path / "mem")
    kwargs.setdefault("skills_dir", tmp_path / "skills")
    return build_default_registry(**kwargs)


@pytest.fixture(autouse=True)
def _guard(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import urllib.request

    def _boom(*a, **k):
        raise AssertionError("network touched in test")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    # re-point media default dirs computed at import time
    from levi.media import local as local_mod

    monkeypatch.setattr(local_mod, "DEFAULT_DIR", tmp_path / "media" / "local")
    return tmp_path


def _ctx():
    return ExecContext()


# -- image_generate -----------------------------------------------------------


def test_image_generate_registered(tmp_path):
    reg = _reg(tmp_path)
    assert reg.get("image_generate") is not None


def test_image_generate_local_backend(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute(
        "image_generate",
        {
            "prompt": "a red circle",
            "backend": "local",
            "width": 48,
            "height": 32,
            "seed": 5,
        },
        _ctx(),
    )
    assert res.ok, res.error
    assert "local procedural image" in res.output
    assert (tmp_path / "media" / "local").exists()


def test_image_generate_default_is_offline(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute(
        "image_generate", {"prompt": "offline check", "width": 32, "height": 24}, _ctx()
    )
    assert res.ok, res.error
    assert "local procedural image" in res.output


def test_image_generate_requires_prompt(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("image_generate", {"prompt": "   "}, _ctx())
    assert not res.ok and "prompt" in res.error


def test_image_generate_bad_backend(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("image_generate", {"prompt": "x", "backend": "dalle"}, _ctx())
    assert not res.ok and "backend" in res.error


def test_image_generate_sd_fails_closed(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("image_generate", {"prompt": "x", "backend": "sd"}, _ctx())
    assert not res.ok
    assert "diffusers" in res.error


# -- python_exec ----------------------------------------------------------------


def test_python_exec_registered(tmp_path):
    assert _reg(tmp_path).get("python_exec") is not None


def test_python_exec_basic(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("python_exec", {"code": "print(40 + 2)"}, _ctx())
    assert res.ok, res.error
    assert "42" in res.output


def test_python_exec_requires_code(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("python_exec", {"code": "  "}, _ctx())
    assert not res.ok and "code" in res.error


def test_python_exec_nonzero_exit(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("python_exec", {"code": "raise SystemExit(3)"}, _ctx())
    assert not res.ok
    assert "exit code 3" in res.error


def test_python_exec_cwd_jailed(tmp_path):
    reg = _reg(tmp_path)
    # attempt to escape the workspace: must land inside the jail, not outside
    res = reg.execute(
        "python_exec",
        {"code": "open('escaped.txt', 'w').write('x')", "cwd": "sub"},
        _ctx(),
    )
    assert res.ok, res.error
    assert (tmp_path / "ws" / "sub" / "escaped.txt").is_file()
    assert not (tmp_path / "escaped.txt").exists()


def test_python_exec_cwd_escape_blocked(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("python_exec", {"code": "print(1)", "cwd": "../../.."}, _ctx())
    assert not res.ok


def test_python_exec_timeout_validation(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute("python_exec", {"code": "print(1)", "timeout": 500}, _ctx())
    assert not res.ok and "timeout" in res.error


def test_python_exec_stderr_captured(tmp_path):
    reg = _reg(tmp_path)
    res = reg.execute(
        "python_exec", {"code": "import sys; sys.stderr.write('oops')"}, _ctx()
    )
    assert res.ok, res.error
    assert "oops" in res.output


def test_python_exec_no_staging_file_left(tmp_path):
    reg = _reg(tmp_path)
    reg.execute("python_exec", {"code": "print('clean')"}, _ctx())
    leftovers = list((tmp_path / "ws" / "agent_scratch").glob("_agent_exec.py"))
    assert leftovers == []
