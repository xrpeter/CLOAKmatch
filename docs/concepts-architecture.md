---
title: Architecture
permalink: /concepts-architecture/
---

# Architecture

## Components

- Server
  - CLI for dataset lifecycle: create, sync, rekey, purge, serve
  - HTTP API for clients: `/sync_data`, `/encryption_type`, `/oprf_evaluate`
  - Data directory per dataset: `server/data/<data_name>/`

- Client
  - CLI for syncing, querying, managing local state
  - Local mirror per server and dataset: `client/data/<server_label>/<data_name>/`

- Shared Crypto
  - Ristretto255 operations, OPRF finalize, HKDF, and XChaCha20-Poly1305 via libsodium

## Flows

### Dataset Build (Server)

1) Load source file `<ioc>,{json}`
2) For each IOC, compute PRF and encrypt metadata
3) Update `index.csv` and append to `changes.log` with hash chaining

### Client Sync

1) Fetch `changes.log` from `/sync_data` (full or delta)
2) Append or rebuild local `changes.log`
3) Maintain `active_index.csv` for fast lookups

### Query

1) Ensure latest sync
2) Compute `P = H1(ioc)`, blind to `B = r*P`
3) POST to `/oprf_evaluate` and receive `E = k*B`
4) Unblind to `Q = r^{-1}*E`, finalize `PRF = H(ioc, Q)`
5) If `PRF` active, decrypt metadata and return to user
