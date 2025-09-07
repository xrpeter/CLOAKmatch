import os
import re
import json
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
# Ensure workspace root is importable before importing our local 'shared' package
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.dirname(_THIS_DIR)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

from shared import crypto_tools


ALNUM_RE = re.compile(r"^[A-Za-z0-9]+$")


def _read_changes_log(base_dir: str, data_type: str) -> list[str]:
    path = os.path.join(base_dir, "data", data_type, "changes.log")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


class SyncHandler(BaseHTTPRequestHandler):
    server_version = "SimpleSyncServer/0.1"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        # Normalize trailing slash to support both /path and /path/
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        base_dir = os.path.dirname(os.path.abspath(__file__))

        if path == "/sync_data":
            data_type = (qs.get("data_type") or [None])[0]
            last_hash = (qs.get("hash") or [None])[0]

            if not data_type or not ALNUM_RE.fullmatch(data_type):
                self._send_json(400, {"error": "Invalid or missing data_type (alphanumeric only)"})
                return

            try:
                lines = _read_changes_log(base_dir, data_type)
            except FileNotFoundError:
                self._send_json(404, {"error": "changes.log not found for data_type"})
                return

            start_idx = 0
            matched = False
            if last_hash:
                # Look for a line whose last space-delimited token equals last_hash
                for i, line in enumerate(lines):
                    tok = line.strip().split()
                    if tok:
                        maybe_hash = tok[-1]
                        if maybe_hash == last_hash:
                            start_idx = i + 1
                            matched = True
                            break

            body_lines = lines[start_idx:]
            body = "".join(body_lines).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header(
                "Content-Disposition", f"attachment; filename=changes_{data_type}.log"
            )
            # Indicate whether this is a delta (hash matched) or full replay
            self.send_header("X-Delta", "delta" if matched else "full")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/encryption_type":
            data_type = (qs.get("data_type") or [None])[0]
            if not data_type or not ALNUM_RE.fullmatch(data_type):
                self._send_json(400, {"error": "Invalid or missing data_type (alphanumeric only)"})
                return

            # Verify the data_type exists by checking schema
            schema_path = os.path.join(base_dir, "schemas", data_type, "schema.json")
            if not os.path.exists(schema_path):
                self._send_json(404, {"error": "Unknown data_type"})
                return

            # Current server encrypts metadata with XChaCha20-Poly1305-IETF
            payload = {
                "data_type": data_type,
                "encryption": "xchacha20poly1305-ietf",
                "suite": "oprf-ristretto255-sha512",
            }
            self._send_json(200, payload)
            return

        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        base_dir = os.path.dirname(os.path.abspath(__file__))

        if path == "/oprf_evaluate":
            # Expect JSON: {"data_type": "name", "blinded": "hex-32-bytes"}
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(411, {"error": "Missing Content-Length"})
                return
            body = self.rfile.read(length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self._send_json(400, {"error": "Invalid JSON"})
                return

            data_type = payload.get("data_type")
            blinded_hex = payload.get("blinded")
            if not data_type or not ALNUM_RE.fullmatch(data_type):
                self._send_json(400, {"error": "Invalid or missing data_type"})
                return
            if not isinstance(blinded_hex, str):
                self._send_json(400, {"error": "Missing blinded"})
                return
            try:
                blinded = bytes.fromhex(blinded_hex)
            except ValueError:
                self._send_json(400, {"error": "Invalid blinded hex"})
                return
            if len(blinded) != 32:
                self._send_json(400, {"error": "Blinded point must be 32 bytes"})
                return

            # Validate schema and algorithm
            schema_path = os.path.join(base_dir, "schemas", data_type, "schema.json")
            if not os.path.exists(schema_path):
                self._send_json(404, {"error": "Unknown data_type"})
                return

            # Load server private key
            key_path = os.path.join(base_dir, "secrets", data_type, "private.key")
            if not os.path.exists(key_path):
                self._send_json(404, {"error": "Missing private key"})
                return
            try:
                with open(key_path, "rb") as f:
                    sk = f.read()
            except OSError as e:
                self._send_json(500, {"error": f"Failed to read key: {e}"})
                return

            try:
                evaluated = crypto_tools.evaluate_blinded_point(sk, blinded)
            except Exception as e:
                self._send_json(500, {"error": f"Evaluation failed: {e}"})
                return

            self._send_json(200, {"evaluated": evaluated.hex()})
            return

        self._send_json(404, {"error": "Not Found"})


def _parse_bind(bind: str) -> tuple[str, int]:
    if ":" not in bind:
        raise ValueError("Bind must be in 'host:port' format")
    host, port_s = bind.rsplit(":", 1)
    port = int(port_s)
    return host, port


def run_server(bind: str) -> None:
    host, port = _parse_bind(bind)
    httpd = ThreadingHTTPServer((host, port), SyncHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
