---
title: Client CLI
permalink: /usage-client/
---

# Client CLI

Entry point: `python -m client.cli`

## Commands

- sync_data: Fetch changes from server and update local state
  - `python -m client.cli sync_data <host:port> <data_name> [--hash <last_hash>]`
  - Stores under `client/data/<server_label>/<data_name>/`:
    - `changes.log`: cumulative change log
    - `active_index.csv`: current active PRF→enc_meta mapping
    - Raw payloads: `full-YYYYmmdd-HHMMSS.log` or `delta-YYYYmmdd-HHMMSS.log`

- reset_data: Force a full fetch and reset local state
  - `python -m client.cli reset_data <host:port> <data_name>`

- purge_data: Remove all local files for a dataset (and clean up empty server dir)
  - `python -m client.cli purge_data <host:port> <data_name>`

- query: OPRF query and metadata decryption for a single IOC
  - `python -m client.cli query <host:port> <data_name> <ioc>`
  - Flow:
    1) Sync latest `changes.log`
    2) Discover encryption type via `/encryption_type`
    3) Hash IOC to group, blind, send to `/oprf_evaluate`
    4) Unblind, finalize PRF, look up in `active_index.csv`
    5) Decrypt metadata if present

## Local Layout

`client/data/<server_label>/<data_name>/`

- `changes.log`: mirror of server log (full then deltas)
- `active_index.csv`: compact active set for fast matching
- `matches.txt`: optional append-only record of successful queries
