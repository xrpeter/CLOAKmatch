---
title: Security
nav_order: 7
---

# Security

## Cryptographic Suite

- OPRF: Ristretto255 group with SHA-512 finalization (RFC 9497-style flow)
- AEAD: XChaCha20-Poly1305-IETF for per-IOC metadata encryption
- Key derivation: HKDF-SHA512 with `IKM = PRF || Q`, `info = b"meta|" + data_name`
- AAD: the raw IOC bytes bind the ciphertext to a specific IOC

## Protocol Sketch

1) Server prepares dataset by computing PRF and encrypting metadata for each IOC; publishes `changes.log` only (no raw IOCs).
2) Client syncs the log and keeps a compact active index of `PRF_HEX → ENC_META`.
3) For a query IOC `x`, client computes `P = H1(x)`, chooses random `r`, sends `B = r * P` to the server.
4) Server returns `E = k * B`. Client computes `Q = r^{-1} * E`, finalizes `PRF = H(x, Q)`.
5) If `PRF` is present in the active index, client derives the AEAD key and decrypts metadata.

## Operational Notes

- Rekey rotates the server private key, recomputes the dataset, and resets `changes.log` to ADDED-only.
- Nonce (`XChaCha20`) is public and included alongside ciphertext.
- The change log reveals dataset size and churn, but not raw IOCs.

## Library Loading

- libsodium is dynamically loaded via `ctypes`. If discovery fails, set `SODIUM_LIBRARY_PATH` to the full shared library path.

