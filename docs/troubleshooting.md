---
title: Troubleshooting
nav_order: 10
---

# Troubleshooting

- libsodium not found: Install via your package manager or set `SODIUM_LIBRARY_PATH` to the shared library path.
- Permission errors writing key: Ensure the process can write to `server/secrets/<data_name>/`.
- Port already in use: Start the server on a different bind, e.g., `127.0.0.1:8001`.
- Query yields no match: Confirm the IOC string exactly matches the source file entry and that you have synced the latest changes.
- After rekey, deltas fail: Run `client reset_data` to force a full fetch and rebuild local state.

