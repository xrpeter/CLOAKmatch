import os
import sys
import hashlib
from typing import Iterable, Tuple, Iterator, Dict, Any, List, Optional, Tuple as Tup

# Ensure we can import the shared crypto package when invoked via CLI
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.dirname(_THIS_DIR)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

from shared import crypto_tools


def _iter_iocs_from_file(path: str) -> Iterable[Tuple[int, str, str]]:
    """Yield (line_no, ioc, metadata) from a data source file.

    Each line must be of the form: '<ioc>,{...metadata...}'
    Returns the IOC (left side of the first comma) and the raw metadata string
    (right side of the first comma) with surrounding whitespace trimmed.
    Blank lines are skipped.
    """
    with open(path, "r", encoding="utf-8") as f:
        for idx, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            if "," not in line:
                # Skip malformed lines; caller can decide how to handle
                continue
            ioc_part, meta_part = line.split(",", 1)
            ioc = ioc_part.strip()
            metadata = meta_part.strip()
            if ioc:
                yield idx, ioc, metadata


def sync_data(data_name: str, data_source_file: str) -> int:
    """Perform server-side computation for each IOC using RFC 9497 VOPRF.

    Returns process exit code (0 on success, non-zero on failure).
    """
    # Load schema
    schema_path = os.path.join(_THIS_DIR, "schemas", data_name, "schema.json")
    if not os.path.exists(schema_path):
        print(f"Schema not found for '{data_name}': {schema_path}", file=sys.stderr)
        return 1

    # Read supported algorithm from schema
    import json

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except Exception as e:
        print(f"Failed to load schema: {e}", file=sys.stderr)
        return 1

    algo = str(schema.get("supported_algorithm", "classic")).lower()
    if algo == "ot":
        print("OT sync not yet implemented; aborting.", file=sys.stderr)
        return 2
    if algo != "classic":
        print(f"Unsupported algorithm in schema: {algo}", file=sys.stderr)
        return 2

    # Load private key
    key_path = os.path.join(_THIS_DIR, "secrets", data_name, "private.key")
    if not os.path.exists(key_path):
        print(f"Private key not found for '{data_name}': {key_path}", file=sys.stderr)
        return 1
    try:
        with open(key_path, "rb") as f:
            sk = f.read()
    except OSError as e:
        print(f"Failed to read private key: {e}", file=sys.stderr)
        return 1

    # Prepare output directory and file under server/data/<data_name>/
    out_dir = os.path.join(_THIS_DIR, "data", data_name)
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as e:
        print(f"Failed to create output directory '{out_dir}': {e}", file=sys.stderr)
        return 1

    # index.csv persists server-side IOC -> values; evaluations.txt is redundant
    index_path = os.path.join(out_dir, "index.csv")
    index_path = os.path.join(out_dir, "index.csv")
    log_path = os.path.join(out_dir, "changes.log")

    # Load current IOCs from source file
    try:
        current_iocs: list[str] = []
        current_meta: Dict[str, str] = {}
        for _, ioc, metadata in _iter_iocs_from_file(data_source_file):
            current_iocs.append(ioc)
            current_meta[ioc] = metadata
    except FileNotFoundError:
        print(f"Source file not found: {data_source_file}", file=sys.stderr)
        return 1
    current_set = set(current_iocs)

    # Load existing evaluations index if present (server-side mapping of IOC->hex)
    existing_order: list[str] = []  # preserve order
    # Map: IOC -> { 'oprf': hex, 'nonce': hex|None, 'ct': hex|None }
    existing_map: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or "," not in line:
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    ioc = parts[0]
                    hexval = parts[1] if len(parts) > 1 else ""
                    nonce = parts[2] if len(parts) > 2 else None
                    ct = parts[3] if len(parts) > 3 else None
                    if not ioc:
                        continue
                    existing_order.append(ioc)
                    existing_map[ioc] = {"oprf": hexval, "nonce": nonce, "ct": ct}
        except OSError as e:
            print(f"Failed to read existing evaluations index: {e}", file=sys.stderr)
            return 1

    # Determine changes
    to_remove = [ioc for ioc in existing_order if ioc not in current_set]
    to_add = [ioc for ioc in current_iocs if ioc not in existing_map]
    # Upgrade entries missing encrypted metadata
    to_upgrade = [
        ioc for ioc in current_iocs
        if ioc in existing_map and (existing_map[ioc].get("nonce") is None or existing_map[ioc].get("ct") is None)
    ]

    # Compute evaluations for additions
    try:
        for ioc in to_add + to_upgrade:
            # Compute OPRF and encryption of metadata
            prf_bytes = None
            nonce = None
            ct = None
            prf_bytes, nonce, ct = crypto_tools.evaluate_and_encrypt_metadata(
                sk, ioc.encode("utf-8"), data_name, current_meta.get(ioc, "").encode("utf-8")
            )
            existing_map[ioc] = {"oprf": prf_bytes.hex(), "nonce": nonce.hex(), "ct": ct.hex()}
    except crypto_tools.MissingLibraryError as e:
        print(str(e), file=sys.stderr)
        return 3
    except Exception as e:
        print(f"Error computing evaluations: {e}", file=sys.stderr)
        return 1

    # Snapshot previous values for removal logging, then apply removals
    prev_map = {k: v.copy() for k, v in existing_map.items()}
    for ioc in to_remove:
        existing_map.pop(ioc, None)

    # Build new order: keep existing order minus removals, then append additions in source order
    new_order = [ioc for ioc in existing_order if ioc in existing_map]
    for ioc in current_iocs:
        if ioc not in new_order:
            new_order.append(ioc)

    # Write back index (ioc,hex[,nonce,ct]); skip evaluations.txt to reduce redundancy
    try:
        with open(index_path, "w", encoding="utf-8") as idxf:
            for ioc in new_order:
                entry = existing_map[ioc]
                hexval = entry["oprf"]
                nonce = entry.get("nonce")
                ct = entry.get("ct")
                if nonce is None or ct is None:
                    idxf.write(f"{ioc},{hexval}\n")
                else:
                    idxf.write(f"{ioc},{hexval},{nonce},{ct}\n")
    except OSError as e:
        print(f"Failed to write index file '{index_path}': {e}", file=sys.stderr)
        return 1

    # Append changes to log including OPRF and encrypted metadata (no raw IOC)
    # with a cumulative hash chain.
    try:
        events: List[Tup[str, Optional[str], Optional[str]]] = []
        for ioc in to_add:
            op = existing_map[ioc]
            enc_meta = None
            if op.get("nonce") and op.get("ct"):
                enc_meta = f"{op['nonce']}:{op['ct']}"
            events.append(("ADDED", op["oprf"], enc_meta))
        for ioc in to_remove:
            old_entry = prev_map.get(ioc)
            old_hex = old_entry.get("oprf") if old_entry else None
            old_enc = None
            if old_entry and old_entry.get("nonce") and old_entry.get("ct"):
                old_enc = f"{old_entry['nonce']}:{old_entry['ct']}"
            events.append(("REMOVED", old_hex, old_enc))
        _append_change_events(log_path, events)
    except OSError as e:
        print(f"Failed to append change log '{log_path}': {e}", file=sys.stderr)
        return 1

    print(f"Updated index at: {index_path}")
    print(f"Logged changes at: {log_path}")
    return 0


def rekey_data(data_name: str, data_source_file: str) -> int:
    """Rotate the private key and recompute evaluations for all IOCs.

    Steps:
    1) Validate schema and algorithm (classic only)
    2) Generate and store a new 32-byte private key
    3) Recompute OPRF outputs for all IOCs in the source file
    4) Overwrite evaluations.txt with new values
    5) Truncate changes.log to empty
    """
    # Load schema
    schema_path = os.path.join(_THIS_DIR, "schemas", data_name, "schema.json")
    if not os.path.exists(schema_path):
        print(f"Schema not found for '{data_name}': {schema_path}", file=sys.stderr)
        return 1

    import json

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except Exception as e:
        print(f"Failed to load schema: {e}", file=sys.stderr)
        return 1

    algo = str(schema.get("supported_algorithm", "classic")).lower()
    if algo == "ot":
        print("OT rekey not yet implemented; aborting.", file=sys.stderr)
        return 2
    if algo != "classic":
        print(f"Unsupported algorithm in schema: {algo}", file=sys.stderr)
        return 2

    # Generate and write new private key
    secrets_dir = os.path.join(_THIS_DIR, "secrets", data_name)
    os.makedirs(secrets_dir, exist_ok=True)
    key_path = os.path.join(secrets_dir, "private.key")
    try:
        sk = crypto_tools.generate_ristretto255_private_key()
        with open(key_path, "wb") as f:
            f.write(sk)
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
    except OSError as e:
        print(f"Failed to write new private key: {e}", file=sys.stderr)
        return 1

    # Prepare output directory and files
    out_dir = os.path.join(_THIS_DIR, "data", data_name)
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as e:
        print(f"Failed to create output directory '{out_dir}': {e}", file=sys.stderr)
        return 1

    index_path = os.path.join(out_dir, "index.csv")
    log_path = os.path.join(out_dir, "changes.log")

    # Load current IOCs and metadata from source file
    try:
        current_iocs: list[str] = []
        current_meta: Dict[str, str] = {}
        for _, ioc, metadata in _iter_iocs_from_file(data_source_file):
            current_iocs.append(ioc)
            current_meta[ioc] = metadata
    except FileNotFoundError:
        print(f"Source file not found: {data_source_file}", file=sys.stderr)
        return 1

    # Recompute and overwrite index (ioc, prf_hex, nonce_hex, ct_hex)
    try:
        added_entries = []  # collect (ioc, prf_hex, nonce_hex, ct_hex) for logging
        with open(index_path, "w", encoding="utf-8") as idxf:
            for ioc in current_iocs:
                prf_bytes, nonce, ct = crypto_tools.evaluate_and_encrypt_metadata(
                    sk, ioc.encode("utf-8"), data_name, current_meta.get(ioc, "").encode("utf-8")
                )
                hexval = prf_bytes.hex()
                nonce_hex = nonce.hex()
                ct_hex = ct.hex()
                idxf.write(f"{ioc},{hexval},{nonce_hex},{ct_hex}\n")
                added_entries.append((ioc, hexval, nonce_hex, ct_hex))
    except crypto_tools.MissingLibraryError as e:
        print(str(e), file=sys.stderr)
        return 3
    except OSError as e:
        print(f"Failed to write index file '{index_path}': {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error during rekey evaluation: {e}", file=sys.stderr)
        return 1

    # Refresh changes log to list additions for all elements post-rekey
    try:
        # Truncate and then append ADDED events with cumulative hash chain
        with open(log_path, "w", encoding="utf-8"):
            pass
        rekey_events: List[Tup[str, Optional[str], Optional[str]]] = []
        for ioc, hexval, nonce_hex, ct_hex in added_entries:
            enc_meta = f"{nonce_hex}:{ct_hex}" if nonce_hex and ct_hex else None
            rekey_events.append(("ADDED", hexval, enc_meta))
        _append_change_events(log_path, rekey_events)
    except OSError as e:
        print(f"Failed to write change log '{log_path}': {e}", file=sys.stderr)
        return 1

    print(f"Rekey complete. Updated key: {key_path}")
    print(f"Rewrote index: {index_path}")
    print(f"Cleared change log: {log_path}")
    return 0


def _append_change_events(log_path: str, events: List[Tup[str, Optional[str], Optional[str]]]) -> None:
    """Append change events to the log with a cumulative SHA-512 hash chain.

    Line format (space separated):
      EVENT OPRF_HEX ENC_META_HEX HASH_HEX

    - EVENT: ADDED or REMOVED
    - OPRF_HEX: 128-hex chars if provided, or '-' if unknown
    - ENC_META_HEX: nonce_hex:ct_hex if provided, or '-' if unknown
    - HASH_HEX: cumulative SHA-512 over (prev_hash || '|' || EVENT || '|' || OPRF_HEX || '|' || ENC_META_HEX)

    The chain seeds prev_hash = 64 zero bytes when the log is empty. For
    backward-compat, if the last existing line used the old comma-separated
    format, we still extract its trailing hash token if present.
    """
    prev_hash = b"\x00" * 64
    # Attempt to read the last hash from the existing log
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                last = None
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    last = line
                if last:
                    # Tokenize by whitespace first; fallback to comma
                    tokens = last.split()
                    if len(tokens) >= 2:
                        last_hex = tokens[-1]
                    else:
                        parts = last.rsplit(",", 1)
                        last_hex = parts[-1].strip() if len(parts) > 1 else ""
                    if len(last_hex) in (64, 128):
                        try:
                            prev_hash = bytes.fromhex(last_hex)
                        except ValueError:
                            prev_hash = b"\x00" * 64
        except OSError:
            pass

    with open(log_path, "a", encoding="utf-8") as logf:
        for ev, hexval, enc_meta in events:
            ev = (ev or "").strip().upper()
            if ev not in ("ADDED", "REMOVED"):
                continue
            hex_part = (hexval or "-")
            meta_part = (enc_meta or "-")
            new_hash = hashlib.sha512(
                prev_hash + b"|" + ev.encode("utf-8") + b"|" + hex_part.encode("utf-8") + b"|" + meta_part.encode("utf-8")
            ).digest()
            logf.write(f"{ev} {hex_part} {meta_part} {new_hash.hex()}\n")
            prev_hash = new_hash
