---
title: CLI Reference
---

# CLI Reference

## One-liner Helpers

- `server_simple.py`: Creates/refreshes a dataset, prepares a sample (or uses `--source`), syncs, and starts the HTTP API.
- `client_simple.py`: Syncs changes and queries a single IOC.

## Server CLI

Invoke as `python -m server.cli <command> [args]`.

- `create_source <data_name> [-a classic|ot] [-r <days>d] [--remove]`
- `sync <data_name> <path/to/source.txt>`
- `rekey <data_name> <path/to/source.txt>`
- `purge_data <data_name>`
- `start_server <host:port>`

## Client CLI

Invoke as `python -m client.cli <command> [args]`.

- `sync_data <host:port> <data_name> [--hash <hex>]`
- `reset_data <host:port> <data_name>`
- `purge_data <host:port> <data_name>`
- `query <host:port> <data_name> <ioc>`

