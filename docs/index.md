---
title: CLOAKmatch
nav_order: 1
---

Private set-style syncing via Ristretto255 OPRF with encrypted metadata.

Use the left navigation to explore:

- Quickstart: two commands to run server and client
- Source File Format: simple line format with JSON metadata
- CLI Reference: helper scripts and full server/client CLIs
- HTTP API: endpoints for sync, encryption type, and OPRF

Highlights:

- Strong privacy: OPRF on Ristretto255 + SHA-512
- Secure metadata: XChaCha20-Poly1305
- Simple workflow: one-line server and client helpers

## Prerequisites

- Python 3.11+
- Python packages (dev/test):
  - Create venv: `python -m venv .venv`
  - Activate: `source .venv/bin/activate` (Windows PowerShell: `.venv\\Scripts\\Activate.ps1`)
  - Install: `python -m pip install -r requirements.txt`
- libsodium:
  - macOS: `brew install libsodium`
  - Debian/Ubuntu: `sudo apt-get install libsodium23 libsodium-dev`

## Quickstart

Two commands: one to start the server with a demo dataset, one to sync and query from the client.

1) Terminal A (server):

```
python server_simple.py --host 127.0.0.1 --port 8000 --name testSource --source path/to/source.txt
```

2) Terminal B (client):

```
python client_simple.py <ioc> --server 127.0.0.1:8000 --name testSource
```

## Source File Format

Plain text, UTF-8; one item per line:

- `<ioc>,{json_metadata}`

Examples:

- `evil.com,{"desc":"known bad domain"}`
- `1.2.3.4,{"as":"AS64500","type":"ip"}`
- `44d88612fea8a8f36de82e1278abb02f,{"type":"md5"}`

Notes:

- Right side must be valid JSON. Use `{}` if no metadata.
- Lines without a comma are skipped; blank lines allowed.
- Proper JSON quoting is required (double quotes, no trailing commas).

## CLI Reference

### One-liners

- `server_simple.py`: Creates/refreshes dataset, syncs, starts HTTP API.
- `client_simple.py`: Syncs and queries a single IOC.

### Server CLI (`python -m server.cli ...`)

- `create_source <data_name> [-a classic|ot] [-r <days>d] [--remove]`
- `sync <data_name> <path/to/source.txt>`
- `rekey <data_name> <path/to/source.txt>`
- `purge_data <data_name>`
- `start_server <host:port>`

### Client CLI (`python -m client.cli ...`)

- `sync_data <host:port> <data_name> [--hash <hex>]`
- `reset_data <host:port> <data_name>`
- `purge_data <host:port> <data_name>`
- `query <host:port> <data_name> <ioc>`

## HTTP API (Server)

- `GET /sync_data?data_type=<name>[&hash=<hex>]` → text/plain delta or full changes
- `GET /encryption_type?data_type=<name>` → `{"suite":"oprf-ristretto255-sha512","encryption":"xchacha20poly1305-ietf"}`
- `POST /oprf_evaluate` with JSON `{ "data_type": "<name>", "blinded": "<hex>" }` → `{ "evaluated": "<hex>" }`

## How It Works

- Server computes OPRF(PRF) over each IOC (Ristretto255 + SHA‑512), encrypts metadata with a key derived from HKDF(PRF||Q), and maintains an append-only `changes.log` (ADDED/REMOVED with nonce:ciphertext and a cumulative hash).
- Client syncs `changes.log`, runs OPRF for the query IOC via the server’s `/oprf_evaluate`, finalizes PRF locally, and decrypts the matching encrypted metadata if present.

## Enable GitHub Pages

1. Commit and push the `docs/` folder to your repository.
2. In GitHub: Settings → Pages.
3. Build and deployment → Source: select `Deploy from a branch`.
4. Branch: choose your default branch (e.g., `main`) and `/docs` folder.
5. Save. The site will be published at: `https://<your-user-or-org>.github.io/<your-repo>/`

Tip: To include the project logo on this site, copy `CLOAKmatch.png` into `docs/` and reference it as `CLOAKmatch.png`.
