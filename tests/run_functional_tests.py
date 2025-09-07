import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PASS = "✅"
FAIL = "❌"


def copy_workspace(src_root: Path, dst_root: Path) -> None:
    for name in ("server", "client", "shared"):
        shutil.copytree(src_root / name, dst_root / name)


def _detect_python(src_root: Path) -> str:
    candidates = [
        src_root / ".venv312" / "bin" / "python",
        src_root / ".venv312" / "bin" / "python3",
        Path(sys.executable),
    ]
    for p in candidates:
        if p and Path(p).exists():
            return str(p)
    return "python3"


def run_module(mod: str, args: list[str], cwd: Path, py: str) -> subprocess.CompletedProcess:
    cmd = [py, "-m", mod, *args]
    env = os.environ.copy()
    # Ensure the copied workspace root is importable first
    env["PYTHONPATH"] = str(cwd)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


def assert_exists(path: Path) -> tuple[bool, str]:
    if path.exists():
        return True, f"{PASS} exists: {path}"
    return False, f"{FAIL} missing: {path}"


def assert_not_exists(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return True, f"{PASS} removed: {path}"
    return False, f"{FAIL} still present: {path}"


def main() -> int:
    src_root = Path(__file__).resolve().parents[1]
    failures = 0
    with tempfile.TemporaryDirectory(prefix="psi_tests_") as td:
        work = Path(td)
        copy_workspace(src_root, work)
        py = _detect_python(src_root)

        # 1) server create_source (create)
        ds = "testSource"
        r = run_module("server.cli", ["create_source", ds, "-a", "classic", "-r", "1d"], work, py)
        if r.returncode != 0:
            print(f"{FAIL} server create_source failed: rc={r.returncode}\n{r.stderr}")
            failures += 1
        sch = work / "server" / "schemas" / ds / "schema.json"
        sec = work / "server" / "secrets" / ds / "private.key"
        ok, msg = assert_exists(sch); print(msg); failures += 0 if ok else 1
        ok, msg = assert_exists(sec); print(msg); failures += 0 if ok else 1

        # 2) server create_source --remove (removes schema + key, prunes dirs if empty)
        r = run_module("server.cli", ["create_source", ds, "--remove"], work, py)
        if r.returncode != 0:
            print(f"{FAIL} server create_source --remove failed: rc={r.returncode}\n{r.stderr}")
            failures += 1
        ok, msg = assert_not_exists(sch); print(msg); failures += 0 if ok else 1
        ok, msg = assert_not_exists(sec); print(msg); failures += 0 if ok else 1
        # also the per-source directories should be pruned if now empty
        ok, msg = assert_not_exists(sch.parent); print(msg); failures += 0 if ok else 1
        ok, msg = assert_not_exists(sec.parent); print(msg); failures += 0 if ok else 1

        # 3) server purge_data removes server/data/<data_name>
        data_dir = work / "server" / "data" / ds
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "dummy.txt").write_text("x")
        r = run_module("server.cli", ["purge_data", ds], work, py)
        if r.returncode != 0:
            print(f"{FAIL} server purge_data failed: rc={r.returncode}\n{r.stderr}")
            failures += 1
        ok, msg = assert_not_exists(data_dir); print(msg); failures += 0 if ok else 1

        # 4) client purge_data behavior under client/data/<label>/<data_name>
        label = "127.0.0.1_8000"
        c_base = work / "client" / "data" / label
        ds_dir = c_base / ds
        other_dir = c_base / "other"
        other_dir.mkdir(parents=True, exist_ok=True)
        ds_dir.mkdir(parents=True, exist_ok=True)
        (ds_dir / "a.txt").write_text("1")
        (ds_dir / "sub").mkdir(exist_ok=True)
        (ds_dir / "sub" / "b.txt").write_text("2")
        r = run_module("client.cli", ["purge_data", "127.0.0.1:8000", ds], work, py)
        if r.returncode != 0:
            print(f"{FAIL} client purge_data failed: rc={r.returncode}\n{r.stderr}")
            failures += 1
        ok, msg = assert_not_exists(ds_dir); print(msg); failures += 0 if ok else 1
        # label directory should still exist because 'other' remains
        ok, msg = assert_exists(c_base); print(msg); failures += 0 if ok else 1

        # 5) client purge_data removes label dir when last dataset removed
        shutil.rmtree(other_dir, ignore_errors=True)
        # Recreate dataset to then purge again
        ds_dir.mkdir(parents=True, exist_ok=True)
        r = run_module("client.cli", ["purge_data", "127.0.0.1:8000", ds], work, py)
        if r.returncode != 0:
            print(f"{FAIL} client purge_data (second) failed: rc={r.returncode}\n{r.stderr}")
            failures += 1
        ok, msg = assert_not_exists(ds_dir); print(msg); failures += 0 if ok else 1
        ok, msg = assert_not_exists(c_base); print(msg); failures += 0 if ok else 1

    if failures == 0:
        print(f"\nAll functional checks passed {PASS}")
        return 0
    else:
        print(f"\nFunctional checks failed: {failures} {FAIL}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
