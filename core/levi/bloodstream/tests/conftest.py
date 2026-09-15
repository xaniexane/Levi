"""Hermetic fixtures for bloodstream tests.

Everything runs under a tmp data_dir; nothing touches the real ~/.levi.
The provider chain is pinned to the deterministic local provider so no
model download or network is ever attempted.
"""

import pytest

from levi.bloodstream.stages import TurnContext
from levi.bloodstream.turn import reset_session_state


@pytest.fixture(autouse=True)
def _pin_provider(monkeypatch):
    monkeypatch.setenv("LEVI_PROVIDER", "local")
    monkeypatch.delenv("LEVI_MODEL_DIR", raising=False)


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "levi-home"
    d.mkdir()
    return d


@pytest.fixture
def ctx(data_dir):
    reset_session_state()
    return TurnContext(session_id="test", data_dir=data_dir, max_model_steps=1)


@pytest.fixture
def ctx_for(data_dir):
    reset_session_state()

    def make(**kwargs):
        kwargs.setdefault("session_id", "test")
        kwargs.setdefault("data_dir", data_dir)
        kwargs.setdefault("max_model_steps", 1)
        return TurnContext(**kwargs)

    return make
