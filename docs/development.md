---
title: Development
permalink: /development/
---

# Development

## Repo Structure

- `server/`: CLI and HTTP API; dataset state under `server/data/`
- `client/`: CLI and local cache under `client/data/`
- `shared/`: crypto helpers built on libsodium
- `tests/`: pytest covering CLI, API, and end-to-end flows

## Setup

Use the steps in Getting Started to install dependencies and libsodium.

## Running Tests

```
python -m pip install pytest
pytest -q
```

## Coding Notes

- Python 3.11+
- Avoid printing secrets; key files are stored under `server/secrets/<data_name>/private.key` with restrictive permissions where possible
- Client/server import `shared.crypto_tools` via a workspace-root insertion for reliable imports
