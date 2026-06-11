# Assignment: Build “newsbeat” — Personal AI News Curation Pipeline + Native macOS/iOS Reader

## 1. Project goal

Build a personal, single-user AI news curation system.

The system should:

- Collect AI-related news from multiple sources.
- Deduplicate and rank the stories.
- Use an LLM to select the most relevant items.
- Generate copy-ready content briefs for LinkedIn posts and Instagram carousel drafts.
- Publish a structured JSON feed and RSS feed.
- Provide a native SwiftUI app for macOS and iOS that reads the JSON feed and makes the briefs easy to read and copy.

This is not a public web app. There are no accounts, no login, no database server, no web backend, and no admin dashboard.

The core purpose is:

> “Every morning and afternoon, I want one clean digest of important AI news, with each story turned into a practical content brief that I can quickly reuse for LinkedIn and Instagram.”

The user is based in Estonia, so EU and Estonia-relevant AI policy/regulation news should receive a relevance boost.

---

## 2. High-level architecture

The project has two main parts:

text Python pipeline: collect → normalize → dedupe/cluster → score → select → enrich/brief → publish JSON/RSS/archive  Native app: fetch local or remote digest.json → cache locally → show grouped digest → copy LinkedIn/Instagram drafts 

Initially, the macOS app may launch the separate Python CLI while the app or
menu bar extra is running. For independent hosted operation, a low-memory
Docker worker runs the same CLI two or three times daily on a VPS and publishes
the same static files.

The shared SwiftUI reader and iOS target are thin native clients that only read
digest.json. A macOS-only host coordinator may invoke the existing CLI as a
child process; pipeline logic must remain in Python.

---

## 3. Non-goals for v1

Do not build:

- A web app
- User accounts
- Login/auth
- A backend API
- A database server
- A vector database
- Embeddings
- Auto-posting to LinkedIn or Instagram
- In-app editing
- Push notifications
- Telegram integration
- Signal integration
- Electron app
- arXiv ingestion

The v1 app is read-only plus copy/share actions.

---

## 4. Tech constraints

### newsbeat-digest processor

Use:

- Python 3.14+
- SQLite
- local macOS host scheduling first
- Docker batch worker and VPS systemd timer after the app phase
- Anthropic Python SDK
- Minimal dependencies

Preferred dependencies:

text anthropic python-dotenv httpx feedparser PyYAML beautifulsoup4 lxml pytest 

Optional:

text trafilatura 

Use trafilatura only if it materially improves article text extraction without making the project fragile.

Do not use:

- Django
- Flask
- FastAPI
- Celery
- Postgres
- Redis
- Heavy frontend frameworks

Docker is limited to packaging the existing CLI as a short-lived worker. Do
not add an API framework or continuously running Python process.

### SwiftUI app

Build a native SwiftUI multiplatform app in /app.

Targets:

- macOS
- iOS

Use Swift 6.3.2.

One shared SwiftUI codebase as much as possible.

The app should:

- Read digest.json from a configured local file or remote URL.
- Cache the last successful response locally.
- Open offline using cached data.
- Show digest items grouped by digest date.
- Provide detail views.
- Provide one-tap copy buttons for LinkedIn and Instagram drafts.
- On macOS, include a menu bar extra showing today’s item count.
- On macOS, optionally run the separate newsbeat_digest CLI while the app is active.
- On iOS, include share sheet support.

---

## 5. Repository layout

Create this structure:

text newsbeat/ ├── newsbeat_digest/ ├── app/ │   ├── README.md │   └── Newsbeat/ │       ├── src/shared/ │       ├── src/macOS/ │       ├── src/iOS/ │       ├── tests/macOS/ │       └── project.yml ├── feed/ ├── digests/ ├── tests/ ├── sources.yaml ├── profile.md ├── digest.db ├── pyproject.toml └── README.md

---

## 6. CLI requirements

The pipeline must support these commands:

bash python -m newsbeat_digest collect python -m newsbeat_digest score python -m newsbeat_digest brief python -m newsbeat_digest publish python -m newsbeat_digest run python -m newsbeat_digest backfill 

Behavior:

### collect

Fetches fresh items from all enabled sources, normalizes them, stores them in SQLite, and prints a table of newly inserted items.

### score

Scores unscored/new items using the LLM and prints a ranked table.

### brief

Selects the top items, fetches article text, generates structured briefs, and stores them.

### publish

Writes:

text feed/digest.json feed/digest.xml digests/YYYY-MM-DD-am.md digests/YYYY-MM-DD-pm.md 

### run

Runs the full pipeline:

text collect → dedupe/cluster → score → select → brief → publish 

### backfill

Useful for local testing. It should collect and process a wider time window, but still avoid duplicate feed entries.

---

## 7. Configuration

### .env

Required:

text ANTHROPIC_API_KEY= 

Optional:

text AI_DIGEST_PAGES_URL= AI_DIGEST_TIMEZONE=Europe/Tallinn AI_DIGEST_MAX_ITEMS=8 

Do not hardcode secrets.

### sources.yaml

RSS feeds should be configurable without code changes.

Initial structure:

yaml rss:   - name: Anthropic News     url: "IMPLEMENT_WORKING_FEED_URL"     enabled: true    - name: OpenAI Blog     url: "IMPLEMENT_WORKING_FEED_URL"     enabled: true    - name: Google DeepMind Blog     url: "IMPLEMENT_WORKING_FEED_URL"     enabled: true    - name: Meta AI Blog     url: "IMPLEMENT_WORKING_FEED_URL"     enabled: true    - name: Mistral News     url: "IMPLEMENT_WORKING_FEED_URL"     enabled: true    - name: Hugging Face Blog     url: "IMPLEMENT_WORKING_FEED_URL"     enabled: true    - name: Import AI     url: "IMPLEMENT_WORKING_FEED_URL"     enabled: true    - name: The Batch     url: "IMPLEMENT_WORKING_FEED_URL"     enabled: true    - name: Ars Technica AI     url: "IMPLEMENT_WORKING_FEED_URL"     enabled: true    - name: The Verge AI     url: "IMPLEMENT_WORKING_FEED_URL"     enabled: true    - name: EU AI / Digital Strategy     url: "IMPLEMENT_WORKING_FEED_URL_IF_AVAILABLE"     enabled: true  reddit:   - subreddit: LocalLLaMA     enabled: true     min_score: 100    - subreddit: MachineLearning     enabled: true     min_score: 100  hackernews:   enabled: true   min_points_default: 30   min_points_strong_keyword: 10 

During implementation, find currently working RSS feed URLs. If a feed cannot be found, leave it disabled with a comment in sources.yaml.

### profile.md

Create this editable profile file:

md # newsbeat Curation Profile  I am interested in:  - AI models and capability changes. - New model releases from major labs. - Practical tools for developers, creators, and small teams. - Research breakthroughs that clearly change what is possible. - AI policy and regulation, especially EU and Estonia-relevant news. - Major business moves only when they affect the AI ecosystem.  Boost:  - EU AI Act - European Commission AI policy - Estonia-related AI policy or adoption - Practical use cases for creators, developers, accountants, or small businesses  Deprioritize:  - Stock price noise - Generic AI doom essays without new facts - Repetitive opinion pieces - Listicles - Thin product announcements - Incremental research papers without clear practical importance 

The scoring prompt should read this file.

---

## 8. Data model

Use SQLite file:

text digest.db 

Create tables using plain SQL migrations or idempotent initialization code.

### items

Fields:

text id INTEGER PRIMARY KEY url TEXT NOT NULL canonical_url TEXT NOT NULL UNIQUE title TEXT NOT NULL source TEXT NOT NULL snippet TEXT published_at TEXT score_hint REAL DEFAULT 0 first_seen_at TEXT NOT NULL cluster_id TEXT cluster_representative INTEGER DEFAULT 1 llm_score REAL llm_category TEXT llm_reason TEXT status TEXT NOT NULL DEFAULT 'new' article_text TEXT created_at TEXT NOT NULL updated_at TEXT NOT NULL 

Allowed statuses:

text new scored selected rejected briefed delivered 

### briefs

Fields:

text id INTEGER PRIMARY KEY item_id INTEGER NOT NULL what_happened TEXT NOT NULL why_it_matters TEXT NOT NULL linkedin_hook TEXT NOT NULL linkedin_points_json TEXT NOT NULL instagram_slides_json TEXT NOT NULL instagram_cta TEXT NOT NULL caution TEXT NOT NULL digest_date TEXT NOT NULL digest_slot TEXT NOT NULL created_at TEXT NOT NULL FOREIGN KEY(item_id) REFERENCES items(id) 

### delivered_clusters

Fields:

text id INTEGER PRIMARY KEY cluster_id TEXT NOT NULL delivered_at TEXT NOT NULL item_id INTEGER NOT NULL 

---

## 9. Collection sources

All sources must implement a common interface.

python @dataclass class RawItem:     title: str     url: str     published_at: str | None     source: str     snippet: str | None = None     score_hint: float = 0 

Base interface:

python class Source:     name: str      def fetch(self) -> list[RawItem]:         ... 

All HTTP calls:

- 15 second timeout
- retry once
- proper User-Agent
- log failures
- never crash the full run because one source failed

### Hacker News

Use Algolia API:

text https://hn.algolia.com/api/v1/search_by_date 

Query AI-related terms from the last 12 hours.

Keywords:

text claude anthropic openai gpt llm gemini deepmind mistral llama diffusion transformer ai act ai regulation agents rag fine-tun inference 

Keep:

- items with points >= 30
- or strong keyword matches with points >= 10

Store HN points as score_hint.

Prefer original story URL over HN item URL when available.

### RSS

Use feedparser.

Feeds are configured in sources.yaml.

If a feed fails, log and continue.

### Reddit

Use public JSON endpoints with no auth.

Example:

text https://www.reddit.com/r/LocalLLaMA/top.json?t=day https://www.reddit.com/r/MachineLearning/top.json?t=day 

Requirements:

- Set a proper User-Agent.
- Keep posts from approximately the last 12 hours where possible.
- Apply subreddit score thresholds from sources.yaml.
- Store Reddit score as score_hint.

### arXiv

Create a stub source but keep disabled in v1.

---

## 10. Normalization and dedupe

### URL canonicalization

Implement:

- Strip common tracking params:
  - utm_*
  - fbclid
  - gclid
  - mc_cid
  - mc_eid
  - ref
- Normalize scheme and host.
- Remove trailing slashes where safe.
- Resolve obvious HN links to original article URLs.
- Keep original URL as url.
- Store normalized URL as canonical_url.

### Exact dedupe

SQLite UNIQUE(canonical_url) is the first dedupe layer.

### Fuzzy dedupe / clustering

For v1, implement this in two layers:

1. Simple title similarity heuristic.
2. Optional LLM clustering for new items in the current run.

Do not make clustering fragile. If the LLM clustering call fails, fall back to title similarity and continue.

The cluster ID can be a stable hash of the representative title or canonical URL.

Keep the highest score_hint item as the cluster representative.

---

## 11. LLM usage

Use the Anthropic Python SDK.

During implementation, check the official Anthropic docs for current model names and API usage. Do not rely on old model names.

Use two model tiers:

1. A cheap/small model for classification, scoring, and clustering.
2. A mid-tier model for writing briefs.

Expose model names in config constants or environment variables so they can be changed easily.

Suggested env vars:

text AI_DIGEST_SCORE_MODEL= AI_DIGEST_BRIEF_MODEL= 

### Cost discipline

The full twice-daily run should usually cost well under $0.10.

To keep costs down:

- Score using titles and snippets only.
- Batch scoring in groups of about 30 items.
- Only fetch full article text for selected items.
- Only generate briefs for selected items.
- Limit final selected items to 6–8 per run.

---

## 12. Scoring

Batch score new cluster representatives.

Prompt input:

- item ID
- title
- source
- snippet
- score_hint
- published_at
- interest profile from profile.md

The LLM must return strict JSON:

json [   {     "id": 123,     "category": "models",     "relevance": 8,     "reason": "Major model release with practical developer impact."   } ] 

Allowed categories:

text models tools research policy business other 

Validation:

- JSON must parse.
- Every item must have an ID.
- Relevance must be 0–10.
- Unknown categories should become other.
- Retry once if parsing fails.
- If still invalid, mark those items as unscored and continue.

Final ranking formula:

text rank = llm_relevance * 2 + log(score_hint + 1) 

Policy boost:

- The prompt should instruct the LLM to boost EU/Estonia-relevant AI policy.
- Additionally, apply a deterministic +2 relevance boost before ranking if title/snippet/source contains strong EU/Estonia policy signals such as:
  - EU AI Act
  - European Commission
  - Estonia
  - Estonian
  - e-Estonia
  - European Union
  - Brussels
  - AI Office

Cap final relevance at 10.

---

## 13. Selection

Select 6–8 items per run.

Rules:

- Highest ranked items first.
- Max 2 per category.
- Do not deliver the same cluster twice within 7 days.
- Do not deliver an item that already has status delivered.
- Prefer cluster representatives.
- If fewer than 6 strong items exist, deliver fewer rather than padding with weak content.

Suggested minimum relevance:

text relevance >= 6 

---

## 14. Article enrichment

For each selected item:

- Fetch source URL.
- Extract main article text.
- Store article text in DB.
- Truncate to approximately 3000 words before sending to the LLM.

If article extraction fails:

- Use title + snippet only.
- Still generate a brief.
- The ONE CAUTION field should mention that the source text could not be fully extracted.

Use a simple extraction fallback:

- Strip script/style/nav/footer.
- Collect paragraph text.
- Prefer the largest coherent text block.

---

## 15. Brief generation

For each selected item, generate a structured content brief.

The brief should be neutral, factual, and useful for later rewriting.

Do not fabricate facts. If details are missing, say so in caution.

Output must be strict JSON:

json {   "what_happened": "Two factual sentences.",   "why_it_matters": "Two to three sentences explaining who is affected and why.",   "linkedin_angle": {     "hook": "One strong hook line.",     "points": [       "Talking point 1",       "Talking point 2",       "Talking point 3"     ]   },   "instagram_carousel": {     "slides": [       "Slide 1 headline, max 8 words",       "Slide 2 one-liner",       "Slide 3 one-liner",       "Slide 4 one-liner"     ],     "cta": "Final slide CTA"   },   "caution": "One uncertainty, limitation, or verification note." } 

Brief rules:

- what_happened: 2 factual sentences.
- why_it_matters: 2–3 sentences.
- LinkedIn hook: insightful, not clickbait.
- LinkedIn points: practical and slightly opinionated, but not hype.
- Instagram slide 1: max 8 words.
- Instagram slides 2–4: concise one-liners.
- Caution: must be useful, not generic.

---

## 16. Publishing

The pipeline publishes three artifact types.

### feed/digest.json

This is the source of truth for the native app.

It should contain a rolling list of approximately the last 30 days of delivered items, newest first.

Schema:

json {   "generated_at": "2026-06-10T07:00:00+03:00",   "items": [     {       "id": 123,       "title": "Story title",       "url": "https://example.com/story",       "source": "Source name",       "category": "models",       "published_at": "2026-06-10T05:12:00Z",       "digest_date": "2026-06-10",       "digest_slot": "am",       "what_happened": "Two factual sentences.",       "why_it_matters": "Why this matters.",       "linkedin_angle": {         "hook": "Hook line",         "points": [           "Point 1",           "Point 2",           "Point 3"         ]       },       "instagram_carousel": {         "slides": [           "Slide 1",           "Slide 2",           "Slide 3",           "Slide 4"         ],         "cta": "CTA"       },       "caution": "Caution text"     }   ] } 

Requirements:

- Valid JSON.
- Stable documented schema.
- Newest first.
- No duplicate items.
- No duplicate clusters within 7 days.
- Only include the last ~30 days.

### feed/digest.xml

RSS 2.0 feed.

Each item:

- title = story title
- link = source URL
- description = why_it_matters
- pubDate = digest delivery time
- guid = stable item ID or canonical URL

The RSS must validate in common RSS readers.

### Markdown archive

Write one human-readable archive file per run:

text digests/YYYY-MM-DD-am.md digests/YYYY-MM-DD-pm.md 

The archive should include:

- Digest title/date
- Each item title and source URL
- Category
- What happened
- Why it matters
- LinkedIn angle
- Instagram carousel
- Caution

---

## 17. VPS automation

Implement this after the SwiftUI app and local macOS host mode are working.

Create:

text Dockerfile compose.yaml deploy/nginx.conf deploy/systemd/newsbeat-digest.service deploy/systemd/newsbeat-digest.timer

The deployment should:

1. Build a minimal Python 3.14 image.
2. Run `python -m newsbeat_digest run` as a short-lived batch container.
3. Cap the worker at 384 MB RAM and 0.5 CPU.
4. Persist `data/digest.db`, `feed/`, and `digests/` on the host.
5. Schedule two or three Tallinn-time runs with systemd.
6. Prevent overlap with a lock.
7. Serve the static output through a small localhost-only web container and
   the VPS's TLS reverse proxy.

Do not hardcode API keys.

Treat `digest.db`, `data/`, `feed/`, and `digests/` as ignored runtime state.
Persist the VPS copies outside the worker container.

---

## 18. SwiftUI app and local macOS host

Create a separate SwiftUI multiplatform app in /app.

The app should be buildable in Xcode.

### Configuration

The app should let me configure the feed source in one obvious place. It must
support a local file for macOS host mode and a remote URL for the VPS feed.

The future hosted value can be a constant such as:

swift let digestFeedURL = URL(string: "https://news.example.com/feed/digest.json")! 

Document exactly where to edit it.

### Data model

Create Swift models matching digest.json.

Important models:

swift DigestFeed DigestItem LinkedInAngle InstagramCarousel 

They must conform to:

swift Codable Identifiable Equatable 

### Fetching and cache

Requirements:

- Load digest.json on launch from the configured local file or remote URL.
- Support manual refresh.
- Cache the last successful JSON response locally.
- If loading the configured source fails, load the cached response.
- Show a friendly offline/error state if no cache exists.

### UI

Main UI:

- List grouped by digest date.
- Each row shows:
  - title
  - source
  - category tag
  - short why-it-matters preview
- Detail view shows:
  - title
  - source
  - open article link
  - category
  - what happened
  - why it matters
  - LinkedIn angle
  - Instagram carousel
  - caution

### Copy actions

Each item detail must include:

#### Copy LinkedIn angle

Copies formatted text:

text [Hook]  • Point 1 • Point 2 • Point 3  Source: [URL] 

#### Copy Instagram carousel

Copies formatted text:

text Slide 1: ... Slide 2: ... Slide 3: ... Slide 4: ...  CTA: ...  Source: [URL] 

Use platform-appropriate clipboard APIs:

- macOS: NSPasteboard
- iOS: UIPasteboard

### iOS share sheet

On iOS, add a share button that can share the LinkedIn angle or Instagram carousel text.

### macOS menu bar extra

On macOS, add a menu bar extra that shows today’s digest item count.

The menu should show:

- Today’s count
- A few latest item titles
- Open app action
- Refresh action if practical

Keep this simple. It does not need notifications.

### macOS local host mode

The macOS target may act as the interim on-prem scheduler. Keep this as a
coordinator around the existing Python executable, not a Swift rewrite of the
pipeline.

Requirements:

- macOS only; iOS must never launch the pipeline
- run once on launch when the digest is stale
- schedule refreshes only while the app or menu bar extra is running
- launch `python -m newsbeat_digest run` as a child process
- prevent overlapping runs
- show running, last success, and failure status
- reload local feed/digest.json after a successful run
- allow manual refresh/run from the app and menu bar
- obtain ANTHROPIC_API_KEY from Keychain or the existing environment
- use configurable repository and Python executable paths
- stop scheduling when the app exits

Do not bundle pipeline logic into Swift, create a daemon, or require a local
HTTP server. Preserve the feed contract so hosted migration only changes the
feed source and disables local scheduling. The personal macOS target may
disable App Sandbox so it can launch the configured local Python process; the
app README must call out that limitation.

### App README

Create /app/README.md with:

- Xcode version assumptions
- How to open the project
- Where to set the feed URL
- How to build for macOS
- How to build for iOS
- How offline caching works
- How to configure the local repository, Python executable, and host schedule
- How credentials are supplied and how local host mode is disabled
- Known limitations

---

## 19. Testing

Add smoke tests for the Python pipeline.

Minimum tests:

text tests/test_url_normalize.py tests/test_feed_json.py tests/test_selection.py tests/test_rss.py 

Tests should verify:

- URL tracking params are stripped.
- Duplicate URLs do not produce duplicate items.
- Selection respects max 2 per category.
- Delivered clusters are not re-delivered within 7 days.
- digest.json is valid and has required fields.
- RSS XML is generated.

Do not require live Anthropic API calls in tests.

Mock LLM responses.

---

## 20. Error handling requirements

The pipeline must be resilient.

A failed source must not crash the run.

A malformed LLM response must:

- Be retried once.
- If still invalid, log the issue and skip those items.

Article extraction failure must not prevent a brief.

A failed item should not prevent other items from being processed.

Running the pipeline twice in a row must not duplicate delivered feed items.

---

## 21. Acceptance criteria

The implementation is complete when:

- python -m newsbeat_digest collect fetches and stores items.
- python -m newsbeat_digest score scores and ranks items.
- python -m newsbeat_digest run creates a complete digest.
- feed/digest.json is valid and contains structured briefs.
- feed/digest.xml opens in a standard RSS reader.
- Markdown archive files are created in digests/.
- Running twice does not duplicate items.
- A new RSS feed can be added by editing sources.yaml.
- The SwiftUI app builds for macOS and iOS.
- The app fetches and caches digest.json.
- The app works offline using cached data.
- The app has one-tap copy for LinkedIn and Instagram content.
- The macOS app includes a menu bar extra.
- The macOS app can run and monitor the local pipeline while it is active.
- The iOS app never runs the pipeline.
- The iOS app includes a share sheet.
- The VPS timer runs the container within the configured resource limits.
- README files clearly explain setup and usage.

---

## 22. Suggested implementation order

Implement in this order. Do not skip ahead.

Status last verified: 2026-06-11 with 44 Python tests, a successful
resource-limited container smoke test, 3 macOS app tests, and successful macOS
and iOS builds.

### Phase 1 — Python skeleton and database [complete]

- [x] Create repo structure.
- [x] Add pyproject.toml.
- [x] Add CLI.
- [x] Add SQLite initialization.
- [x] Add RawItem and source interface.
- [x] Add URL normalization.
- [x] Add basic tests.

Verify:

bash python -m newsbeat_digest collect pytest 

Verified with Python 3.14.2 and the automated test suite.

### Phase 2 — Sources [complete]

Implement:

- [x] Hacker News source
- [x] RSS source
- [x] Reddit source
- [x] arXiv stub
- [x] 15-second HTTP timeout, one retry, and a descriptive User-Agent
- [x] Per-source failure isolation and logging
- [x] Configurable source enablement in sources.yaml

Verify that collection works even when one source fails.

Verified with a live collection run. Working sources fetched real items and
the run continued when Reddit returned HTTP 403.

### Phase 3 — Scoring and selection [complete]

Implement:

- [x] URL canonicalization
- [x] SQLite uniqueness by canonical URL
- [x] Simple title-similarity dedupe and cluster assignment
- [x] Anthropic client wrapper
- [x] Batch scoring
- [x] JSON validation with one retry
- [x] Deterministic EU/Estonia policy boost
- [x] Ranking and ranked CLI table
- [x] Selection rules and seven-day delivered-cluster guard

Verify:

bash python -m newsbeat_digest score 

Verified with mocked Anthropic responses and focused tests for clustering,
retry, policy boosting, category limits, minimum relevance, and the
seven-day delivered-cluster guard. Live Anthropic verification requires
`ANTHROPIC_API_KEY`.

### Phase 4 — Brief generation [complete]

Implement:

- [x] Article fetching
- [x] Article text extraction
- [x] Brief generation
- [x] Brief validation
- [x] DB persistence

Verify that selected items receive complete structured briefs.

Verified with mocked HTTP and brief generation tests. Tests do not call the
live Anthropic API.

### Phase 5 — Publishing [complete]

Implement:

- [x] JSON feed
- [x] RSS feed
- [x] Markdown archive
- [x] Idempotent delivery

Verify:

bash python -m newsbeat_digest publish 

Open the JSON in a browser and test RSS in an RSS reader.

Verified with JSON schema assertions, XML parsing, and a repeated publish test
that records one delivered cluster.

### Phase 6 — SwiftUI app and local macOS host [complete]

Implement:

- [x] Shared models
- [x] Local and remote feed loading
- [x] Cache
- [x] List UI
- [x] Detail UI
- [x] Copy buttons
- [x] iOS share sheet
- [x] macOS menu bar extra
- [x] macOS host coordinator
- [x] Stale-on-launch and in-process scheduling
- [x] Pipeline run status and overlap prevention
- [x] App README

Verify that both targets build, the reader works against local digest.json,
host mode refreshes it on macOS, and iOS remains feed-only.

Verified on 2026-06-10 with Swift 6.3.2 and Xcode 26.5. Both targets build,
macOS unit tests cover feed decoding, local loading, offline cache, and child
process launch, and only the macOS target includes the host coordinator.

### Phase 7 — Docker VPS deployment [complete]

Implement:

- [x] Minimal Python 3.14 image
- [x] 384 MB worker and 48 MB static-server limits
- [x] Persistent state and output mounts
- [x] Three-run Tallinn-time systemd timer
- [x] Overlap prevention
- [x] VPS reverse-proxy instructions
- [x] Remote feed configuration
- [x] Document disabling local host scheduling after migration

Verify with a local container run first, then verify the unchanged app feed
models against the VPS `digest.json`.

The container, timer, and fallback workflow contracts are covered by offline
regression tests. A live image pull/build, timer installation, and public URL
check require Docker and the target VPS.

---

## 23. Implementation notes

Keep the code simple and readable.

Prefer explicit functions over clever abstractions.

Use type hints.

Use structured logging.

Avoid unnecessary dependencies.

Do not hardcode secrets.

Do not fabricate missing article facts in briefs.

The quality of the brief matters more than collecting hundreds of sources.

The app’s core UX is:

> open → see today’s important AI stories → tap → copy LinkedIn or Instagram draft.

Optimize for that.
