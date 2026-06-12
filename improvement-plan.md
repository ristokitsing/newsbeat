newsbeat Improvement Plan

 For agentic workers: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

 Goal: Harden and finish newsbeat: VPS runs every 4–5h (4 daytime runs), 7-day feed retention verified, the SwiftUI app builds/runs on macOS + iOS Simulator, and LinkedIn/Instagram drafts are generated only when the
 user taps a button in the app (direct Claude Haiku call from Swift), with backend security hardening.

 Architecture: The Python pipeline keeps auto-generating a short summary (what_happened, why_it_matters, caution) per selected story but stops pre-generating social posts. The app gains a PostGenerationService that
 calls the Anthropic Messages API directly (raw URLSession — no official Swift SDK) with the key in Keychain, caching results locally. Feed stays version: 1; linkedin_angle/instagram_carousel become optional on both
 sides (legacy rows still in the 7-day window keep emitting them).

 Tech stack: Python 3.14 + anthropic SDK + httpx + SQLite; SwiftUI (Swift 6, XcodeGen); Docker + systemd timer + nginx static feed on a VPS. Models: claude-haiku-4-5 everywhere (configurable; pipeline via
 AI_DIGEST_SCORE_MODEL/AI_DIGEST_BRIEF_MODEL, app via Settings).

 ---
 Context

 Audit of the repo (2026-06-12) found the system is largely built and healthy, but four user requirements need work:

 1. VPS cadence — timer runs 3×/day (07:07/14:07/20:07); user wants 4 daytime runs (~4–5h apart).
 2. On-demand post generation — today pipeline/brief.py auto-generates LinkedIn + Instagram drafts for every selected item on every run. User wants posts generated only on explicit button press in the app.
 3. App — UI is complete (list/detail, copy, share sheet, offline cache, menu bar extra, macOS host coordinator) but app/Newsbeat/ was never committed to git, and buildability on macOS/iOS Simulator is unverified.
 4. Security hardening — container/nginx/systemd lack several cheap mitigations; article fetching has no download size cap (risk under the 384MB worker).

 Audit: already solid (no change needed)

 - 7-day feed retention exists: FEED_HISTORY_DAYS = 7 in newsbeat_digest/publish/publisher.py:18 (Task 2.5 only adds a regression test).
 - 7-day cluster redelivery window in pipeline/select.py (REDELIVERY_WINDOW_DAYS).
 - Overlap prevention: flock -n in deploy/systemd/newsbeat-digest.service; atomic feed writes; parameterized SQL throughout db.py; non-root Docker user; mem 384m / cpu 0.5 / pids 128 caps in compose.yaml; .gitignore
 correctly excludes .env, data/, feed/, digests/, digest.db; no secrets committed (.env.example only).
 - Claude API usage is modern and correct: messages.create with output_config: {format: {type: "json_schema"}}, strict local validation, retry-once on malformed output, batching of 30 for scoring, deterministic
 EU/Estonia boost in code (score.py:220). Anthropic SDK's built-in retries already cover 429/5xx.
 - httpx verifies TLS by default; 15s timeouts; custom User-Agent; per-source failure isolation.

 Audit: weaknesses → tasks

 ┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┬──────────┐
 │                                                      Finding                                                      │   Task   │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ App source never committed                                                                                        │ 1.1      │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ Builds unverified on macOS/iOS Simulator                                                                          │ 1.2–1.3  │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ Social posts pre-generated every run (cost + violates new requirement)                                            │ 2.x, 3.x │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ Timer is 3×/day, not 4–5h cadence                                                                                 │ 4.1      │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ MacHostCoordinator hardcodes 08:00/17:00 schedule (out of sync with new cadence)                                  │ 4.2      │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ No download size cap when fetching articles/sources (HttpClient buffers whole body; OOM risk at 384MB)            │ 5.1      │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ Worker container: no cap_drop, no-new-privileges, or read-only rootfs                                             │ 5.2      │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ nginx: server_tokens not off, no X-Content-Type-Options, runs as root master (official image)                     │ 5.3      │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ Public TLS / reverse-proxy setup not documented; .env perms not documented                                        │ 5.4      │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ temperature=0 sent unconditionally — breaks if user configures Opus 4.7+/Fable via env (those reject temperature) │ 2.6      │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ KeychainStore lives in src/macOS/ though the code is platform-portable; iOS has no key storage                    │ 3.1      │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ App Codable models require linkedin_angle/instagram_carousel (blocks contract change)                             │ 3.2      │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ Swift test coverage minimal (one file)                                                                            │ 3.6      │
 ├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────┤
 │ README/app README will be stale after these changes; Claude usage/cost not documented                             │ 6.x      │
 └───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┴──────────┘

 Decisions (made with user, 2026-06-12)

 - Post generation: App calls Anthropic Messages API directly (both platforms), key in Keychain, default model claude-haiku-4-5, results cached locally, Regenerate supported.
 - Pipeline still auto-generates the short summary (what_happened, why_it_matters, caution) per selected item — article fetching stays.
 - Schedule: 4 daytime runs at 07:07, 11:07, 16:07, 21:07 Europe/Tallinn. Max gap (21:07→07:07) is 10h < the existing 12h collect lookback, so lookback_hours=12 stays.
 - Feed contract: stays version: 1; the two social fields become optional. Rationale: the app is the only consumer and ships in lockstep; old cached feeds (superset) still decode; a version bump would only add
 compatibility code. Producer keeps emitting social fields for legacy briefs still inside the 7-day window.

 ---
 Phase 1 — Baseline: commit the app, verify everything builds

 Task 1.1: Commit the untracked app

 Files: app/Newsbeat/** (all currently untracked; .xcodeproj and generated/ stay gitignored)
 - [x] git add app/ && git status — confirm only source files, project.yml, tests, READMEs are staged (no DerivedData, no xcuserdata). (Removed a stray nested empty `.git` repo inside app/Newsbeat first.)
 - [x] Commit: git commit -m "Add native SwiftUI reader app".

 Task 1.2: Verify Python baseline

 - [x] Run pytest from repo root. Expected: all 16 test files pass. (46 tests passed in .venv after `pip install -e ".[dev]"`.) Fix any pre-existing failure before proceeding (none expected — pipeline ran successfully 2026-06-10..12).

 Task 1.3: Verify app baseline builds

 - [x] cd app/Newsbeat && xcodegen generate
 - [x] xcodebuild -project Newsbeat.xcodeproj -scheme NewsbeatMac -destination 'platform=macOS' build test — build + 3 FeedModelsTests passed.
 - [x] xcodebuild -project Newsbeat.xcodeproj -scheme NewsbeatIOS -destination 'platform=iOS Simulator,name=iPhone 17' build — BUILD SUCCEEDED (iPhone 16 not installed; used iPhone 17).
 - [x] Fix whatever breaks (deployment target, missing platform guards). Nothing broke — no fix commit needed.

 ---
 Phase 2 — Backend: pipeline stops pre-generating social posts (feed contract, Python side)

 Order matters: DB → models → brief → publish → tests. The system stays runnable after each task because social columns become nullable, not removed.

 Task 2.1: DB migration — make social columns nullable

 Files: Modify newsbeat_digest/db.py (briefs table at ~line 48, insert_brief at ~294, row mapping at ~482); Test tests/test_db.py
 - [x] Add a PRAGMA user_version-gated migration in Database.initialize(): if user_version < 1, rebuild briefs with linkedin_hook, linkedin_points_json, instagram_slides_json, instagram_cta as nullable (TEXT without
 NOT NULL), copying existing rows (CREATE TABLE briefs_new …; INSERT INTO briefs_new SELECT … FROM briefs; DROP TABLE briefs; ALTER TABLE briefs_new RENAME TO briefs; inside one transaction), then PRAGMA
 user_version = 1. New databases get the nullable schema directly with user_version = 1. (Rebuild gated on detecting old NOT NULL schema via PRAGMA table_info.)
 - [x] insert_brief accepts a BriefContent whose social parts are absent and writes NULL for the four columns.
 - [x] Row→model mapping returns None for NULL social columns (see Task 2.2 model change).
 - [x] Test: create a DB with the old schema + one populated brief row, run initialize(), assert row survives, social fields readable, and a new summary-only insert succeeds. Run pytest tests/test_db.py -v.
 - [x] Commit: git commit -m "Make brief social columns nullable with user_version migration".

 Task 2.2: Models — optional social fields

 Files: Modify newsbeat_digest/models.py (BriefContent TypedDict, Brief dataclass)
 - [x] BriefContent: linkedin_angle and instagram_carousel become NotRequired[...] (kept on BriefContent so legacy briefs/feeds still decode).
 - [x] Brief dataclass: linkedin_hook: str | None, linkedin_points: tuple[str, ...] | None, instagram_slides: tuple[str, ...] | None, instagram_cta: str | None.
 - [x] pytest — fix type fallout in db.py/publish/ reported by failures. Commit.

 Task 2.3: Brief generator → summary-only

 Files: Modify newsbeat_digest/pipeline/brief.py; Test tests/test_brief.py
 - [x] BRIEF_SCHEMA shrinks to {what_happened, why_it_matters, caution} (all required, additionalProperties: false).
 - [x] _brief_prompt drops the LinkedIn/Instagram requirement lines; keep the factual-only system prompt and the limited-source caution rule.
 - [x] max_tokens 1500 → 700.
 - [x] validate_brief_content validates the 3-field shape only.
 - [x] Keep CLI command name brief (no churn in __main__.py).
 - [x] Update tests/test_brief.py fixtures to the new shape; add a rejection test for a response that still contains linkedin_angle. Run pytest tests/test_brief.py -v. Commit: git commit -m "Generate summary-only
 briefs; social posts move to the app".

 Task 2.4: Publishers emit social fields only when stored

 Files: Modify newsbeat_digest/publish/feed_json.py (_feed_item), check newsbeat_digest/publish/feed_rss.py + publish/archive.py for social-field references; Test tests/test_feed_json.py
 - [x] _feed_item: include linkedin_angle/instagram_carousel keys only when brief.linkedin_hook is not None (legacy rows inside the 7-day window keep them; new rows omit them). Feed version stays 1.
 - [x] If feed_rss.py / archive.py render social fields, guard them the same way (summary fields are always present). (feed_rss.py never rendered social fields; archive.py guarded.)
 - [x] Tests: one item with social content → keys present; one without → keys absent; JSON still valid. Run pytest tests/test_feed_json.py -v. Commit.

 Task 2.5: 7-day retention regression test

 Files: Test tests/test_feed_json.py (or tests/test_pipeline.py, wherever publish_digest is already exercised)
 - [x] Test publish_digest with briefs dated today, 6 days ago, and 8 days ago: feed contains the first two, drops the third, newest first. (Uses the existing now= injection in publish_digest.) Run pytest. Commit. (test_feed_retention_keeps_recent_days_newest_first)

 Task 2.6: Guard temperature for newer models

 Files: Modify newsbeat_digest/pipeline/score.py:89, newsbeat_digest/pipeline/brief.py:91
 - [x] Both call sites pass temperature=0 unconditionally. Opus 4.7+/Fable reject temperature with a 400, so a user overriding AI_DIGEST_*_MODEL breaks. Add a tiny shared helper (e.g. in score.py, imported by
 brief.py): omit temperature when the model name starts with claude-opus-4-7, claude-opus-4-8, or claude-fable; otherwise keep temperature=0 for deterministic Haiku output. One comment line stating the constraint. (supports_temperature in score.py.)
 - [x] pytest (existing fake-client tests must still pass). Commit.

 ---
 Phase 3 — App: optional fields + on-demand post generation (Swift side)

 Task 3.1: Move KeychainStore to shared

 Files: Move app/Newsbeat/src/macOS/KeychainStore.swift → app/Newsbeat/src/shared/KeychainStore.swift
 - [x] The implementation is already platform-portable (Foundation + Security, no AppKit). Move the file; no project.yml change needed (it globs src/shared).
 - [x] xcodegen generate + build both schemes. Commit.

 Task 3.2: Feed models — optional social fields

 Files: Modify app/Newsbeat/src/shared/FeedModels.swift; Test app/Newsbeat/tests/macOS/FeedModelsTests.swift
 - [x] DigestItem.linkedinAngle: LinkedInAngle?, instagramCarousel: InstagramCarousel?.
 - [x] linkedInText/instagramText become helpers that build text from either the pre-generated structs or a generated post (see Task 3.3) — simplest: move the formatting into free functions
 formatLinkedIn(hook:points:url:) / formatInstagram(slides:cta:url:) so both paths share them. (linkedInText/instagramText now return String?.)
 - [x] Tests: decode a feed item JSON without the two keys (must succeed), and a legacy one with them. Run macOS build test. Commit.

 Task 3.3: PostGenerationService (direct Anthropic call) + local post cache

 Files: Create app/Newsbeat/src/shared/PostGenerationService.swift, app/Newsbeat/src/shared/GeneratedPostStore.swift
 - [x] PostGenerationService (actor): func generate(_ kind: PostKind, for item: DigestItem, apiKey: String, model: String) async throws -> GeneratedPost where PostKind is .linkedIn | .instagram. (Request building/parsing are pure static funcs; no beta header needed for output_config json_schema.)
   - POST https://api.anthropic.com/v1/messages, headers x-api-key, anthropic-version: 2023-06-01, content-type: application/json; 30s timeout.
   - Body: model (default claude-haiku-4-5), max_tokens: 1500, output_config: {format: {type: "json_schema", schema: …}} — schema per kind: LinkedIn {hook: string, points: string[3]}, Instagram {slides: string[4],
 cta: string} (mirror the validation constraints from the old Python BRIEF_SCHEMA in pipeline/brief.py).
   - System prompt mirrors brief.py: factual-only, use only supplied material, never invent facts/quotes/numbers.
   - User content: the feed item's title, source, URL, category, what_happened, why_it_matters, caution — and an explicit instruction that no full article text is available, so claims must stay within the supplied
 summary.
   - Parse: check HTTP status (decode Anthropic error body {type:"error", error:{type,message}} for the message), find first content block with "type": "text", JSONDecoder the text into the typed post, validate
 counts (3 points / 4 slides).
 - [x] GeneratedPostStore (actor): persists [String: GeneratedPost] keyed "\(item.id)-\(kind)" to Application Support/newsbeat/posts-cache.json (same pattern as DigestService.persistCache); methods post(for:kind:),
 save(_:for:kind:). Generation results survive relaunch; Regenerate overwrites.
 - [x] Build both schemes. Commit: git commit -m "Add on-demand Claude post generation with local cache". (Bridged to SwiftUI via a @MainActor PostGenerationModel.)

 Task 3.4: Settings — API key + model on both platforms

 Files: Modify app/Newsbeat/src/shared/ReaderViews.swift (SettingsView), app/Newsbeat/src/shared/FeedPreferences.swift; check app/Newsbeat/src/macOS/MacHostViews.swift for the existing key field
 - [x] Add a shared "Post generation" section to SettingsView: SecureField for the Anthropic API key (read/write via KeychainStore, same service/account the macOS host coordinator already uses — one key for both
 features) and a model TextField defaulting to claude-haiku-4-5, stored in FeedPreferences (UserDefaults).
 - [x] Deduplicate: if MacHostSettingsSection has its own key field, point it at the same shared section or note it reuses the same Keychain entry. (Removed the host section's key field + apiKeyDraft/saveAPIKey; it reuses the shared Keychain entry.)
 - [x] Build both schemes; on macOS open Settings and save/read a key. Commit. (Builds verified; manual save/read is a runtime check.)

 Task 3.5: Detail view — Create/Copy/Regenerate flows

 Files: Modify app/Newsbeat/src/shared/ReaderViews.swift (DigestDetailView, DraftSection)
 - [x] Replace the two static DraftSections with a state-driven PostSection(kind:) per platform-shared view:
   - Pre-generated content present (legacy item): show text + Copy (today's behavior).
   - Cached generated post: show text + Copy + Regenerate button.
   - Nothing yet: prominent "Create LinkedIn post" / "Create Instagram post" button.
   - Loading: ProgressView + disabled button. Error: readable message + Retry. Missing API key: message with a button that opens Settings.
 - [x] Copy/share use the shared formatting helpers from Task 3.2; keep the iOS ShareLinks, now driven by whichever text is available.
 - [x] Build both schemes. Manual check in macOS app and iOS Simulator: button → spinner → draft → copy; relaunch → draft still there; Regenerate replaces it. Commit. (Builds verified; the button→spinner→draft→relaunch flow is a runtime check.)

 Task 3.6: Swift tests for the new logic

 Files: Modify app/Newsbeat/tests/macOS/FeedModelsTests.swift or create app/Newsbeat/tests/macOS/PostGenerationTests.swift
 - [x] No live network in tests: factor request-body building and response parsing in PostGenerationService into pure functions; test (a) request JSON contains model/schema/system, (b) a canned Anthropic response
 parses into a valid post, (c) malformed/over-count responses throw. (Added PostGenerationTests.swift — 7 cases.)
 - [x] xcodebuild … -scheme NewsbeatMac build test passes. Commit. (11 macOS tests pass.)

 ---
 Phase 4 — Scheduling: every 4–5 hours

 Task 4.1: systemd timer → 4 daytime runs

 Files: Modify deploy/systemd/newsbeat-digest.timer
 - [x] Replace the three OnCalendar= lines with four: 07:07, 11:07, 16:07, 21:07 (Europe/Tallinn); update Description=Run newsbeat-digest four times daily. Keep Persistent=true + RandomizedDelaySec=5min.
 - [x] No lookback change needed: max gap 10h (21:07→07:07) < 12h lookback_hours in __main__.py:_collect; canonical-URL dedupe makes overlap free. Note this in the commit message.
 - [x] Verify syntax: systemd-analyze calendar "*-*-* 07,11,16,21:07:00 Europe/Tallinn" style check or four separate lines (keep four lines for clarity). Commit. (systemd-analyze unavailable on macOS; format matches the prior working entries, and test_container_deployment asserts the 4 lines/hours.)

 Task 4.2: Align MacHostCoordinator schedule

 Files: Modify app/Newsbeat/src/macOS/MacHostCoordinator.swift (currentSlotStart, currentScheduleToken, status message at line ~64)
 - [x] Replace the hardcoded 08:00/17:00 slots with the same four local hours [7, 11, 16, 21]: token = "\(day)-\(slotHour)"; currentSlotStart returns the most recent slot hour. Update the "Watching the …" status
 string.
 - [x] Build macOS scheme; with host mode enabled confirm a stale feed triggers a run at launch. Commit. (Build verified; stale-feed launch run is a runtime check. Note: committed with the Phase 3 app commit since both edit MacHostCoordinator.swift.)

 ---
 Phase 5 — Security hardening (backend)

 Task 5.1: Download size cap in HttpClient

 Files: Modify newsbeat_digest/sources/base.py (HttpClient.get); Test tests/test_sources.py
 - [ ] Cap response bodies at MAX_RESPONSE_BYTES = 5_000_000: use self._client.stream("GET", …), raise for status, accumulate chunks until the cap, and raise a clear error if exceeded (protects the 384MB worker from
 a hostile/huge article URL; applies to all sources and pipeline/article.py automatically since both use this client). Preserve the existing retry-once and return an httpx.Response-compatible object — simplest:
 build the response via httpx.Response(status_code, content=collected, …) or return (bytes, headers)-style wrapper; pick whichever keeps rss.py/reddit.py/hn.py/article.py call sites (response.text, .json())
 unchanged.
 - [ ] Test with a mocked transport streaming > cap → error; normal body → unchanged behavior. pytest tests/test_sources.py -v. Commit.

 Task 5.2: Worker container lockdown

 Files: Modify compose.yaml (worker service)
 - [ ] Add to newsbeat-digest service: read_only: true, tmpfs: ["/tmp:size=16m"], cap_drop: [ALL], security_opt: ["no-new-privileges:true"]. Writable paths are already the three bind mounts (/data, /app/feed,
 /app/digests).
 - [ ] Verify locally: docker compose run --rm newsbeat-digest collect completes (or --help if no key configured). Commit.

 Task 5.3: nginx hardening

 Files: Modify compose.yaml (static-feed), deploy/nginx.conf
 - [ ] Switch image to nginxinc/nginx-unprivileged:1.29-alpine (no root master, no setuid caps needed), then add cap_drop: [ALL], security_opt: ["no-new-privileges:true"]. Update nginx.conf for the unprivileged
 image: pid /tmp/nginx.pid;, cache/temp paths under /tmp, adjust the tmpfs entries accordingly (/tmp:size=16m), keep listen 8080.
 - [ ] In nginx.conf http/server block: server_tokens off;, add_header X-Content-Type-Options "nosniff" always;, add_header Referrer-Policy "no-referrer" always;, charset utf-8;. Keep GET/HEAD-only and try_files
 $uri =404.
 - [ ] Verify: docker compose up -d static-feed && curl -sI http://127.0.0.1:8088/feed/digest.json shows the headers, no nginx version, 200. Commit.

 Task 5.4: Document TLS proxy, .env perms, key handling

 Files: Modify README.md (VPS section), deploy/README.md
 - [ ] Document fronting 127.0.0.1:8088 with a host reverse proxy for the public feed URL — include a complete Caddy example (news.example.invalid { reverse_proxy 127.0.0.1:8088 }, automatic TLS) and note the
 certbot/nginx alternative; instruct setting AI_DIGEST_PAGES_URL to the public URL. Use a documented placeholder domain (the real URL is unknown).
 - [ ] Document chmod 600 .env on the VPS, that the key never appears in images or compose files (env_file only on the worker), and that the feed is intentionally public, non-secret content (note basic-auth at the
 proxy as an option the user can add later).
 - [ ] Note the limits of systemd-unit hardening here (the unit just invokes docker compose; isolation comes from the container settings in 5.2/5.3). Commit.

 ---
 Phase 6 — Documentation + final verification

 Task 6.1: Update docs for all changed behavior

 Files: Modify README.md, app/README.md, ARCHITECTURE.md (feed contract section), .env.example if needed
 - [ ] Feed contract: linkedin_angle/instagram_carousel now optional; version stays 1.
 - [ ] New workflow: pipeline = collect/score/summarize/publish 4×/day; posts generated on demand in the app; where the API key lives on each platform (Keychain) and that the macOS host coordinator + post generation
 share one Keychain entry.
 - [ ] Claude API usage & cost section: scoring (Haiku, batches of 30, titles/snippets only, ~2–5 calls/run), summaries (Haiku, ~6–8 calls/run, article text truncated to 12k chars), on-demand posts (Haiku, 1
 call/button press, ≈$0.003). Estimated pipeline cost ≈ $0.05–0.08/run → ≈ $0.20–0.32/day at 4 runs (within the <$0.10/run rule). Models configurable: AI_DIGEST_SCORE_MODEL, AI_DIGEST_BRIEF_MODEL, app Settings.
 - [ ] New timer cadence + how to apply on the VPS (cp deploy/systemd/* /etc/systemd/system/ && systemctl daemon-reload && systemctl restart newsbeat-digest.timer).
 - [ ] Commit.

 Task 6.2: End-to-end verification

 - [ ] pytest — all green.
 - [ ] python -m newsbeat_digest run (with ANTHROPIC_API_KEY set) — completes; feed/digest.json valid, new items have no social keys, items ≤7 days only; run twice → no duplicate delivered items.
 - [ ] cd app/Newsbeat && xcodegen generate
 - [ ] xcodebuild -project Newsbeat.xcodeproj -scheme NewsbeatMac -destination 'platform=macOS' build test
 - [ ] xcodebuild -project Newsbeat.xcodeproj -scheme NewsbeatIOS -destination 'platform=iOS Simulator,name=iPhone 16' build
 - [ ] Manual on macOS app + iOS Simulator: load feed (local file on macOS, remote/local on iOS), open story, Create LinkedIn post → draft appears → Copy; kill app, relaunch offline → cached feed + cached post still
 present; Regenerate works; missing-key state shows guidance.
 - [ ] macOS host mode: enable, Run Now → pipeline runs, feed reloads; iOS has no pipeline affordances.
 - [ ] docker compose build && docker compose run --rm newsbeat-digest run locally under the new hardening flags.
 - [ ] Final commit; leave repo on main with clean status.

 ---
 Risks & limitations

 - API key on device: direct app→Anthropic calls require the key in the device Keychain. Acceptable for a single-user personal tool; never embed the key in source or the feed. iOS Simulator Keychain is per-simulator
 (re-enter the key there).
 - Generated posts lack article text: on-demand prompts only see the stored summary, so post quality depends on summary quality; the prompt explicitly forbids invention and the caution field is passed through. If
 quality disappoints, a later option is storing truncated article_text in the feed (size tradeoff) — out of scope now.
 - SQLite migration: the user_version rebuild runs once on the VPS's persistent data/digest.db; the test in Task 2.1 covers it, but take a one-line backup first (cp data/digest.db data/digest.db.bak) when deploying.
 - Legacy cached app data: old digest-cache.json decodes fine under the new optional models; the posts cache is new and starts empty.
 - nginx-unprivileged switch: path/pid changes are easy to get subtly wrong — Task 5.3's curl check is mandatory before deploying.
 - Out of scope (per CLAUDE.md non-goals): no backend API, no auth, no push, no auto-posting, no third-party Swift packages.