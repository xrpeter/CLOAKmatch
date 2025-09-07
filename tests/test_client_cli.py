from pathlib import Path

from .utils import run_module


def test_client_purge_and_reset_scaffold(workspace: Path, pyexe: str):
    label = "127.0.0.1_9999"
    data_name = "DS1"
    base = workspace / "client" / "data" / label
    ds_dir = base / data_name
    # Seed some files
    (ds_dir / "sub").mkdir(parents=True, exist_ok=True)
    (ds_dir / "sub" / "x.txt").write_text("1", encoding="utf-8")
    # purge_data removes dataset and prunes label if empty
    r = run_module(pyexe, "client.cli", ["purge_data", f"127.0.0.1:9999", data_name], workspace)
    assert r.returncode == 0
    assert not ds_dir.exists()
    assert not base.exists()

    # reset_data: creates clean dir and attempts sync (will fail to connect), but should create dir beforehand
    r2 = run_module(pyexe, "client.cli", ["reset_data", f"127.0.0.1:9999", data_name], workspace)
    # Connection will fail; accept non-zero but ensure directory created
    out_dir = workspace / "client" / "data" / label / data_name
    assert out_dir.exists()
