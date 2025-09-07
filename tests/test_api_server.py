import json
import time
from pathlib import Path
from urllib.request import urlopen, Request
import subprocess
import os

import pytest

from .utils import run_module, wait_for_port, pick_free_port


def write_source(path: Path, lines: list[tuple[str, str]]):
    with open(path, "w", encoding="utf-8") as f:
        for ioc, meta in lines:
            f.write(f"{ioc},{meta}\n")


def _get(url: str) -> tuple[int, dict, bytes]:
    req = Request(url, headers={"Accept": "application/json, text/plain"})
    with urlopen(req) as resp:
        data = resp.read()
        return resp.status, dict(resp.headers), data


def test_api_endpoints_full_and_delta(workspace: Path, pyexe: str, libsodium_available: bool):
    if not libsodium_available:
        pytest.skip("libsodium not available")
    ds = "HTTP1"
    # Prepare dataset
    r = run_module(pyexe, "server.cli", ["create_source", ds], workspace)
    assert r.returncode == 0, r.stderr
    src = workspace / "http_src.txt"
    write_source(src, [("ioc1","{\"a\":1}")])
    r2 = run_module(pyexe, "server.cli", ["sync", ds, str(src)], workspace)
    assert r2.returncode == 0, r2.stderr

    # Start server
    port = pick_free_port()
    bind = f"127.0.0.1:{port}"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workspace)
    proc = subprocess.Popen([pyexe, "-m", "server.cli", "start_server", bind], cwd=workspace, env=env)
    try:
        wait_for_port("127.0.0.1", port, timeout=5)
        # encryption_type
        st, _, body = _get(f"http://127.0.0.1:{port}/encryption_type?data_type={ds}")
        assert st == 200
        info = json.loads(body.decode())
        assert info["encryption"] == "xchacha20poly1305-ietf"
        assert info["suite"] == "oprf-ristretto255-sha512"

        # sync_data full
        st, hdrs, text = _get(f"http://127.0.0.1:{port}/sync_data?data_type={ds}")
        assert st == 200
        assert hdrs.get("X-Delta", "full").lower() == "full"
        lines = text.decode().splitlines()
        assert lines and lines[0].startswith("ADDED ")
        last_hash = lines[-1].split()[-1]

        # sync_data delta from last hash
        st, hdrs, text2 = _get(f"http://127.0.0.1:{port}/sync_data?data_type={ds}&hash={last_hash}")
        assert st == 200
        assert hdrs.get("X-Delta", "").lower() == "delta"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
