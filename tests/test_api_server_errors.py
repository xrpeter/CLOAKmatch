import json
import os
import subprocess
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from .utils import run_module, wait_for_port, pick_free_port


def _get(url: str, accept: str = "application/json"):
    req = Request(url, headers={"Accept": accept})
    try:
        with urlopen(req) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except HTTPError as e:
        return e.code, dict(e.headers or {}), e.read() if hasattr(e, 'read') else b""


def _post_json(url: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    try:
        with urlopen(req) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except HTTPError as e:
        return e.code, dict(e.headers or {}), e.read() if hasattr(e, 'read') else b""


def test_api_errors_without_dataset(workspace, pyexe):
    port = pick_free_port()
    bind = f"127.0.0.1:{port}"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workspace)
    proc = subprocess.Popen([pyexe, "-m", "server.cli", "start_server", bind], cwd=workspace, env=env)
    try:
        wait_for_port("127.0.0.1", port)
        # Unknown data_type for encryption_type
        st, _, body = _get(f"http://127.0.0.1:{port}/encryption_type?data_type=Nope")
        assert st == 404
        # Unknown data_type for sync
        st, _, body = _get(f"http://127.0.0.1:{port}/sync_data?data_type=Nope", accept="text/plain")
        assert st == 404
        # Bad blinded payload
        st, _, body = _post_json(f"http://127.0.0.1:{port}/oprf_evaluate", {"data_type": "Nope", "blinded": "zz"})
        assert st == 400 or st == 404
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
