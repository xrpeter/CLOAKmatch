import argparse
import os
import re
import sys
import time
from urllib.parse import urlencode
from urllib.request import urlopen, Request
import json
import shutil

# Ensure workspace root is importable before importing our local 'shared' package
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.dirname(_THIS_DIR)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

from shared import crypto_tools


ALNUM_RE = re.compile(r"^[A-Za-z0-9]+$")


def _normalize_server(server: str) -> tuple[str, int, str]:
    if ":" not in server:
        raise ValueError("--server must be in 'host:port' format")
    host, port_s = server.rsplit(":", 1)
    try:
        port = int(port_s)
    except ValueError:
        raise ValueError("Port must be an integer")
    label = f"{host.replace(':','_').replace('/', '_')}_{port}"
    return host, port, label


def _latest_hash_from_file(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    last = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                last = line
    except OSError:
        return None
    if not last:
        return None
    parts = last.split()
    if len(parts) >= 3:
        # Format: EVENT OPRF_HEX ENC_META HASH
        return parts[-1]
    # Fallback (older comma format)
    if "," in last:
        return last.rsplit(",", 1)[-1].strip()
    return None


def _http_get_json(url: str) -> dict:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req) as resp:
        data = resp.read()
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}: {data.decode('utf-8', 'ignore')}")
        return json.loads(data.decode("utf-8"))


def _http_post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    with urlopen(req) as resp:
        data = resp.read()
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}: {data.decode('utf-8', 'ignore')}")
        return json.loads(data.decode("utf-8"))


def _load_local_changes_log(base_dir: str, label: str, data_name: str) -> list[str]:
    path = os.path.join(base_dir, "data", label, data_name, "changes.log")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Local changes.log not found at {path}. Run 'sync_data' first.")
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def _load_active_index(base_dir: str, label: str, data_name: str) -> dict[str, str]:
    out_dir = os.path.join(base_dir, "data", label, data_name)
    path = os.path.join(out_dir, "active_index.csv")
    mapping: dict[str, str] = {}
    if not os.path.exists(path):
        return mapping
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw or "," not in raw:
                    continue
                prf_h, enc_meta = raw.split(",", 1)
                mapping[prf_h.lower()] = enc_meta
    except OSError:
        return {}
    return mapping


def cmd_query(args: argparse.Namespace) -> int:
    data_name = args.data_name
    if not ALNUM_RE.fullmatch(data_name):
        print("data_name must be alphanumeric", file=sys.stderr)
        return 2
    try:
        host, port, label = _normalize_server(args.server)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Always sync latest changes from server before querying
    sync_args = argparse.Namespace(server=args.server, data_name=args.data_name, hash=None)
    rc = cmd_sync_data(sync_args)
    if rc != 0:
        return rc
    # 1) Discover encryption type
    try:
        info = _http_get_json(f"http://{host}:{port}/encryption_type?data_type={data_name}")
    except Exception as e:
        print(f"Failed to query encryption_type: {e}", file=sys.stderr)
        return 1
    if info.get("encryption") != "xchacha20poly1305-ietf" or info.get("suite") != "oprf-ristretto255-sha512":
        print("Unsupported suite/encryption returned by server", file=sys.stderr)
        return 1

    # 2) Hash to group
    ioc_bytes = args.ioc.encode("utf-8")
    P = crypto_tools.ristretto_hash_to_group(data_name, ioc_bytes)

    # 3) Blind with ephemeral scalar
    r = crypto_tools.ristretto_scalar_random()
    B = crypto_tools.ristretto_scalarmult(r, P)

    # 4) Transmit to server for evaluation
    try:
        res = _http_post_json(f"http://{host}:{port}/oprf_evaluate", {"data_type": data_name, "blinded": B.hex()})
    except Exception as e:
        print(f"OPRF evaluate request failed: {e}", file=sys.stderr)
        return 1
    E_hex = res.get("evaluated")
    if not isinstance(E_hex, str):
        print("Invalid server response (missing 'evaluated')", file=sys.stderr)
        return 1
    E = bytes.fromhex(E_hex)

    # 5) Unblind
    r_inv = crypto_tools.ristretto_scalar_invert(r)
    Q = crypto_tools.ristretto_scalarmult(r_inv, E)

    # 6) Finalize
    PRF = crypto_tools.oprf_finalize(data_name, ioc_bytes, Q)
    prf_hex = PRF.hex()

    # 7) Check for matches using the maintained active index
    active = _load_active_index(base_dir, label, data_name)
    if not active:
        # Fallback to replaying local changes.log if index missing
        try:
            lines = _load_local_changes_log(base_dir, label, data_name)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 1
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            event, prf_h, enc_meta = parts[0].upper(), parts[1], parts[2]
            if event == "ADDED":
                active[prf_h.lower()] = enc_meta
            elif event == "REMOVED":
                active.pop(prf_h.lower(), None)

    enc_meta_hex = active.get(prf_hex.lower())
    if not enc_meta_hex:
        print("No active match found in changes.log (either not present or removed)")
        return 0

    # 8) Decrypt metadata
    try:
        nonce_hex, ct_hex = enc_meta_hex.split(":", 1)
        nonce = bytes.fromhex(nonce_hex)
        ct = bytes.fromhex(ct_hex)
        meta = crypto_tools.decrypt_metadata_from_prf_and_q(data_name, ioc_bytes, PRF, Q, nonce, ct)
    except Exception as e:
        print(f"Failed to decrypt metadata: {e}", file=sys.stderr)
        return 1

    print("Match found.")
    print(f"PRF: {prf_hex}")
    print(f"Metadata: {meta.decode('utf-8', 'replace')}")
    # Optionally persist
    out_dir = os.path.join(base_dir, "data", label, data_name)
    try:
        with open(os.path.join(out_dir, "matches.txt"), "a", encoding="utf-8") as f:
            f.write(f"{args.ioc},{prf_hex},{meta.decode('utf-8', 'replace')}\n")
    except OSError:
        pass
    return 0
def cmd_sync_data(args: argparse.Namespace) -> int:
    data_name = args.data_name
    if not ALNUM_RE.fullmatch(data_name):
        print("data_name must be alphanumeric (A–Z, a–z, 0–9)", file=sys.stderr)
        return 2
    try:
        host, port, label = _normalize_server(args.server)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(base_dir, "data", label, data_name)
    os.makedirs(out_dir, exist_ok=True)

    local_log = os.path.join(out_dir, "changes.log")
    # Determine hash to use (CLI overrides local discovery). Allow callers to
    # skip local hash discovery to force a full fetch.
    if getattr(args, "skip_local_hash", False):
        last_hash = args.hash  # may be None
    else:
        last_hash = args.hash or _latest_hash_from_file(local_log)

    qs = {"data_type": data_name}
    if last_hash:
        qs["hash"] = last_hash
    url = f"http://{host}:{port}/sync_data?{urlencode(qs)}"

    try:
        req = Request(url, headers={"Accept": "text/plain"})
        with urlopen(req) as resp:  # nosec - user supplies host; this is a CLI client
            if resp.status != 200:
                print(f"Server returned HTTP {resp.status}", file=sys.stderr)
                return 1
            body = resp.read()
            delta_mode = (resp.headers.get("X-Delta", "").lower() == "delta")
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 1

    if not body:
        print("No new changes received (empty response).")
        return 0

    # If we received a full response (e.g., after rekey), purge old delta-* logs
    if not delta_mode:
        try:
            for name in os.listdir(out_dir):
                if name.startswith("delta-") and name.endswith(".log"):
                    try:
                        os.remove(os.path.join(out_dir, name))
                    except OSError:
                        pass
        except OSError:
            pass

    # Save raw payload for audit
    ts = time.strftime("%Y%m%d-%H%M%S")
    raw_prefix = "delta" if (last_hash or delta_mode) else "full"
    raw_path = os.path.join(out_dir, f"{raw_prefix}-{ts}.log")
    try:
        with open(raw_path, "wb") as f:
            f.write(body)
    except OSError as e:
        print(f"Failed to write raw delta file: {e}", file=sys.stderr)
        return 1

    # Write to local changes.log (append for delta, reset for full)
    try:
        text = body.decode("utf-8", errors="replace")
        if not delta_mode:
            # Remove existing state to avoid mixing with a new full replay
            try:
                if os.path.exists(local_log):
                    os.remove(local_log)
                # Also reset active index
                active_index_path = os.path.join(out_dir, "active_index.csv")
                if os.path.exists(active_index_path):
                    os.remove(active_index_path)
            except OSError:
                pass
        mode = "a" if delta_mode else "w"
        with open(local_log, mode, encoding="utf-8") as f:
            if not text.endswith("\n"):
                text += "\n"
            f.write(text)
    except OSError as e:
        print(f"Failed to write local changes.log: {e}", file=sys.stderr)
        return 1

    # Update or rebuild active_index.csv used for matching
    try:
        active_index_path = os.path.join(out_dir, "active_index.csv")
        if delta_mode and os.path.exists(active_index_path):
            # Load current active set
            active = _load_active_index(base_dir, label, data_name)
        else:
            active = {}

        # Apply new events from response text
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            parts = ln.split()
            if len(parts) < 4:
                continue
            event, prf_h, enc_meta = parts[0].upper(), parts[1], parts[2]
            key = prf_h.lower()
            if event == "ADDED":
                active[key] = enc_meta
            elif event == "REMOVED":
                active.pop(key, None)

        with open(active_index_path, "w", encoding="utf-8") as f:
            for prf_h, enc_meta in active.items():
                f.write(f"{prf_h},{enc_meta}\n")
    except OSError as e:
        print(f"Failed to update active_index.csv: {e}", file=sys.stderr)
        return 1

    print(f"Saved changes to: {local_log}")
    print(f"Raw response at: {raw_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="client-cli", description="Client CLI for PSI sync")
    sub = p.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("sync_data", help="Fetch changes from server /sync_data and store locally")
    ps.add_argument("server", help="Server in host:port format, e.g. 127.0.0.1:8000")
    ps.add_argument("data_name", help="Alphanumeric data source name")
    ps.add_argument("--hash", help="Optional last known cumulative hash", default=None)
    ps.set_defaults(func=cmd_sync_data)

    pr = sub.add_parser("reset_data", help="Force a full fetch and reset local state for a dataset")
    pr.add_argument("server", help="Server in host:port format")
    pr.add_argument("data_name", help="Alphanumeric data source name")
    def _reset_entry(args: argparse.Namespace) -> int:
        # Purge local data for this dataset, then fetch a fresh full sync.
        rc = _purge_entry(args)
        if rc != 0:
            return rc
        # Call sync_data but skip local hash detection to ensure a full fetch.
        sync_args = argparse.Namespace(server=args.server, data_name=args.data_name, hash=None, skip_local_hash=True)
        return cmd_sync_data(sync_args)
    pr.set_defaults(func=_reset_entry)

    # purge_data command: remove local dataset and cleanup empty server directory, no sync
    pg = sub.add_parser("purge_data", help="Remove all local files for a server/data_name and delete the server directory if empty")
    pg.add_argument("server", help="Server in host:port format")
    pg.add_argument("data_name", help="Alphanumeric data source name")
    def _purge_entry(args: argparse.Namespace) -> int:
        try:
            host, port, label = _normalize_server(args.server)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        base_dir = os.path.dirname(os.path.abspath(__file__))
        out_dir = os.path.join(base_dir, "data", label, args.data_name)
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir, ignore_errors=True)
        # After removing the dataset, also remove the per-server directory if now empty
        label_dir = os.path.join(base_dir, "data", label)
        try:
            if os.path.isdir(label_dir) and not os.listdir(label_dir):
                os.rmdir(label_dir)
        except OSError:
            pass
        return 0
    pg.set_defaults(func=_purge_entry)

    pq = sub.add_parser("query", help="Query OPRF for an IOC and attempt metadata decryption")
    pq.add_argument("server", help="Server in host:port format")
    pq.add_argument("data_name", help="Alphanumeric data source name")
    pq.add_argument("ioc", help="IOC string to query (exact string used in source file)")
    pq.set_defaults(func=cmd_query)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
