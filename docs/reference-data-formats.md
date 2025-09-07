---
title: Data Formats
permalink: /reference-data-formats/
---

# Data Formats

## Source File (input)

- One per line: `<ioc>,{json_metadata}`
- Examples:
  - `evil.com,{"desc":"known bad domain"}`
  - `1.2.3.4,{"as":"AS64500","type":"ip"}`
  - `44d88612fea8a8f36de82e1278abb02f,{"type":"md5"}`
- Rules:
  - Right side must be valid JSON; use `{}` if none
  - Lines without a comma are ignored; blank lines allowed

## Server `index.csv`

Location: `server/data/<data_name>/index.csv`

- CSV with columns: `IOC,PRF_HEX,NONCE_HEX,CT_HEX`
- Used internally to compute deltas and serve client syncs; not exposed directly

## Server `changes.log`

Location: `server/data/<data_name>/changes.log`

- Space-separated lines with cumulative hash chain:

```
EVENT OPRF_HEX ENC_META_HEX HASH_HEX
```

- `EVENT`: `ADDED` or `REMOVED`
- `OPRF_HEX`: 128-hex chars (SHA-512) or `-` when unknown for removals
- `ENC_META_HEX`: `NONCE_HEX:CT_HEX` or `-`
- `HASH_HEX`: cumulative SHA-512 over `prev_hash | EVENT | OPRF_HEX | ENC_META_HEX`

## Client `active_index.csv`

Location: `client/data/<server_label>/<data_name>/active_index.csv`

- Compact mapping: `PRF_HEX,NONCE_HEX:CT_HEX`
- Updated on every `sync_data` to reflect current active entries
