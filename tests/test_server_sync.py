from pathlib import Path
import csv

import pytest

from .utils import run_module


def write_source(path: Path, lines: list[tuple[str, str]]):
    with open(path, "w", encoding="utf-8") as f:
        for ioc, meta in lines:
            f.write(f"{ioc},{meta}\n")


@pytest.mark.skipif(True, reason="Requires libsodium; enabled in test_server_rekey when available")
def test_placeholder():
    pass


def test_sync_add_remove_cycle(workspace: Path, pyexe: str, libsodium_available: bool):
    if not libsodium_available:
        pytest.skip("libsodium not available")
    ds = "SyncA"
    # Prepare source and create classic
    r = run_module(pyexe, "server.cli", ["create_source", ds], workspace)
    assert r.returncode == 0, r.stderr
    src = workspace / "data_src.txt"
    write_source(src, [("ioc1","{\"a\":1}"), ("ioc2","{\"b\":2}")])

    # Initial sync
    r1 = run_module(pyexe, "server.cli", ["sync", ds, str(src)], workspace)
    assert r1.returncode == 0, r1.stderr
    out_dir = workspace / "server" / "data" / ds
    idx = out_dir / "index.csv"
    log = out_dir / "changes.log"
    assert idx.exists() and log.exists()
    rows = list(csv.reader(open(idx, newline="", encoding="utf-8")))
    assert {r[0] for r in rows} == {"ioc1","ioc2"}
    log_lines = [ln.strip() for ln in open(log, encoding="utf-8")] 
    assert all(ln.startswith("ADDED ") for ln in log_lines[-2:])

    # Modify: remove ioc2, add ioc3
    write_source(src, [("ioc1","{\"a\":1}"), ("ioc3","{\"c\":3}")])
    r2 = run_module(pyexe, "server.cli", ["sync", ds, str(src)], workspace)
    assert r2.returncode == 0, r2.stderr
    rows2 = list(csv.reader(open(idx, newline="", encoding="utf-8")))
    assert {r[0] for r in rows2} == {"ioc1","ioc3"}
    log_lines2 = [ln.strip() for ln in open(log, encoding="utf-8")] 
    # Expect at least one REMOVED and one ADDED in the new tail
    tail = log_lines2[len(log_lines):]
    assert any(ln.startswith("REMOVED ") for ln in tail)
    assert any(ln.startswith("ADDED ") for ln in tail)
