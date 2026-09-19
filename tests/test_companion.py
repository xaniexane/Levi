"""Tests for levi.companion -- on-device on-demand hands."""

import stat


from levi import companion


def _make_bin(tmp_path, monkeypatch, name, script):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    exe = bin_dir / name
    exe.write_text(script)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + __import__("os").environ["PATH"])
    return exe


def test_off_device_everything_unavailable(monkeypatch):
    # With no termux binaries on PATH, every tool fails cleanly.
    monkeypatch.setattr(companion, "_which", lambda name: None)
    assert companion.on_device() is False
    assert companion.available() == {
        "termux-sms-list": False,
        "termux-sms-send": False,
        "termux-screenshot": False,
    }
    assert companion.read_sms().ok is False
    assert companion.send_sms("+12175550123", "hi", confirmed=True).ok is False
    assert companion.read_screen().ok is False


def test_send_sms_requires_confirmation():
    r = companion.send_sms("+12175550123", "hello")
    assert r.ok is False
    assert "confirmed" in r.detail


def test_send_sms_validates_recipient_and_length():
    assert companion.send_sms("nope", "hi", confirmed=True).ok is False
    assert companion.send_sms("+12175550123", "   ", confirmed=True).ok is False
    assert companion.send_sms("+12175550123", "x" * 501, confirmed=True).ok is False


def test_send_sms_happy_path_with_fake_binary(tmp_path, monkeypatch):
    _make_bin(tmp_path, monkeypatch, "termux-sms-send", "#!/bin/sh\nexit 0\n")
    r = companion.send_sms("+12175550123", "hello", confirmed=True)
    assert r.ok is True
    assert r.as_dict()["data"]["to"] == "+12175550123"


def test_send_sms_binary_failure_reported(tmp_path, monkeypatch):
    _make_bin(
        tmp_path,
        monkeypatch,
        "termux-sms-send",
        '#!/bin/sh\necho "permission denied" >&2\nexit 1\n',
    )
    r = companion.send_sms("+12175550123", "hello", confirmed=True)
    assert r.ok is False
    assert "permission denied" in r.detail


def test_read_sms_parses_fake_binary(tmp_path, monkeypatch):
    _make_bin(
        tmp_path,
        monkeypatch,
        "termux-sms-list",
        '#!/bin/sh\necho \'[{"address":"+1555","body":"hello there"}]\'\n',
    )
    r = companion.read_sms(limit=5)
    assert r.ok is True
    assert r.data["messages"][0]["body"] == "hello there"


def test_read_sms_bad_json_reported(tmp_path, monkeypatch):
    _make_bin(tmp_path, monkeypatch, "termux-sms-list", "#!/bin/sh\necho 'not json'\n")
    r = companion.read_sms()
    assert r.ok is False


def test_organize_dry_run_then_real(tmp_path):
    d = tmp_path / "downloads"
    d.mkdir()
    (d / "photo.jpg").write_text("img")
    (d / "report.pdf").write_text("doc")
    (d / "mystery.xyz").write_text("keep")
    (d / ".hidden.jpg").write_text("dotfile")

    preview = companion.organize(str(d), dry_run=True)
    assert preview.ok is True
    assert len(preview.data["moves"]) == 2
    assert (d / "photo.jpg").exists(), "dry run must not move anything"

    done = companion.organize(str(d))
    assert done.ok is True and done.data["moved"] == 2
    assert (d / "Images" / "photo.jpg").exists()
    assert (d / "Documents" / "report.pdf").exists()
    assert (d / "mystery.xyz").exists()
    assert (d / ".hidden.jpg").exists(), "dotfiles are never moved"


def test_organize_missing_dir(tmp_path):
    r = companion.organize(str(tmp_path / "nope"))
    assert r.ok is False


def test_tools_manifest_lists_classes():
    manifest = companion.tools()
    assert "write" in manifest["send_sms"]
    assert "read" in manifest["read_sms"]
