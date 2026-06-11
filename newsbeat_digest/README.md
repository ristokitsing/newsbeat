# newsbeat-digest

This directory contains the Python import package for the `newsbeat-digest`
batch processor. The installed CLI is `newsbeat-digest`; it can also run from
the source tree as `python -m newsbeat_digest`.

```text
sources/    collect external news
pipeline/   normalize, deduplicate, score, select, extract, and brief
publish/    generate JSON, RSS, and Markdown output
db.py       persist processor state in SQLite
config.py   load backend environment configuration
__main__.py expose the batch CLI
```

This package does not contain the `newsbeat` app UI or an HTTP API. Its
interface to the native app is the generated root-level `feed/digest.json`.
Generated feeds, archives, and SQLite files are ignored by Git. See
[`ARCHITECTURE.md`](../ARCHITECTURE.md) for the full repository boundary.
