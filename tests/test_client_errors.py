from pathlib import Path

from .utils import run_module


def test_client_sync_invalid_data_name(workspace: Path, pyexe: str):
    r = run_module(pyexe, "client.cli", ["sync_data", "127.0.0.1:8000", "bad-name"], workspace)
    assert r.returncode != 0
    assert "alphanumeric" in (r.stderr + r.stdout)


def test_client_sync_bad_server_format(workspace: Path, pyexe: str):
    r = run_module(pyexe, "client.cli", ["sync_data", "hostonly", "Data1"], workspace)
    assert r.returncode != 0
    assert "host:port" in (r.stderr + r.stdout)


def test_client_sync_server_down(workspace: Path, pyexe: str):
    # Choose an unlikely listening port
    r = run_module(pyexe, "client.cli", ["sync_data", "127.0.0.1:6553", "Data1"], workspace)
    assert r.returncode != 0
    assert "Request failed" in (r.stderr + r.stdout)

