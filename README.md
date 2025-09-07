<p align="center">
  <img src="CLOAKmatch.png" alt="CLOAKmatch logo" width="520" />
</p>

# CLOAKmatch: Server and Client (Ristretto255 OPRF)

Private set-style syncing of indicators with encrypted metadata using an OPRF on Ristretto255 and XChaCha20-Poly1305.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quickstart](#quickstart)
- [Source File Format](#source-file-format)
- [How It Works](#how-it-works)
- [Repository Layout](#repository-layout)
- [Commands](#commands)
- [Data Formats](#data-formats)
- [Security](#security)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
 - [Documentation Site](#documentation-site)

## Prerequisites

- Python 3.11+
- Python packages (dev/test):
  - Create a virtual environment (recommended): `python -m venv .venv`
  - Activate it: `source .venv/bin/activate` (Windows PowerShell: `.venv\\Scripts\\Activate.ps1`)
  - Install requirements: `python -m pip install -r requirements.txt`
- libsodium:
  - macOS: `brew install libsodium`
  - Debian/Ubuntu: `sudo apt-get install libsodium23 libsodium-dev`

## Quickstart

Two simple commands: one to set up and run the server, one to sync and query from the client.

### Server (terminal A)
- Start the server with a demo dataset and sample IOC/metadata:
  - `python server_simple.py`
  - Options: `--host 127.0.0.1 --port 8000 --name testSource --source path/to/source.txt`

### Client (terminal B)
- Sync and query in one shot (replace `<ioc>`):
  - `python client_simple.py <ioc>`
  - Example: `python client_simple.py evil.com`
  - Options: `--server 127.0.0.1:8000 --name testSource`

## Source File Format

Plain text, UTF-8; one item per line in the form:

- `<ioc>,{json_metadata}`

Examples:

- `evil.com,{"desc":"known bad domain"}`
- `1.2.3.4,{"as":"AS64500","type":"ip"}`
- `44d88612fea8a8f36de82e1278abb02f,{"type":"md5"}`

Notes:

- The right side must be valid JSON. Use `{}` if you have no metadata.
- Lines without a comma are skipped; blank lines are allowed.
- The server reads the file as-is; quoting must be proper JSON (double quotes, no trailing commas).

## How It Works
- Server computes OPRF(PRF) over each IOC (Ristretto255 + SHA‑512), encrypts metadata with a key derived from HKDF(PRF||Q), and maintains an append-only `changes.log` (ADDED/REMOVED with nonce:ciphertext and a cumulative hash).
- Client syncs `changes.log`, runs OPRF for the query IOC via the server’s `/oprf_evaluate`, finalizes PRF locally, and decrypts the matching encrypted metadata if present.

## Repository Layout
- `server/cli.py`: server CLI (create_source, sync, rekey, purge_data, start_server)
- `server/api_server.py`: HTTP endpoints (`/sync_data`, `/encryption_type`, `/oprf_evaluate`)
- `server/data_sync.py`: server-side processing and `changes.log` logic
- `client/cli.py`: client CLI (sync_data, reset_data, purge_data, query)
- `server_simple.py`: one-shot server bootstrap (dataset + sample + start_server)
- `client_simple.py`: one-shot client sync + query for a provided IOC
- `shared/crypto_tools.py`: libsodium-backed OPRF + XChaCha20-Poly1305 helpers
- `tests/`: pytest suite (CLI, API, end-to-end)

## Commands
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

## Data Formats
- Location: `server/data/<data_name>/`
- `index.csv`: `IOC,PRF_HEX,NONCE_HEX,CT_HEX` (used for computing changes; not served directly)
- `changes.log`: space-separated lines with cumulative hash chain:
  - `EVENT OPRF_HEX ENC_META_HEX HASH_HEX`
  - `EVENT ∈ {ADDED, REMOVED}`; `ENC_META_HEX = NONCE_HEX:CT_HEX or '-'`

## Security
- OPRF suite: Ristretto255 + SHA‑512. Metadata encryption: XChaCha20‑Poly1305‑IETF.
- The nonce is public in AEAD; secrecy is not required. Decryption requires both PRF and Q for the exact IOC (obtained via OPRF), which the log alone does not reveal.

## Testing
- Install pytest: `python -m pip install pytest`
- Ensure libsodium is installed (macOS: `brew install libsodium`, Debian/Ubuntu: `sudo apt-get install libsodium23 libsodium-dev`).
- Run tests: `pytest -q`
  - Includes CLI tests, API tests (full and delta), error cases, and end-to-end client↔server query flow.

## Troubleshooting
- libsodium not found: set `SODIUM_LIBRARY_PATH` to the libsodium library file or install via your package manager.
- Port already in use: choose a different bind, e.g., `127.0.0.1:8001`.

## Documentation Site

A documentation site is included under `docs/`, using the Minimal Mistakes Jekyll theme with a dark skin.

- Enable GitHub Pages: Settings → Pages → Source: `Deploy from a branch`; Branch: your default branch; Folder: `/docs`.
- The site will publish to `https://<your-user-or-org>.github.io/<your-repo>/`.
- To show the logo, copy `CLOAKmatch.png` into `docs/` (already referenced in `docs/_config.yml`).
- Start reading at `docs/index.md` or visit the published site once Pages is enabled.

Key sections:

- Overview and Quickstart: `docs/index.md`
- Getting Started and prerequisites: `docs/getting-started.md`
- Server CLI: `docs/usage-server.md`
- Client CLI: `docs/usage-client.md`
- HTTP API: `docs/api-http.md`
- Data formats and security: `docs/reference-data-formats.md`, `docs/reference-security.md`
