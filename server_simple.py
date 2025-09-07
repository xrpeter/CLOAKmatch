#!/usr/bin/env python3
"""
One-liner server bootstrap for CLOAKmatch.

Creates (or resets) a demo dataset, prepares a tiny sample source,
computes server-side state, and starts the HTTP API.

Usage:
  python server_simple.py [--host 127.0.0.1] [--port 8000] [--name testSource] [--source path/to/source.txt]

This is a convenience wrapper around `python -m server.cli` commands.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        sys.exit(proc.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description="CLOAKmatch simple server bootstrapper")
    ap.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    ap.add_argument("--name", default="testSource", help="Dataset name (alphanumeric)")
    ap.add_argument(
        "--source",
        default=None,
        help=(
            "Path to a source file with one line per IOC in the format "
            "<ioc>,{json_metadata}. If omitted, a sample file is created."
        ),
    )
    args = ap.parse_args()

    bind = f"{args.host}:{args.port}"

    # 1) Reset any existing dataset quietly (ignore errors), then create fresh
    subprocess.run([sys.executable, "-m", "server.cli", "create_source", args.name, "--remove"])  # ignore rc
    run([sys.executable, "-m", "server.cli", "create_source", args.name, "-a", "classic", "-r", "1d"])

    # 2) Prepare or use source file
    if args.source:
        sample_path = Path(args.source).expanduser().resolve()
        if not sample_path.exists():
            print(f"Provided --source not found: {sample_path}", file=sys.stderr)
            return 1
        print(f"Using provided source: {sample_path}")
    else:
        sample_path = Path("sample_data.txt").resolve()
        sample_path.write_text('evil.com,{"desc":"known bad domain"}\n', encoding="utf-8")
        print(f"Wrote sample source: {sample_path}")

    # 3) Compute server-side evaluations and changes.log
    run([sys.executable, "-m", "server.cli", "sync", args.name, str(sample_path)])

    # 4) Start HTTP server (blocks)
    print(f"Starting server on http://{bind} (Ctrl+C to stop)…")
    run([sys.executable, "-m", "server.cli", "start_server", bind])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
