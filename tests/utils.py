import os
import socket
import subprocess
from pathlib import Path


def run_module(py: str, mod: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd)
    cmd = [py, "-m", mod, *args]
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


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

