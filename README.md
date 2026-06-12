# newsbeat

`newsbeat` is the native macOS/iOS SwiftUI app. Its separate backend batch
processor, `newsbeat-digest`, collects and ranks AI news, writes a concise
factual summary per selected story, and publishes static JSON, RSS, and
Markdown digests. The app consumes the published JSON, generates LinkedIn and
Instagram drafts on demand, and includes an optional macOS-only local host
mode.

## Component map

The repository contains two independently runnable components:

| Component | Location | Responsibility |
| --- | --- | --- |
| **Native app** | `app/` | macOS/iOS SwiftUI reader, offline cache, copy/share actions |
| **newsbeat-digest processor** | `newsbeat_digest/`, `Dockerfile`, `compose.yaml`, `deploy/` | Python collection, ranking, brief generation, and static publishing |

They communicate only through the generated `feed/digest.json` contract.
`newsbeat-digest` is a batch processor, not an API server. The iOS app is always a
feed-only client; the macOS app can optionally launch the separate Python CLI
while it is open.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the complete repository map,
ownership rules, and data flow.

Phases 1-5 provide a complete Python pipeline: collection, URL and title
deduplication, Anthropic scoring, constrained selection, article extraction,
structured brief generation, and static JSON/RSS/Markdown publishing. arXiv
is present as a disabled v1 stub.

## Implementation status

- [x] Phase 1: Python skeleton, CLI, configuration, and SQLite database
- [x] Phase 2: Hacker News, RSS, Reddit, and disabled arXiv sources
- [x] Phase 3: Dedupe/clustering, scoring, ranking, and selection
- [x] Phase 4: Article extraction and structured briefs
- [x] Phase 5: JSON, RSS, and Markdown publishing
- [x] Phase 6: Native SwiftUI app and optional local macOS host mode
- [x] Phase 7: low-memory Docker deployment on a VPS

The detailed checklist is maintained in `TASKS.md`; the hardening and
on-demand-post-generation follow-up is tracked in `improvement-plan.md`.
Status was last verified on 2026-06-12 with Python 3.14, 57 passing Python
tests, a hardened resource-limited container smoke test (collect exits 0;
static feed returns the security headers with no nginx version), and 11
passing macOS app tests.

## Requirements

- Python 3.14 or newer
- Swift 6.3.2 for the macOS/iOS app phase
- SQLite, included with Python
- Docker Engine with the Compose plugin for VPS deployment

## Backend setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

Configuration is loaded from a root `.env` file when present, while already
exported environment variables take precedence.

`ANTHROPIC_API_KEY` is required when new items need scoring or selected items
need briefs. Do not commit the key.

Optional configuration:

- `AI_DIGEST_PAGES_URL`
- `AI_DIGEST_TIMEZONE`, default `Europe/Tallinn`
- `AI_DIGEST_MAX_ITEMS`, default `8`
- `AI_DIGEST_SCORE_MODEL`, default `claude-haiku-4-5`
- `AI_DIGEST_BRIEF_MODEL`, default `claude-haiku-4-5`
- `AI_DIGEST_DATABASE_PATH`, primarily useful for tests and local isolation

The model defaults were checked against the official Anthropic model
documentation on 2026-06-10. Both remain configurable.

## Backend CLI

All planned commands are available:

```bash
newsbeat-digest collect
newsbeat-digest score
newsbeat-digest brief
newsbeat-digest publish
newsbeat-digest run
newsbeat-digest backfill
```

The equivalent source-tree form is `python -m newsbeat_digest <command>`.

`collect` fetches recent items, normalizes their URLs, and stores new rows.
`score` clusters similar titles, batch-scores representatives, prints a
ranked table, and applies the category, quality, and seven-day redelivery
rules. `brief` fetches article text for selected rows and generates a
schema-constrained **summary** (`what_happened`, `why_it_matters`, `caution`).
LinkedIn and Instagram drafts are no longer pre-generated here; the app
produces them on demand (see [Post generation in the app](#post-generation-in-the-app)).
`publish` writes the rolling JSON feed, RSS 2.0 feed, and current AM/PM
Markdown archive. `run` executes all stages, while `backfill` executes them
with a seven-day collection window. Repeated runs do not duplicate delivered
items.

Scoring uses titles and snippets only. Full article text is fetched only for
selected stories. The deterministic rank is:

```text
rank = relevance * 2 + log(score_hint + 1)
```

Strong EU and Estonia policy signals receive a deterministic +2 relevance
boost, capped at 10. Selection requires relevance of at least 6, limits each
category to two stories, and never pads the digest with weak content.

## Claude API usage and cost

The pipeline keeps LLM usage cheap and predictable (well under $0.10 per run):

- **Scoring** — Haiku, titles and snippets only, batched in groups of 30
  (~2–5 calls per run).
- **Summaries** — Haiku, only for the 6–8 selected stories (~6–8 calls per
  run), with article text truncated to 12k characters.
- **On-demand posts** — Haiku, one call per button press in the app
  (≈ $0.003 each), not part of the pipeline.

Estimated pipeline cost is ≈ $0.05–0.08 per run, so ≈ $0.20–0.32 per day at
four runs. Both pipeline models are configurable via `AI_DIGEST_SCORE_MODEL`
and `AI_DIGEST_BRIEF_MODEL`; the app's post-generation model is set in
**Settings → Post generation**. `temperature=0` is sent for deterministic
Haiku output but is automatically omitted for models that reject it
(Opus 4.7+/Fable), so overriding the model does not break the run.

## Backend sources

Edit `sources.yaml` to enable, disable, or add RSS feeds without changing
Python code. A source failure is logged and does not stop the remaining
sources. Every HTTP request uses a 15-second timeout, a descriptive user
agent, and one retry.

Feeds that could not be verified are disabled with an explanatory YAML
comment.

## Backend tests

```bash
pytest
```

Tests do not make network or LLM calls.

The Phase 3 tests use a fake score client to verify JSON validation, retry,
policy boosts, title clustering, category limits, and the seven-day delivery
guard. A live scoring/briefing run additionally requires a configured
`ANTHROPIC_API_KEY`.

## Shared feed contract

- `feed/digest.json` is the source of truth for the SwiftUI app and
  contains the current digest date and the previous six digest dates.
- `feed/digest.xml` is an RSS 2.0 representation of the same seven-day
  history.
- `digests/YYYY-MM-DD-am.md` and `digests/YYYY-MM-DD-pm.md` are readable
  run archives.

The feed stays at `version: 1`. Each item always carries the summary fields
(`what_happened`, `why_it_matters`, `caution`). The `linkedin_angle` and
`instagram_carousel` keys are now **optional**: new summary-only items omit
them, while legacy items still inside the seven-day window keep their
pre-generated drafts. The app (the only consumer) decodes both shapes.

`feed/`, `digests/`, `data/`, and local `digest.db` are generated runtime
state and are intentionally ignored by Git. Persist or back them up on the
machine that runs `newsbeat-digest`; do not treat them as source files.
SQLite records and Markdown archives are not deleted when items leave the
rolling seven-day app feed.

Set `AI_DIGEST_PAGES_URL` before public publishing. When it is absent, the RSS
channel uses `https://example.invalid/newsbeat` as an explicit placeholder.

## Native app

The XcodeGen project is in `app/Newsbeat`; detailed setup and build commands
are in `app/README.md`. The macOS and iOS targets share a SwiftUI reader that:

- loads `digest.json` from a selected local file or remote URL
- caches the last successful response and opens it offline
- groups stories by digest date and shows full detail views
- generates LinkedIn and Instagram drafts on demand and copies them
- exposes native iOS share sheets

The macOS target also provides a menu bar count and an optional host
coordinator. Host mode:

- it does not move pipeline logic into Swift
- it does not run on iOS
- it does not continue after the macOS app exits
- it prevents overlapping runs and exposes the last run status
- it uses configured local repository and Python executable paths
- it reuses the Anthropic key from the Keychain (shared with post generation)
- it checks the 07:00, 11:00, 16:00, and 21:00 local schedule while open
- it requires the personal macOS target to run without App Sandbox
- it keeps the same `digest.json` contract used by the VPS-hosted feed

### Post generation in the app

LinkedIn and Instagram drafts are generated on demand, not by the pipeline.
In a story's detail view, **Create LinkedIn post** / **Create Instagram post**
calls the Anthropic Messages API directly from the app (raw `URLSession`, no
Swift SDK) using the story's summary, caches the result locally
(`Application Support/newsbeat/posts-cache.json`), and offers **Copy**,
**Regenerate**, and (on iOS) share. Drafts survive relaunch and work the same
on macOS and iOS.

Configure this in **Settings → Post generation**: the Anthropic API key is
stored in the device Keychain (the same entry the macOS host coordinator
reuses) and the model defaults to `claude-haiku-4-5`. The key is never
embedded in source or the feed. The iOS Simulator Keychain is per-simulator,
so re-enter the key there. Generated drafts only see the stored summary (no
full article text), and the prompt forbids inventing facts.

## Backend Docker deployment

The primary hosted deployment is the short-lived `newsbeat-digest` Docker
batch worker on a VPS.
It does not run a Python API or daemon. A systemd timer starts the worker four
times per day, the worker exits after publishing, and a small nginx container
serves the static feed.

Both containers are hardened: read-only root filesystem, a small `/tmp`
tmpfs for the only writable scratch space, `cap_drop: [ALL]`, and
`no-new-privileges`. The worker runs as a non-root UID/GID and writes only to
the three bind mounts; the static feed uses the `nginx-unprivileged` image
(no root master) and serves with `server_tokens off`, `X-Content-Type-Options:
nosniff`, and `Referrer-Policy: no-referrer`. HTTP response bodies are capped
at 5 MB so a hostile or oversized article URL cannot exhaust the 384 MB
worker.

Configured resource ceilings:

- pipeline worker: 384 MB RAM, 0.5 CPU, 128 processes
- static feed server: 48 MB RAM, 0.1 CPU, 32 processes
- combined Newsbeat ceiling while generating: 432 MB RAM and 0.6 CPU
- idle Newsbeat footprint: only the 48 MB-capped static server

The limits do not include the Docker daemon or other VPS workloads. A 2 GB VPS
is recommended when another service such as NadekoBot is running. On a 1 GB
host, configure swap and verify actual headroom with `docker stats`.

### VPS setup

Clone the repository to `/opt/newsbeat-digest`, then prepare persistent directories:

```bash
cd /opt/newsbeat-digest
cp .env.example .env
mkdir -p data feed digests
```

Set `ANTHROPIC_API_KEY`, the public origin in `AI_DIGEST_PAGES_URL`, and the
UID/GID of the account that owns these directories:

```bash
id -u
id -g
```

Store those values as `NEWSBEAT_DIGEST_UID` and `NEWSBEAT_DIGEST_GID` in
`.env`. They default to `1000`, which is the usual first Linux user. If
migrating existing state, copy `digest.db` to `data/digest.db` once before the
first container run.

Restrict the secrets file so only the owner can read it, and never commit it:

```bash
chmod 600 .env
```

The Anthropic key lives only in `.env`, which is loaded into the worker via
`env_file`. It is never baked into an image and never appears in
`compose.yaml`. The published feed is intentionally public, non-secret
content; if you want to gate it, add HTTP basic auth at the reverse proxy
(below) rather than in the worker.

Build and verify the worker and the hardened static feed:

```bash
docker compose build newsbeat-digest
docker compose run --rm newsbeat-digest
docker compose up -d static-feed
curl -sI http://127.0.0.1:8088/feed/digest.json   # 200, security headers, Server: nginx (no version)
```

### Public TLS via a reverse proxy

The feed binds only to `127.0.0.1:8088`. Terminate TLS and serve the public
hostname with a host reverse proxy in front of it. A complete Caddy example
(automatic TLS via Let's Encrypt) — replace the placeholder domain with your
own:

```caddy
news.example.invalid {
    reverse_proxy 127.0.0.1:8088
}
```

The nginx + certbot alternative is equivalent: a `server` block listening on
443 with `proxy_pass http://127.0.0.1:8088;` and a certbot-managed
certificate. Either way, set `AI_DIGEST_PAGES_URL` in `.env` to the public
origin so the RSS channel and any absolute links use it:

```text
https://news.example.invalid/feed/digest.json
```

The systemd unit only invokes `docker compose`; it provides almost no
isolation itself. The container hardening above (read-only rootfs,
`cap_drop`, `no-new-privileges`, non-root user, resource caps) is what
confines the worker and feed server.

### Scheduling

The provided systemd timer runs four times daily — approximately 07:07,
11:07, 16:07, and 21:07 in `Europe/Tallinn` (~4–5 h apart during the day). The
largest gap, 21:07→07:07, is 10 h, still under the 12 h collection lookback,
and canonical-URL dedupe makes overlapping windows free, so no lookback change
is needed. A small randomized delay avoids starting every VPS task on the
exact minute. `flock` prevents overlapping runs.

```bash
sudo cp deploy/systemd/newsbeat-digest.service /etc/systemd/system/
sudo cp deploy/systemd/newsbeat-digest.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now newsbeat-digest.timer
systemctl list-timers newsbeat-digest.timer
```

If the repository is not at `/opt/newsbeat-digest`, edit `WorkingDirectory` in the
installed service. Logs are available with:

```bash
journalctl -u newsbeat-digest.service
```

To change the cadence, edit the `OnCalendar` lines in
`deploy/systemd/newsbeat-digest.timer`, then reinstall and reload:

```bash
sudo cp deploy/systemd/newsbeat-digest.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart newsbeat-digest.timer
```

### Persistence and updates

Persistent state lives outside the worker container:

- `data/digest.db`
- `feed/digest.json` and `feed/digest.xml`
- `digests/*.md`

Back up those paths while `newsbeat-digest.service` is not running. Updating the
application is a pull and image rebuild:

```bash
git pull --ff-only
docker compose build newsbeat-digest
docker compose run --rm newsbeat-digest
```

The VPS systemd timer is the hosted scheduler. It starts the Python module in
the resource-limited Docker worker, which publishes into the persistent host
mounts and exits after each run.

After the first successful VPS run, set the app to **Remote URL**, enter the
public `feed/digest.json` URL, and disable **Local macOS host**. No feed schema
or reader changes are required.

## Current database

The local `digest.db` and hosted `data/digest.db` contain three tables:

- `items` for collected, scored, and delivered stories
- `briefs` for generated content briefs
- `delivered_clusters` for the seven-day redelivery guard

Schema creation is idempotent, and canonical story URLs are unique.
