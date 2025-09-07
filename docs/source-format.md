---
title: Source File Format
nav_order: 3
---

Plain text, UTF-8; one item per line in the form:

```
<ioc>,{json_metadata}
```

Examples:

```
evil.com,{"desc":"known bad domain"}
1.2.3.4,{"as":"AS64500","type":"ip"}
44d88612fea8a8f36de82e1278abb02f,{"type":"md5"}
```

Notes:

- The right side must be valid JSON. Use `{}` if you have no metadata.
- Lines without a comma are skipped; blank lines are allowed.
- Proper JSON quoting is required (double quotes, no trailing commas).
