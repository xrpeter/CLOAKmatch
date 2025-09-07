from pathlib import Path

from .utils import run_module


def test_purge_data_idempotent(workspace: Path, pyexe: str):
    ds = "PurgeA"
    out_dir = workspace / "server" / "data" / ds
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dummy.txt").write_text("x", encoding="utf-8")
    # Purge removes
    r = run_module(pyexe, "server.cli", ["purge_data", ds], workspace)
    assert r.returncode == 0
    assert not out_dir.exists()
    # Purge again should still succeed
    r2 = run_module(pyexe, "server.cli", ["purge_data", ds], workspace)
    assert r2.returncode == 0
