import os
import sys
import shutil
import tempfile

import pytest


# Ensure repo root is importable when users run `pytest -q` without
# setting PYTHONPATH or installing the package.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.fixture()
def temp_outdir():
    d = tempfile.mkdtemp(prefix="audit_run_")
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture()
def block_network(monkeypatch):
    """Best-effort network kill-switch for tests.

    We cannot toggle the host network from pytest in a portable way, so we
    monkeypatch common Python networking entry points to fail loudly.
    """
    import socket

    def _blocked(*args, **kwargs):
        raise RuntimeError("Network access is forbidden during execution audit tests")

    # Common DNS/connection paths
    monkeypatch.setattr(socket, "create_connection", _blocked, raising=True)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked, raising=True)

    # Block direct socket connects
    _orig_socket = socket.socket

    class _NoNetSocket(_orig_socket):  # type: ignore[misc]
        def connect(self, *a, **k):  # type: ignore[override]
            raise RuntimeError("Network access is forbidden during execution audit tests")

    monkeypatch.setattr(socket, "socket", _NoNetSocket, raising=True)

    # urllib
    try:
        import urllib.request
        monkeypatch.setattr(urllib.request, "urlopen", _blocked, raising=True)
    except Exception:
        pass

    # requests
    try:
        from requests.sessions import Session  # type: ignore
        monkeypatch.setattr(Session, "request", _blocked, raising=True)
    except Exception:
        pass

    yield
