import argparse
import json
import shutil
import os
import re
import sys
from typing import Optional

# Ensure the workspace root (parent of this server dir) is on sys.path so we can
# import the sibling 'shared' package regardless of invocation path.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.dirname(_THIS_DIR)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

# Import shared crypto tools so server and a future client can share them
try:
    from shared import crypto_tools
except ImportError:  # pragma: no cover - fallback if shared isn't importable
    crypto_tools = None  # Will be checked at runtime when needed


def create_source(args: argparse.Namespace) -> None:
    """Create or remove a source definition.

    - Create: writes server/schemas/<data_name>/schema.json and generates
      server/secrets/<data_name>/private.key.
    - Remove (with --remove): deletes the above files and prunes the two
      per-source directories if empty.
    """
    data_name = args.data_name
    supported_algorithm = args.supported_algorithm
    rekey_interval = args.rekey_interval

    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(base_dir, "schemas", data_name)
    schema_path = os.path.join(target_dir, "schema.json")
    secrets_dir = os.path.join(base_dir, "secrets", data_name)
    key_path = os.path.join(secrets_dir, "private.key")

    # If removal was requested, delete files created by create_source and return
    if getattr(args, "remove", False):
        removed_any = False
        try:
            if os.path.exists(schema_path):
                os.remove(schema_path)
                removed_any = True
            # Remove schemas/<data_name> dir if empty
            if os.path.isdir(target_dir) and not os.listdir(target_dir):
                os.rmdir(target_dir)
            if os.path.exists(key_path):
                os.remove(key_path)
                removed_any = True
            # Remove secrets/<data_name> dir if empty
            if os.path.isdir(secrets_dir) and not os.listdir(secrets_dir):
                os.rmdir(secrets_dir)
        except OSError as e:
            print(f"Error removing source '{data_name}': {e}", file=sys.stderr)
            sys.exit(1)
        if removed_any:
            print(f"Removed source '{data_name}' (schema and key)")
        else:
            print(f"No source files found for '{data_name}' to remove")
        return

    # Prevent overwriting an existing source when creating
    if os.path.exists(schema_path) or os.path.exists(key_path) or os.path.isdir(target_dir) or os.path.isdir(secrets_dir):
        print(
            f"Source '{data_name}' already exists; refusing to overwrite.",
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(target_dir, exist_ok=True)
    schema = {
        "data_name": data_name,
        "supported_algorithm": supported_algorithm,
        "rekey_interval": rekey_interval,
    }

    try:
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)
            f.write("\n")
    except OSError as e:
        print(f"Error writing schema: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Created {schema_path}")

    # Create or place a private key under server/secrets/<data_name>
    os.makedirs(secrets_dir, exist_ok=True)

    try:
        if supported_algorithm == "classic":
            if crypto_tools is None:
                print(
                    "Crypto tools not available; cannot generate ristretto255 key",
                    file=sys.stderr,
                )
                sys.exit(1)
            key_bytes = crypto_tools.generate_ristretto255_private_key()
            with open(key_path, "wb") as f:
                f.write(key_bytes)
        else:  # ot
            placeholder = (
                b"ot-placeholder-key\n"  # Placeholder until OT implementation is added
            )
            with open(key_path, "wb") as f:
                f.write(placeholder)
    except OSError as e:
        print(f"Error writing private key: {e}", file=sys.stderr)
        sys.exit(1)

    # Best-effort restrict permissions on the key file
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass

    print(f"Created {key_path}")


def data_name_type(value: str) -> str:
    """Validate that data_name is strictly alphanumeric (A–Z, a–z, 0–9)."""
    if not re.fullmatch(r"[A-Za-z0-9]+", value):
        raise argparse.ArgumentTypeError(
            "data_name must be alphanumeric only (A–Z, a–z, 0–9)"
        )
    return value


def rekey_interval_type(value: str) -> str:
    """Validate rekey interval as '<positive_integer>d' and normalize it."""
    value = value.strip()
    m = re.fullmatch(r"(\d+)d", value)
    if not m:
        raise argparse.ArgumentTypeError(
            "--rekey-interval must be a positive integer followed by 'd' (e.g., 1d, 7d)"
        )
    days = int(m.group(1))
    if days < 1:
        raise argparse.ArgumentTypeError("--rekey-interval must be at least 1d")
    return f"{days}d"  # normalize (strip leading zeros/spaces)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="server-cli", description="Simple server CLI tool"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create_source command
    p_create = subparsers.add_parser(
        "create_source",
        help="Create a source schema under server/schemas/<data_name>/",
    )
    p_create.add_argument(
        "data_name",
        type=data_name_type,
        help=(
            "Name of IOC type; must be alphanumeric (e.g., filehashes, ipaddresses)"
        ),
    )
    p_create.add_argument(
        "-a",
        "--supported-algorithm",
        type=str.lower,
        choices=["classic", "ot"],
        default="classic",
        help="Supported algorithm: classic (default) or ot",
    )
    p_create.add_argument(
        "-r",
        "--rekey-interval",
        type=rekey_interval_type,
        default="1d",
        help="Days before rekey is required (default: 1d)",
    )
    p_create.add_argument(
        "--remove",
        action="store_true",
        help="Remove the source (schema and private key) instead of creating it",
    )
    p_create.set_defaults(func=create_source)

    # sync command
    p_sync = subparsers.add_parser(
        "sync",
        help=(
            "Compute server-side evaluations for IOCs using RFC 9497 with Ristretto255"
        ),
    )
    p_sync.add_argument(
        "data_name",
        type=data_name_type,
        help="Target data source name (alphanumeric)",
    )
    p_sync.add_argument(
        "data_source_file",
        help="Path to IOC source file (one '<ioc>,{...}' per line)",
    )

    def _sync_entry(args: argparse.Namespace) -> None:
        from server import data_sync

        rc = data_sync.sync_data(args.data_name, args.data_source_file)
        if rc != 0:
            sys.exit(rc)

    p_sync.set_defaults(func=_sync_entry)

    # rekey command
    p_rekey = subparsers.add_parser(
        "rekey",
        help=(
            "Rotate private key and recompute evaluations for all IOCs in the source"
        ),
    )
    p_rekey.add_argument(
        "data_name",
        type=data_name_type,
        help="Target data source name (alphanumeric)",
    )
    p_rekey.add_argument(
        "data_source_file",
        help="Path to IOC source file (one '<ioc>,{...}' per line)",
    )

    def _rekey_entry(args: argparse.Namespace) -> None:
        from server import data_sync

        rc = data_sync.rekey_data(args.data_name, args.data_source_file)
        if rc != 0:
            sys.exit(rc)

    p_rekey.set_defaults(func=_rekey_entry)

    # purge_data command
    p_purge = subparsers.add_parser(
        "purge_data",
        help="Remove all server files for a dataset under server/data/<data_name>",
    )
    p_purge.add_argument(
        "data_name",
        type=data_name_type,
        help="Target data source name (alphanumeric)",
    )

    def _purge_entry(args: argparse.Namespace) -> None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        out_dir = os.path.join(base_dir, "data", args.data_name)
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir, ignore_errors=True)
        print(f"Purged server dataset directory: {out_dir}")

    p_purge.set_defaults(func=_purge_entry)

    # start_server command
    p_srv = subparsers.add_parser(
        "start_server",
        help="Start a simple HTTP API server with /sync_data endpoint",
    )
    p_srv.add_argument(
        "bind",
        help="Server bind in 'host:port' format (e.g., 127.0.0.1:8000)",
    )

    def _start_server_entry(args: argparse.Namespace) -> None:
        from server.api_server import run_server

        run_server(args.bind)

    p_srv.set_defaults(func=_start_server_entry)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        args.func(args)
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
