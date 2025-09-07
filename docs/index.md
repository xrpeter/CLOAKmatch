---
title: Overview
permalink: /
---

# CLOAKmatch

Private set-style syncing of indicators with encrypted metadata using an OPRF on Ristretto255 and XChaCha20-Poly1305.

Tip: To display the logo on this site, copy `CLOAKmatch.png` into the `docs/` folder; it is already referenced in `docs/_config.yml`.

## What Is It?

- Server computes OPRF(PRF) over each IOC (Ristretto255 + SHA-512), encrypts per-IOC metadata using a key derived from HKDF(PRF||Q), and maintains an append-only `changes.log` of ADDED/REMOVED events with a cumulative hash chain.
- Client syncs `changes.log`, runs OPRF for the query IOC via the server’s `/oprf_evaluate` endpoint, finalizes the PRF locally, and decrypts matching metadata if present — without revealing the raw IOC to the server.

## Quick Links

- Getting Started: prerequisites and quickstart — see Getting Started
- Server CLI: create, sync, rekey, purge, start — see Server CLI
- Client CLI: sync, reset, purge, query — see Client CLI
- HTTP API: `/sync_data`, `/encryption_type`, `/oprf_evaluate` — see HTTP API
- Data Formats: source file, `index.csv`, `changes.log` — see Data Formats
- Security: OPRF suite and AEAD details — see Security

## Quickstart

1) Install prerequisites — see Getting Started.

2) In one terminal, start the server with a sample dataset:

```
python server_simple.py --host 127.0.0.1 --port 8000 --name testSource
```

3) In another terminal, sync and query an IOC:

```
python client_simple.py evil.com --server 127.0.0.1:8000 --name testSource
```

If the IOC appears in the dataset, the client prints PRF and decrypted metadata.

## Repository Layout

- `server/cli.py`: server CLI (create_source, sync, rekey, purge_data, start_server)
- `server/api_server.py`: HTTP endpoints (`/sync_data`, `/encryption_type`, `/oprf_evaluate`)
- `server/data_sync.py`: server-side processing and `changes.log` logic
- `client/cli.py`: client CLI (sync_data, reset_data, purge_data, query)
- `server_simple.py`: one-shot server bootstrap (dataset + sample + start_server)
- `client_simple.py`: one-shot client sync + query for a provided IOC
- `shared/crypto_tools.py`: libsodium-backed OPRF + XChaCha20-Poly1305 helpers
- `tests/`: pytest suite (CLI, API, end-to-end)
