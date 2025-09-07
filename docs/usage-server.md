---
title: Server CLI
nav_order: 3
---

# Server CLI

Entry point: `python -m server.cli`

## Commands

- create_source: Create or remove a dataset schema and private key
  - Create: `python -m server.cli create_source <data_name> -a classic -r 1d`
  - Remove: `python -m server.cli create_source <data_name> --remove`
  - Options:
    - `-a, --supported-algorithm`: `classic` (Ristretto255 OPRF) or `ot` (placeholder)
    - `-r, --rekey-interval`: e.g., `1d`, `7d` (validated, normalized)

- sync: Compute OPRF outputs and encrypted metadata, update index and changes log
  - `python -m server.cli sync <data_name> <path/to/source.txt>`
  - Reads source lines of the form `<ioc>,{json_metadata}`
  - Writes/updates:
    - `server/data/<data_name>/index.csv`
    - `server/data/<data_name>/changes.log`

- rekey: Generate a new private key, recompute all entries, refresh change log
  - `python -m server.cli rekey <data_name> <path/to/source.txt>`
  - Overwrites `index.csv` and resets `changes.log` to ADDED-only for all entries

- purge_data: Remove server data directory for a dataset
  - `python -m server.cli purge_data <data_name>`

- start_server: Start the HTTP API server
  - `python -m server.cli start_server 127.0.0.1:8000`

## Source File Format

- One IOC per line: `<ioc>,{json_metadata}`
- Right side must be valid JSON; `{}` if none
- Lines without a comma are ignored; blank lines allowed

