import json
import os
import subprocess
from pathlib import Path

import pytest

from .utils import run_module, wait_for_port, pick_free_port


def write_source(path: Path, lines: list[tuple[str, str]]):
    with open(path, "w", encoding="utf-8") as f:
        for ioc, meta in lines:
            f.write(f"{ioc},{meta}\n")


def _label(host: str, port: int) -> str:
    return f"{host}_{port}"


def test_end_to_end_client_server_sync_and_query(workspace: Path, pyexe: str, libsodium_available: bool):
    if not libsodium_available:
        pytest.skip("libsodium not available")

    ds = "E2E1"
    # Create dataset and initial source
    r = run_module(pyexe, "server.cli", ["create_source", ds, "-a", "classic"], workspace)
    assert r.returncode == 0, r.stderr
    src = workspace / "e2e_src.txt"
    meta1 = json.dumps({"desc": "alpha"})
    meta2 = json.dumps({"desc": "beta"})
    write_source(src, [("ioc_alpha", meta1), ("ioc_beta", meta2)])
    r1 = run_module(pyexe, "server.cli", ["sync", ds, str(src)], workspace)
    assert r1.returncode == 0, r1.stderr

    # Start server
    port = pick_free_port()
    host = "127.0.0.1"
    bind = f"{host}:{port}"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workspace)
    proc = subprocess.Popen([pyexe, "-m", "server.cli", "start_server", bind], cwd=workspace, env=env)
    try:
        wait_for_port(host, port, timeout=5)

        # Client full sync
        r2 = run_module(pyexe, "client.cli", ["sync_data", bind, ds], workspace)
        assert r2.returncode == 0, r2.stderr
        label = _label(host, port)
        client_dir = workspace / "client" / "data" / label / ds
        assert (client_dir / "changes.log").exists()

        # Update server source: remove ioc_beta, add ioc_gamma
        meta3 = json.dumps({"desc": "gamma"})
        write_source(src, [("ioc_alpha", meta1), ("ioc_gamma", meta3)])
        r3 = run_module(pyexe, "server.cli", ["sync", ds, str(src)], workspace)
        assert r3.returncode == 0, r3.stderr

        # Client delta sync
        r4 = run_module(pyexe, "client.cli", ["sync_data", bind, ds], workspace)
        assert r4.returncode == 0, r4.stderr

        # Client query for ioc_alpha should succeed and print metadata
        r5 = run_module(pyexe, "client.cli", ["query", bind, ds, "ioc_alpha"], workspace)
        assert r5.returncode == 0, r5.stderr
        assert "Match found." in r5.stdout
        assert "Metadata:" in r5.stdout and "alpha" in r5.stdout

        # Client query for removed ioc_beta should return no match
        r6 = run_module(pyexe, "client.cli", ["query", bind, ds, "ioc_beta"], workspace)
        assert r6.returncode == 0
        assert "No active match" in r6.stdout
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()

