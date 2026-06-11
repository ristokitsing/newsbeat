# CLAUDE.md

## Project: newbseat
newsbeat is a personal AI news curation system.

It has two parts:
1. A Python pipeline that collects AI news, scores it, generates structured content briefs, and publishes static feed files.
2. A native SwiftUI app for macOS and iOS that reads the published JSON feed and makes the briefs easy to read, copy, and share.
This is a single-user personal tool, not a SaaS product. Optimize for reliability, simplicity, low cost, and a workflow the user will actually use daily.
---
## Core user workflow
The main workflow is: text open native app → see latest AI stories → tap story → copy LinkedIn or Instagram draft 
Each selected story should produce:
- what happened
- why it matters
- LinkedIn hook and talking points
- Instagram carousel draft
- one useful caution
- source URL
The shared app is a thin reader. The Python pipeline creates the content. On
macOS only, an optional local host coordinator may launch the separate Python
CLI while the app is running.
---
## Hard non-goals
Do not build these in v1:
- web app
- public website UI
- user accounts
- login/authentication
- admin dashboard
- database server
- backend API server
- vector database
- embeddings
- auto-posting to LinkedIn or Instagram
- in-app editing
- push notifications
- Telegram integration
- Signal integration
- Electron app
- arXiv ingestion beyond a disabled stub
If a feature requires a hosted backend, account system, or always-on process, do not add it.
---
## Architecture
Pipeline: text collect → normalize → dedupe/cluster → score → select → enrich/brief → publish 
Published artifacts:
- text feed/digest.json feed/digest.xml digests/YYYY-MM-DD-am.md digests/YYYY-MM-DD-pm.md 
- feed/digest.json is the source of truth for the SwiftUI app.

Repository ownership:
- `app/` is the native macOS/iOS client.
- `newsbeat_digest/`, `tests/`, `pyproject.toml`, `sources.yaml`, and `profile.md`
  are the `newsbeat-digest` Python batch processor.
- `Dockerfile`, `compose.yaml`, and `deploy/` package and schedule the backend
  processor on the VPS.
- `feed/`, `digests/`, and `data/` are backend-generated output/state.
- `feed/digest.json` is the only runtime contract between backend and app.

The shared reader and iOS app must not run the Python pipeline. A macOS-only
host coordinator may invoke `python -m newsbeat_digest run` as a child process while
the app or menu bar extra is running, then reload the local digest.json. Do not
port pipeline logic into Swift or create a background daemon.
---
## Tech stack
Python:
- Python 3.14+
- SQLite
- local macOS host scheduling first
- low-memory Docker batch worker and VPS systemd timer after the app phase
- Anthropic Python SDK
- minimal dependencies

Allowed Python dependencies: text anthropic python-dotenv httpx feedparser PyYAML beautifulsoup4 lxml pytest 

Optional: text trafilatura 
Only add trafilatura if it clearly improves article extraction.
Do not add Django, Flask, FastAPI, Celery, Postgres, Redis, React, Next.js, Electron, Firebase, Supabase, or analytics.

Docker is used only to package the existing CLI as a short-lived VPS batch
worker. Do not turn it into an API server or always-running Python service.
Cap the worker at 384 MB RAM and 0.5 CPU.

Swift:
- Swift 6.3.2
- SwiftUI
- one shared multiplatform codebase for macOS and iOS
- async/await for network calls
- local cache for offline use
- no backend
- no auth
---
## Secrets and configuration
Never hardcode secrets.
Required environment variable: text ANTHROPIC_API_KEY 
Optional environment variables: text AI_DIGEST_PAGES_URL AI_DIGEST_TIMEZONE AI_DIGEST_MAX_ITEMS AI_DIGEST_SCORE_MODEL AI_DIGEST_BRIEF_MODEL 
Keep Anthropic model names configurable. Before finalizing default model names, check the current official Anthropic documentation. Do not rely on stale model names.
---
## Working style
Before making broad changes, inspect the existing repo structure and current files. Work phase by phase. Do not scaffold the entire repo with incomplete placeholder code. Do not ask the user for architecture decisions that are already specified here. Make reasonable implementation choices, document them, and continue. Prefer a small working vertical slice over a large half-finished scaffold. After each meaningful change, run the relevant verification command.
If something cannot be completed, leave the repo in a runnable state and document the limitation.
---
## Build order
Follow this order unless the user explicitly asks otherwise.
### Phase 1: Python skeleton and database
Create the package, CLI, SQLite initialization, config loading, models, and basic tests.
Required CLI commands: bash python -m newsbeat_digest collect python -m newsbeat_digest score python -m newsbeat_digest brief python -m newsbeat_digest publish python -m newsbeat_digest run python -m newsbeat_digest backfill 
At the end of this phase, these must run: bash python -m newsbeat_digest collect pytest 
It is acceptable if collect prints no items before sources are implemented, but it must not crash.
---
### Phase 2: Sources
Implement source interface and these sources:
- Hacker News via Algolia API
- RSS via sources.yaml
- Reddit JSON endpoints
- disabled arXiv stub

All sources must:
- use a 15 second timeout
- retry once
- set a proper User-Agent
- log failures
- never crash the whole run

A failed source should not stop other sources.
---
### Phase 3: Normalize, dedupe, score, select
Implement:
- URL canonicalization
- SQLite uniqueness by canonical URL
- simple title similarity dedupe
- optional LLM clustering
- LLM scoring
- deterministic EU/Estonia policy boost
- selection rules

Selection rules:
- select 6–8 items per run
- max 2 per category
- do not redeliver the same cluster within 7 days
- do not deliver an item already marked delivered
- prefer fewer strong stories over weak filler

At the end of this phase: bash python -m newsbeat_digest score 
must print a ranked table.
---
### Phase 4: Article extraction and briefs
Implement:
- source article fetching
- article text extraction
- fallback to title/snippet if extraction fails
- structured brief generation
- JSON validation
- DB persistence

Brief output must contain:
json {   "what_happened": "Two factual sentences.",   "why_it_matters": "Two to three useful sentences.",   "linkedin_angle": {     "hook": "One hook line.",     "points": ["Point 1", "Point 2", "Point 3"]   },   "instagram_carousel": {     "slides": ["Slide 1", "Slide 2", "Slide 3", "Slide 4"],     "cta": "CTA"   },   "caution": "One useful uncertainty or limitation." } 
Do not fabricate facts. If full article text is unavailable, mention that in caution.
---
### Phase 5: Publishing
Write: text feed/digest.json feed/digest.xml digests/YYYY-MM-DD-am.md digests/YYYY-MM-DD-pm.md 
Requirements:
- digest.json is valid JSON
- digest.json contains approximately the last 30 days of delivered items
- newest items first
- no duplicate delivered items
- RSS is valid RSS 2.0
- Markdown archive is readable
At the end of this phase: bash python -m newsbeat_digest run 
must create a complete digest. Running the same command twice must not duplicate delivered feed items.
---
### Phase 6: SwiftUI app and local macOS host
Create the native app in /app.
The app must:
- build for macOS
- build for iOS
- fetch digest.json
- cache the last successful response
- work offline from cache
- group items by digest date
- show list and detail views
- show category tag, source, title, and brief sections
- open original source URL
- copy LinkedIn angle
- copy Instagram carousel
- support iOS share sheet
- provide macOS menu bar extra showing today’s count
The app must not require a backend.

The macOS target may also provide optional local host mode. It must:
- run the existing CLI when the digest is stale and on a timer while the app is running
- avoid overlapping runs
- expose run status and refresh the feed after success
- read local feed/digest.json directly
- keep credentials in Keychain or the existing process environment
- use configurable repository and Python executable paths

The shared reader and iOS target remain feed-only. Closing the macOS app stops
local scheduling. The personal macOS target may disable App Sandbox to launch
the configured Python process; document that limitation.
---
### Phase 7: Docker VPS deployment
Create: text Dockerfile compose.yaml deploy/nginx.conf deploy/systemd/newsbeat-digest.service deploy/systemd/newsbeat-digest.timer

The systemd timer runs the container two or three times daily. Use persistent
host mounts for `data/digest.db`, `feed/`, and `digests/`, and use a lock to
prevent overlap. The static feed server may remain running but the Python
worker must exit after each digest.

Never hardcode `ANTHROPIC_API_KEY`.
---
## Python code standards
Use type hints. Use dataclasses or typed models where useful. Keep modules small and focused. Prefer readable explicit code over clever abstractions. Use pathlib for paths. Use UTC internally where practical, but publish digest dates in Europe/Tallinn. Use parameterized SQL queries. Do not call live external APIs in unit tests. Do not call Anthropic in tests. Mock network and LLM responses.
---
## Swift code standards
Use SwiftUI. Use async/await. Use Codable models matching feed/digest.json. Use a simple app-level view model. Use local file caching or another simple native cache.
Use platform conditionals where needed: swift #if os(macOS) #endif  #if os(iOS) #endif
Do not add third-party Swift packages unless clearly necessary.
---
## LLM usage rules
Keep LLM usage cheap and predictable. The full digest run should usually cost well under $0.10.

Cost controls:
- score titles and snippets only
- batch scoring in groups of about 30
- fetch full article text only for selected items
- generate briefs only for selected items
- select 6–8 items per run
- truncate article text before sending to the LLM
- validate JSON
- retry malformed LLM responses once only
Scoring model and brief model must be configurable.
---
## Source rules
Initial sources:
- Hacker News
- configured RSS feeds
- Reddit: r/LocalLLaMA, r/MachineLearning
- disabled arXiv stub
RSS feeds must be editable in sources.yaml. If a feed URL is broken or unavailable, disable it in sources.yaml and add a short comment. Adding a new RSS feed should not require code changes.
---
## EU and Estonia relevance
The user is based in Estonia. Boost AI policy/regulation news related to:
- EU AI Act
- European Commission
- European Union
- EU AI Office
- Estonia
- Estonian public sector
- e-Estonia
- Baltic AI policy, if directly relevant
Apply this both in the scoring prompt and with a deterministic boost in code.
---
## Error handling
The pipeline must be resilient. A failed source logs and continues. A malformed LLM response retries once. If retry fails, skip the affected items and continue. Article extraction failure should not block brief generation. Publishing should never write invalid JSON. Running twice should not duplicate delivered items.
---
## Tests
Use pytest. Minimum tests: text tests/test_url_normalize.py tests/test_feed_json.py tests/test_selection.py tests/test_rss.py 
Tests should verify:
- tracking params are stripped from URLs
- duplicate canonical URLs are not inserted twice
- selection respects max 2 per category
- delivered clusters are not redelivered within 7 days
- digest.json contains required fields
- RSS XML is generated
No live Anthropic calls in tests. No live network calls in unit tests.
---
## Verification commands
Use these during implementation: bash python -m newsbeat_digest collect python -m newsbeat_digest score python -m newsbeat_digest run pytest 
Before claiming the Python pipeline is done, verify: text feed/digest.json exists feed/digest.xml exists at least one digests/*.md file exists running twice does not duplicate delivered feed items 
Before claiming the app is done, verify: text macOS build succeeds iOS build succeeds app loads local digest.json app loads cached data offline copy LinkedIn angle works copy Instagram carousel works macOS host mode runs the CLI and refreshes the feed iOS does not launch the pipeline 
---
## Documentation requirements
Update README.md when setup or usage changes.
The root README must explain:
- what the project does
- how to install dependencies
- required secrets
- how to run locally
- how to configure sources
- how to configure profile
- how macOS local host mode finds and runs the Python CLI
- how to disable local host scheduling
- how the Docker worker, systemd timer, resource limits, and persistence work
- how to expose the static feed through the VPS reverse proxy
The app README must explain:
- how to open the Xcode project
- where to set the feed URL
- how to build for macOS
- how to build for iOS
- how offline cache works
- known limitations
---
## Git rules
Do not commit secrets. Do not commit .env.
Do commit source configuration such as `sources.yaml` and `profile.md`.
Do not commit generated runtime state: `digest.db`, `data/`, `feed/`, or
`digests/`.
Persist `data/digest.db` on the VPS because the scheduled pipeline needs
dedupe/delivery state. The manual Actions fallback creates temporary runtime
state and publishes generated files directly without committing them.
Keep generated output deterministic where practical.
---
## When blocked
If a source is unavailable, disable it and document why.
If an API response shape changed, make the parser defensive and add a test fixture.
If the LLM response is malformed, improve validation and fallback behavior.
If the public VPS URL is unknown, use a documented placeholder.
If Xcode project setup requires manual signing, document the steps instead of inventing credentials.
Do not stop to ask about choices already defined in this file.
---
## Definition of done
The project is complete when:
- the Python pipeline runs locally
- the pipeline publishes valid JSON, RSS, and Markdown archive files
- duplicate delivery is prevented
- the macOS app can optionally schedule the local pipeline while it is running
- the SwiftUI app builds for macOS and iOS
- the app reads the feed and works offline from cache
- the app supports one-tap copy for LinkedIn and Instagram drafts
- the VPS container runs the pipeline on schedule within its resource cap
- the VPS can serve the static feed files
- setup is documented clearly
