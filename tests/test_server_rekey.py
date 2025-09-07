from pathlib import Path
import csv

import pytest

from .utils import run_module


def write_source(path: Path, lines: list[tuple[str, str]]):
    with open(path, "w", encoding="utf-8") as f:
        for ioc, meta in lines:
            f.write(f"{ioc},{meta}\n")


def test_rekey_resets_changes_and_updates_index(workspace: Path, pyexe: str, libsodium_available: bool):
    if not libsodium_available:
        pytest.skip("libsodium not available")
    ds = "RK1"
    r = run_module(pyexe, "server.cli", ["create_source", ds], workspace)
    assert r.returncode == 0, r.stderr
    src = workspace / "src.txt"
    write_source(src, [("ioc1","{\"x\":1}"), ("ioc2","{\"y\":2}")])
    # Initial sync
    r1 = run_module(pyexe, "server.cli", ["sync", ds, str(src)], workspace)
    assert r1.returncode == 0, r1.stderr
    out_dir = workspace / "server" / "data" / ds
    idx = out_dir / "index.csv"
    key_path = workspace / "server" / "secrets" / ds / "private.key"
    key_before = key_path.read_bytes()
    rows_before = list(csv.reader(open(idx, newline="", encoding="utf-8")))
    prfs_before = {r[0]: r[1] for r in rows_before}

    # Rekey
    r2 = run_module(pyexe, "server.cli", ["rekey", ds, str(src)], workspace)
    assert r2.returncode == 0, r2.stderr
    key_after = key_path.read_bytes()
    assert key_before != key_after
    rows_after = list(csv.reader(open(idx, newline="", encoding="utf-8")))
    prfs_after = {r[0]: r[1] for r in rows_after}
    # PRFs should change on rekey
    assert any(prfs_before[k] != prfs_after[k] for k in prfs_before.keys())
    # changes.log should contain only ADDED entries (2 lines)
    log = out_dir / "changes.log"
    lines = [ln.strip() for ln in open(log, encoding="utf-8")] 
    assert len(lines) >= 2
    assert all(ln.startswith("ADDED ") for ln in lines)
