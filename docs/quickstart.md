---
title: Quickstart
permalink: /quickstart/
---

Two commands: one to start the server with a demo dataset (or your own source file), one to sync and query from the client.

## Server

Start the server with a dataset named `testSource` on `127.0.0.1:8000`:

```
python server_simple.py --host 127.0.0.1 --port 8000 --name testSource --source path/to/source.txt
```

If `--source` is omitted, the script creates `sample_data.txt` with one example IOC and uses it.

## Client

Sync the latest changes and query a single IOC:

```
python client_simple.py <ioc> --server 127.0.0.1:8000 --name testSource
```

Replace `<ioc>` with the exact string used in your source file, e.g. `evil.com`.
