---
title: HTTP API
permalink: /api-http/
---

# HTTP API

Base URL is the server bind, e.g., `http://127.0.0.1:8000`.

## GET /sync_data

Return the change log for a dataset — either full or tail delta.

- Query: `data_type=<name>[&hash=<last_seen_hash>]`
- 200 OK with `text/plain` body of lines: `EVENT OPRF_HEX ENC_META_HEX HASH_HEX`
- Headers:
  - `X-Delta: full|delta` — indicates whether response is a full replay or a delta after the provided hash
- 400 if `data_type` invalid, 404 if dataset not found

## GET /encryption_type

Discover encryption suite for a dataset.

- Query: `data_type=<name>`
- 200 OK JSON:

```
{ "data_type": "<name>", "encryption": "xchacha20poly1305-ietf", "suite": "oprf-ristretto255-sha512" }
```

- 400 for invalid name, 404 if dataset unknown

## POST /oprf_evaluate

Evaluate the OPRF on a blinded group element.

- JSON body: `{ "data_type": "<name>", "blinded": "<hex 32 bytes>" }`
- 200 OK JSON: `{ "evaluated": "<hex 32 bytes>" }`
- Errors: 400 for invalid inputs, 404 if key/schema missing, 500 for evaluation errors

Notes:

- Client sends `B = r * H1(IOC)`; server returns `E = k * B`; client unblinds and finalizes.
- See Client CLI for the full query flow.
