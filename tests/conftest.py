import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest


def _copy_workspace(src_root: Path, dst_root: Path) -> None:
    for name in ("server", "client", "shared"):
        shutil.copytree(src_root / name, dst_root / name)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    src_root = Path(__file__).resolve().parents[1]
    dst = tmp_path / "ws"
    _copy_workspace(src_root, dst)
    return dst


@pytest.fixture()
def pyexe(workspace: Path) -> str:
    candidates = [
        workspace.parents[1] / ".venv312" / "bin" / "python",
        workspace.parents[1] / ".venv312" / "bin" / "python3",
        Path(sys.executable),
    ]
    for p in candidates:
        if p and Path(p).exists():
            return str(p)
    return sys.executable


def run_module(py: str, mod: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd)
    cmd = [py, "-m", mod, *args]
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


@pytest.fixture()
def libsodium_available(workspace: Path, pyexe: str) -> bool:
    code = "from shared.crypto_tools import _load_libsodium; _load_libsodium(); print('OK')"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workspace)
    cp = subprocess.run([pyexe, "-c", code], cwd=workspace, capture_output=True, text=True, env=env)
    return cp.returncode == 0 and "OK" in cp.stdout


def wait_for_port(host: str, port: int, timeout: float = 5.0) -> None:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.25)
            try:
                s.connect((host, port))
                return
            except OSError:
                time.sleep(0.05)
    raise RuntimeError(f"Server {host}:{port} not reachable within {timeout}s")


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

