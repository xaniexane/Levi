"""ServiceMesh.find boundary tests (hermetic, stdlib-only)."""

from __future__ import annotations

import pytest

from levi.runtime.service_mesh import ServiceMesh


def test_find_rejects_non_string():
    mesh = ServiceMesh()
    for bad in (None, 123, ["x"]):
        with pytest.raises(ValueError, match="'q' must be a string"):
            mesh.find(bad)  # type: ignore[arg-type]


def test_find_still_searches():
    mesh = ServiceMesh()
    results = mesh.find("agent")
    assert isinstance(results, list)
    assert mesh.find("zzz-no-such-service") == []
