#!/usr/bin/env python3
"""
One-liner client sync + query for CLOAKmatch.

Syncs from the server and performs a single query for the provided IOC.

Usage:
  python client_simple.py <ioc> [--server 127.0.0.1:8000] [--name testSource]

This is a convenience wrapper around `python -m client.cli` commands.
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        sys.exit(proc.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description="CLOAKmatch simple client query")
    ap.add_argument("ioc", help="IOC to test (e.g., evil.com)")
    ap.add_argument("--server", default="127.0.0.1:8000", help="Server host:port (default: 127.0.0.1:8000)")
    ap.add_argument("--name", default="testSource", help="Dataset name (alphanumeric)")
    args = ap.parse_args()

    # 1) Ensure local state is synced
    run([sys.executable, "-m", "client.cli", "sync_data", args.server, args.name])
    # 2) Query the provided IOC
    run([sys.executable, "-m", "client.cli", "query", args.server, args.name, args.ioc])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

