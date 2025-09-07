---
title: FAQ
permalink: /faq/
---

# FAQ

- What does “OPRF” mean?
  - Oblivious Pseudo-Random Function: the server helps compute a PRF on a client input without learning the input.

- Do I have to use the simple scripts?
  - No. They are convenience wrappers around the CLI. You can call `server.cli` and `client.cli` directly.

- Can I rotate keys?
  - Yes. Use `python -m server.cli rekey <data_name> <source.txt>`. Clients should run `reset_data` to refresh after rekey.

- What metadata can I store?
  - Anything JSON-serializable as a string blob. The server treats it as opaque bytes for encryption.

- Is the change log confidential?
  - It hides IOCs but reveals volume and churn over time. Consider operational privacy requirements before publishing logs broadly.
