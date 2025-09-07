---
title: HTTP API
nav_order: 5
---

All endpoints are served over HTTP by `server.api_server` once started via `python -m server.cli start_server <host:port>` or `server_simple.py`.

## GET /sync_data

Query parameters:

- `data_type`: dataset name
- `hash` (optional): last known cumulative hash

Response:

- `text/plain` body containing one or more lines, each: `EVENT OPRF_HEX ENC_META_HEX HASH_HEX`
- Header `X-Delta: delta` when returning a delta, omitted for full responses

## GET /encryption_type

Query parameters:

- `data_type`: dataset name

Response JSON:

```
{"suite":"oprf-ristretto255-sha512","encryption":"xchacha20poly1305-ietf"}
```

## POST /oprf_evaluate

Request JSON:

```
{ "data_type": "<name>", "blinded": "<hex>" }
```

Response JSON:

```
{ "evaluated": "<hex>" }
```
