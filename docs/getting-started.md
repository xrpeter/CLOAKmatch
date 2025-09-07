---
title: Getting Started
permalink: /getting-started/
---

# Getting Started

## Prerequisites

- Python 3.11+
- Virtual environment recommended
- libsodium installed and discoverable by the dynamic loader

Install libsodium:

- macOS: `brew install libsodium`
- Debian/Ubuntu: `sudo apt-get install libsodium23 libsodium-dev`
- Custom path: set `SODIUM_LIBRARY_PATH` to the full path of the libsodium shared library

Create and activate a virtualenv, then install Python deps:

```
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run the Demo

Server (terminal A):

```
python server_simple.py --host 127.0.0.1 --port 8000 --name testSource
```

Client (terminal B):

```
python client_simple.py evil.com --server 127.0.0.1:8000 --name testSource
```

Expected output includes a PRF and decrypted metadata when the IOC exists.
