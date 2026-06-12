# Project: newsbeat-app

This repository contains the native SwiftUI reader for the static
`digest.json` feed produced by the separate `newsbeat-digest` repository.

## Repository scope

This repository owns:

- shared macOS/iOS feed models, loading, caching, and reader UI
- on-demand LinkedIn and Instagram post generation
- macOS menu bar UI and optional local processor coordinator
- iOS copy and share behavior
- the consumer side of the `digest.json` contract

Do not add the Python pipeline, SQLite processing, Docker deployment, source
collection, ranking, summarization, or feed publishing here.

## Hard constraints

- Use Swift 6.3.2 and SwiftUI.
- Keep macOS and iOS in one shared codebase where practical.
- Use async/await and Codable models matching `digest.json`.
- Keep dependencies minimal; do not add third-party Swift packages without a
  clear need.
- Do not add accounts, authentication, analytics, Firebase, Supabase, a web
  app, push notifications, auto-posting, or in-app editing.
- Store API keys in Keychain. Never hardcode secrets.
- The app must remain usable from cached feed data when offline.

## Feed boundary

The app reads a local file or remote HTTPS `digest.json`. It does not require a
backend API. Feed version 1 always includes `what_happened`,
`why_it_matters`, and `caution`; `linkedin_angle` and
`instagram_carousel` are optional legacy fields.

Feed producer changes belong in `newsbeat-digest`. Coordinate schema changes
across both repositories rather than copying processor logic into Swift.

## Platform rules

- The iOS target is feed-only and must never launch Python.
- The macOS target may launch `python -m newsbeat_digest run` in a
  user-configured digest checkout while the app is open.
- Closing the macOS app stops local scheduling.
- The personal macOS target may keep App Sandbox disabled for local host mode;
  document this limitation.

## Verification

After source or project changes, run:

```bash
xcodegen generate
xcodebuild -project Newsbeat.xcodeproj \
  -scheme NewsbeatMac \
  -destination 'platform=macOS' \
  build test
xcodebuild -project Newsbeat.xcodeproj \
  -scheme NewsbeatIOS \
  -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  CODE_SIGNING_ALLOWED=NO \
  build
```

Do not make live Anthropic calls in tests. Test request construction and
response parsing with fixtures.
