## Project: newsbeat

This repository contains a personal AI news curation system.

The goal is to build a low-cost, single-user pipeline that collects AI news, ranks it, generates reusable social media content briefs, publishes static feed files, and provides a native SwiftUI reader app for macOS and iOS.

This is not a public SaaS product. Do not build accounts, authentication, admin panels, dashboards, or a web app.

---

## Core product idea

The user wants to open a native macOS/iOS app and quickly see the most relevant AI news from the latest digest.

For each story, the system should provide:

- What happened
- Why it matters
- A LinkedIn angle
- Instagram carousel draft text
- One caution or uncertainty
- Source link

The most important UX is:

text open app → see today's AI stories → tap story → copy LinkedIn or Instagram draft 

Optimize everything around that.

---

## Architecture

There are two parts.

### Repository ownership

- `app/` is the native macOS/iOS client.
- `newsbeat_digest/`, `tests/`, `pyproject.toml`, `sources.yaml`, and `profile.md`
  are the Python backend processor.
- `Dockerfile`, `compose.yaml`, and `deploy/` package and schedule the backend
  processor on the VPS.
- `feed/`, `digests/`, and `data/` are backend-generated output/state, not app
  source.
- `feed/digest.json` is the only runtime contract between backend and app.

### 1. `newsbeat-digest` backend processor

The pipeline:

text collect → normalize → dedupe/cluster → score → select → enrich/brief → publish 

It publishes:

text feed/digest.json feed/digest.xml digests/YYYY-MM-DD-am.md digests/YYYY-MM-DD-pm.md 

The JSON feed is the source of truth for the app.

### 2. Native SwiftUI app

The app lives in /app.

It is a native SwiftUI multiplatform app for:

- macOS
- iOS

The shared reader and the iOS app only read published digest.json files.

The macOS app may act as an optional local host. For independent hosted
operation, a low-memory Docker worker runs the `newsbeat-digest` processor as
a short-lived VPS batch job and publishes static files for the reader.

Do not port pipeline logic to Swift. The Python CLI remains a separate,
independently runnable component. Closing the macOS app stops local scheduling.

---

## Hard constraints

Use Python 3.14+.

Use SQLite only.

Use the macOS app as the optional local scheduler and a VPS systemd timer as
the primary hosted scheduler.

Use local published files for macOS host mode and a small static web server for
VPS-hosted files.

The VPS worker must remain a batch process, use no more than 384 MB RAM and 0.5
CPU, prevent overlapping runs, and persist SQLite/feed data outside the
container. It should run two or three times daily and exit after each run.

Use the Anthropic Python SDK for LLM calls.

Keep dependencies minimal.

Preferred Python dependencies:

text anthropic python-dotenv httpx feedparser PyYAML beautifulsoup4 lxml pytest 

Optional dependency:

text trafilatura 

Only add trafilatura if article extraction is clearly better with it.

Do not use:

text Django Flask FastAPI Celery Postgres Redis Electron React Next.js vector databases embeddings 

Do not add Telegram, Signal, push notifications, in-app editing, or auto-posting in v1.

---

## Secrets

Never hardcode secrets.

Required environment variable:

text ANTHROPIC_API_KEY 

Optional environment variables:

text AI_DIGEST_PAGES_URL AI_DIGEST_TIMEZONE AI_DIGEST_MAX_ITEMS AI_DIGEST_SCORE_MODEL AI_DIGEST_BRIEF_MODEL 

Model names should be configurable.

Before finalizing Anthropic model names, check the current official Anthropic docs. Do not rely on stale model names.

---

## Important implementation rule

Do not scaffold the whole project with incomplete placeholders.

Work phase by phase.

Each phase must be runnable before moving to the next phase.

Prefer a smaller working system over a large half-finished system.

---

## Build order

Implement in this order.

### Phase 1: Skeleton, CLI, database

Create:

text newsbeat_digest/ newsbeat_digest/__main__.py newsbeat_digest/db.py newsbeat_digest/models.py newsbeat_digest/config.py tests/ pyproject.toml README.md 

Required CLI commands:

bash python -m newsbeat_digest collect python -m newsbeat_digest score python -m newsbeat_digest brief python -m newsbeat_digest publish python -m newsbeat_digest run python -m newsbeat_digest backfill 

At the end of this phase:

bash python -m newsbeat_digest collect pytest 

must run without crashing.

---

### Phase 2: Sources

Implement sources behind a common interface.

Sources:

- Hacker News via Algolia API
- RSS via sources.yaml
- Reddit JSON endpoints
- arXiv stub, disabled in v1

A failed source must not crash the run.

All HTTP calls must have:

- 15 second timeout
- retry once
- proper User-Agent
- logging on failure

At the end of this phase:

bash python -m newsbeat_digest collect 

must fetch and store real items.

---

### Phase 3: Normalize, dedupe, score, select

Implement:

- URL canonicalization
- SQLite uniqueness by canonical URL
- simple title-similarity dedupe
- optional LLM clustering
- LLM scoring
- deterministic EU/Estonia policy boost
- selection rules

Selection rules:

- 6–8 items per run
- max 2 per category
- do not redeliver same cluster within 7 days
- do not pad with weak content
- prefer fewer strong stories over many mediocre ones

At the end of this phase:

bash python -m newsbeat_digest score 

must print a ranked table.

---

### Phase 4: Article extraction and briefs

Implement:

- article fetching
- article text extraction
- fallback to title/snippet if extraction fails
- structured brief generation
- JSON validation
- DB persistence

Brief JSON shape:

json {   "what_happened": "Two factual sentences.",   "why_it_matters": "Two to three useful sentences.",   "linkedin_angle": {     "hook": "One hook line.",     "points": [       "Point 1",       "Point 2",       "Point 3"     ]   },   "instagram_carousel": {     "slides": [       "Slide 1",       "Slide 2",       "Slide 3",       "Slide 4"     ],     "cta": "CTA"   },   "caution": "One useful uncertainty or limitation." } 

Do not fabricate facts.

If source text is weak or unavailable, say so in caution.

---

### Phase 5: Publishing

Implement:

text feed/digest.json feed/digest.xml digests/YYYY-MM-DD-am.md digests/YYYY-MM-DD-pm.md 

The JSON feed must be valid and should contain approximately the last 30 days of delivered items.

RSS must be valid RSS 2.0.

At the end of this phase:

bash python -m newsbeat_digest run 

must create a complete digest.

Running the same command twice must not create duplicate delivered items.

---

### Phase 6: SwiftUI app and local macOS host

Create the app in /app.

The app must:

- build for macOS
- build for iOS
- load digest.json from a local file or remote URL
- cache the last successful response
- work offline from cache
- show items grouped by digest date
- show detail view
- copy LinkedIn angle
- copy Instagram carousel
- open source article URL
- provide iOS share sheet
- provide macOS menu bar extra with today's count

The app must not require a backend.

The shared reader and iOS target must not run the Python pipeline.

The macOS target may provide an optional host mode that:

- runs once on launch when the local digest is stale
- schedules refreshes only while the app or menu bar extra is running
- launches `python -m newsbeat_digest run` as a child process
- prevents overlapping pipeline runs
- reports running, success, and failure status
- refreshes the reader after a successful run
- reads the local feed/digest.json without requiring a local HTTP server
- stores the Anthropic API key in Keychain or uses the existing environment
- uses configurable repository and Python executable paths

Host mode must be disabled or clearly unavailable on iOS. It is an interim
on-prem scheduler, not a background daemon, embedded Python implementation, or
backend service. The personal macOS target may disable App Sandbox so it can
launch the configured local Python process; document this limitation clearly.

---

### Phase 7: Docker VPS deployment

Create:

text Dockerfile compose.yaml deploy/nginx.conf deploy/systemd/newsbeat-digest.service deploy/systemd/newsbeat-digest.timer

The deployment should:

1. Build a minimal Python 3.14 image.
2. Run `python -m newsbeat_digest run` as a short-lived container.
3. Cap the worker at 384 MB RAM and 0.5 CPU.
4. Persist SQLite, feed files, and Markdown archives on the host.
5. Use a systemd timer for two or three runs per day.
6. Use a lock to prevent overlapping runs.
7. Serve only static `feed/` and `digests/` files through the existing reverse proxy.

Files to persist:

text data/digest.db feed/digest.json feed/digest.xml digests/*.md 

Moving from local host mode to the VPS should require changing the feed source
and disabling local scheduling, not changing the feed schema or reader UI.

The root `digest.db`, `data/`, `feed/`, and `digests/` paths are generated
runtime state. Keep them ignored by Git and persist the VPS paths outside the
container.

---

## Python code style

Use type hints.

Prefer dataclasses or typed dictionaries for simple models.

Keep functions small.

Avoid clever abstractions.

Prefer readable, explicit code.

Use structured logging where helpful.

Do not silently swallow errors unless the caller can continue safely.

Do not introduce a dependency without a clear reason.

---

## Swift code style

Use Swift 6.3.2 and SwiftUI.

Use async/await for fetching.

Use Codable models matching digest.json.

Use a simple app-level view model.

Cache JSON locally using file storage or UserDefaults if appropriate.

Use platform checks where needed:

swift #if os(macOS) #endif  #if os(iOS) #endif 

Keep macOS and iOS in one shared codebase where practical.

Do not add Firebase, Supabase, analytics, or accounts.

---

## LLM cost discipline

The full run should usually cost well under $0.10.

To control cost:

- Score only titles/snippets.
- Batch scoring.
- Fetch full article text only for selected items.
- Brief only selected items.
- Keep selected items to 6–8.
- Truncate article text before sending to LLM.
- Validate JSON and retry only once.

Do not call the LLM in tests.

Mock LLM responses in tests.

---

## Error handling

The pipeline should be resilient.

A failed source should log and continue.

A malformed LLM response should retry once.

If the retry fails, skip those items and continue.

Article extraction failure should not block brief generation.

Publishing should not produce invalid JSON.

Running twice should not create duplicate delivered items.

---

## Tests

Use pytest.

Minimum tests:

text tests/test_url_normalize.py tests/test_feed_json.py tests/test_selection.py tests/test_rss.py 

Tests should verify:

- tracking params are stripped from URLs
- duplicate URLs are not inserted twice
- selection respects max 2 per category
- delivered clusters are not redelivered within 7 days
- digest.json has required fields
- RSS XML is generated

No live network calls in tests unless explicitly marked as integration tests.

No live Anthropic calls in tests.

---

## Acceptance checks before finishing

Before claiming the task is done, run:

bash python -m newsbeat_digest collect python -m newsbeat_digest score python -m newsbeat_digest run pytest 

Also validate `docker compose config` and build the worker image when Docker is
available.

Also verify:

text feed/digest.json exists feed/digest.xml exists at least one digests/*.md file exists running twice does not duplicate delivered feed items 

For the app, verify:

text macOS build succeeds iOS build succeeds app can load local digest.json app can load cached data offline copy LinkedIn angle works copy Instagram carousel works macOS host mode can run the CLI and refresh the feed iOS never launches the pipeline 

---

## Handling uncertainty

If a feed URL is unavailable or broken, do not block the project.

Disable that feed in sources.yaml and add a comment explaining why.

If Anthropic model names are uncertain, check official docs and keep them configurable.

If the public VPS URL is unknown, use a clearly documented placeholder and
explain where the user should replace it.

If a feature would require a backend, server, account system, or heavy dependency, do not implement it in v1.

---

## Product priorities

Priority order:

1. Reliable pipeline
2. Valid JSON feed
3. Useful brief quality
4. Native app reading/copying experience
5. RSS fallback
6. Nice UI polish

Do not optimize for source quantity at the expense of digest quality.

Do not make the app complex.

Do not build features that make posting automatic. The user wants copy-ready drafts, not auto-posting.

---

## Definition of done

The project is done when:

- The Python pipeline can run locally.
- The macOS app can optionally schedule the local pipeline while it is running.
- The SwiftUI app builds for macOS and iOS.
- The app reads the feed and works offline from cache.
- The app supports one-tap copy for LinkedIn and Instagram drafts.
- The VPS container can run it on schedule within the configured resource cap.
- Output is persisted and published.
- The JSON feed is stable and documented.
- The RSS feed works.
- README files explain setup clearly.
