from pathlib import Path

from .utils import run_module


def test_sync_without_schema_fails(workspace: Path, pyexe: str):
    ds = "ErrNoSchema"
    src = workspace / "src.txt"
    src.write_text("ioc,{\"x\":1}\n", encoding="utf-8")
    r = run_module(pyexe, "server.cli", ["sync", ds, str(src)], workspace)
    assert r.returncode != 0
    assert "Schema not found" in (r.stderr + r.stdout)


def test_sync_missing_key_fails(workspace: Path, pyexe: str):
    ds = "ErrNoKey"
    # Create schema/key then remove key
    r = run_module(pyexe, "server.cli", ["create_source", ds], workspace)
    assert r.returncode == 0
    key_path = workspace / "server" / "secrets" / ds / "private.key"
    key_path.unlink()
    src = workspace / "src2.txt"
    src.write_text("ioc,{\"x\":1}\n", encoding="utf-8")
    r2 = run_module(pyexe, "server.cli", ["sync", ds, str(src)], workspace)
    assert r2.returncode != 0
    assert "Private key not found" in (r2.stderr + r2.stdout)

