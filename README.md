# CLOAKmatch: Server and Client (Ristretto255 OPRF)

Private set-style syncing of indicators and encrypted metadata via an OPRF on Ristretto255 with XChaCha20-Poly1305. This repo contains:
- Server CLI + HTTP API (serves changes and OPRF evaluation)
- Client CLI (syncs changes, queries an IOC, decrypts metadata on match)
- Tests (CLI + HTTP + end-to-end)

Quickstart shows the happy path to get a “Match found” or “No active match” on a fresh server and client.

**Happy Path (Minimal Commands)**
- Prereqs: Python 3.11+; libsodium installed (macOS: `brew install libsodium`, Debian/Ubuntu: `sudo apt-get install libsodium23 libsodium-dev`).

Server (terminal A)
- Create a dataset and key:
  - `python -m server.cli create_source testSource -a classic -r 1d`
- Prepare a simple source file (CSV-like: `ioc,{json_metadata}`):
  - `echo 'evil.com,{"desc":"known bad domain"}' > data.txt`
- Compute server-side outputs and change log:
  - `python -m server.cli sync testSource data.txt`
- Start the HTTP API:
  - `python -m server.cli start_server 127.0.0.1:8000`

Client (terminal B)
- Sync changes from the server:
  - `python -m client.cli sync_data 127.0.0.1:8000 testSource`
- Query an IOC (match):
  - `python -m client.cli query 127.0.0.1:8000 testSource evil.com`
  - Output includes:
    - `Match found.`
    - `Metadata: {"desc":"known bad domain"}`
- Query an IOC (no match):
  - `python -m client.cli query 127.0.0.1:8000 testSource benign.com`
  - Output: `No active match found in changes.log (either not present or removed)`

What It Does
- Server computes OPRF(PRF) over each IOC (Ristretto255 + SHA‑512), encrypts metadata with a key derived from HKDF(PRF||Q), and maintains an append-only `changes.log` (ADDED/REMOVED with nonce:ciphertext and a cumulative hash).
- Client syncs `changes.log`, runs OPRF for the query IOC via the server’s `/oprf_evaluate`, finalizes PRF locally, and decrypts the matching encrypted metadata if present.

Repository Layout
- `server/cli.py`: server CLI (create_source, sync, rekey, purge_data, start_server)
- `server/api_server.py`: HTTP endpoints (`/sync_data`, `/encryption_type`, `/oprf_evaluate`)
- `server/data_sync.py`: server-side processing and `changes.log` logic
- `client/cli.py`: client CLI (sync_data, reset_data, purge_data, query)
- `shared/crypto_tools.py`: libsodium-backed OPRF + XChaCha20-Poly1305 helpers
- `tests/`: pytest suite (CLI, API, end-to-end)

Key Commands
- Create dataset schema + key: `python -m server.cli create_source <data_name> -a classic -r 1d`
  - Remove (cleanup only schema + key): `python -m server.cli create_source <data_name> --remove`
- Sync from a source file: `python -m server.cli sync <data_name> <path/to/source.txt>`
- Rekey (new private key, rebuild index, reset changes.log to ADDED-only):
  - `python -m server.cli rekey <data_name> <path/to/source.txt>`
- Purge server data directory: `python -m server.cli purge_data <data_name>`
- Start HTTP API: `python -m server.cli start_server 127.0.0.1:8000`
- Client full/delta sync: `python -m client.cli sync_data <host:port> <data_name>`
- Client purge: `python -m client.cli purge_data <host:port> <data_name>`
- Client reset + fresh full sync: `python -m client.cli reset_data <host:port> <data_name>`
- Client query: `python -m client.cli query <host:port> <data_name> <ioc>`

Data Formats (server/data/<data_name>/)
- `index.csv`: `IOC,PRF_HEX,NONCE_HEX,CT_HEX` (used for computing changes; not served directly)
- `changes.log`: space-separated lines with cumulative hash chain:
  - `EVENT OPRF_HEX ENC_META_HEX HASH_HEX`
  - `EVENT ∈ {ADDED, REMOVED}`; `ENC_META_HEX = NONCE_HEX:CT_HEX or '-'`

Security Notes
- OPRF suite: Ristretto255 + SHA‑512. Metadata encryption: XChaCha20‑Poly1305‑IETF.
- The nonce is public in AEAD; secrecy is not required. Decryption requires both PRF and Q for the exact IOC (obtained via OPRF), which the log alone does not reveal.

Testing
- Install pytest: `python -m pip install pytest`
- Ensure libsodium is installed (macOS: `brew install libsodium`, Debian/Ubuntu: `sudo apt-get install libsodium23 libsodium-dev`).
- Run tests: `pytest -q`
  - Includes CLI tests, API tests (full and delta), error cases, and end-to-end client↔server query flow.

Troubleshooting
- libsodium not found: set `SODIUM_LIBRARY_PATH` to the libsodium library file or install via your package manager.
- Port already in use: choose a different bind, e.g., `127.0.0.1:8001`.
