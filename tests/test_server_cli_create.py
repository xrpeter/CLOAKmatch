import os
from pathlib import Path

import pytest

from .utils import run_module


def test_create_and_remove_source_classic(workspace: Path, pyexe: str):
    ds = "Alpha1"
    r = run_module(pyexe, "server.cli", ["create_source", ds, "-a", "classic", "-r", "7d"], workspace)
    assert r.returncode == 0, r.stderr
    schema = workspace / "server" / "schemas" / ds / "schema.json"
    key = workspace / "server" / "secrets" / ds / "private.key"
    assert schema.exists()
    assert key.exists()

    # Duplicate create should fail
    r2 = run_module(pyexe, "server.cli", ["create_source", ds], workspace)
    assert r2.returncode != 0
    assert "already exists" in (r2.stderr + r2.stdout)

    # Remove
    r3 = run_module(pyexe, "server.cli", ["create_source", ds, "--remove"], workspace)
    assert r3.returncode == 0, r3.stderr
    assert not schema.exists()
    assert not key.exists()
    assert not schema.parent.exists()
    assert not key.parent.exists()


@pytest.mark.parametrize("bad", ["with-dash", "space x", "sym$"], ids=["dash","space","symbol"])
def test_create_source_rejects_bad_data_name(workspace: Path, pyexe: str, bad: str):
    r = run_module(pyexe, "server.cli", ["create_source", bad], workspace)
    assert r.returncode != 0
    assert "alphanumeric" in (r.stderr + r.stdout)


@pytest.mark.parametrize("ival,ok", [("1d", True), ("01d", True), ("0d", False), ("7x", False)])
def test_rekey_interval_validation(workspace: Path, pyexe: str, ival: str, ok: bool):
    ds = "Beta2"
    args = ["create_source", ds, "-r", ival]
    r = run_module(pyexe, "server.cli", args, workspace)
    if ok:
        assert r.returncode == 0
    else:
        assert r.returncode != 0


def test_create_source_ot_placeholder(workspace: Path, pyexe: str):
    ds = "Gamma3"
    r = run_module(pyexe, "server.cli", ["create_source", ds, "-a", "ot"], workspace)
    assert r.returncode == 0, r.stderr
    key = workspace / "server" / "secrets" / ds / "private.key"
    assert key.exists()
    assert key.read_bytes().startswith(b"ot-placeholder-key")
