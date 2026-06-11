# Native macOS/iOS app

Everything under `app/` belongs to the native SwiftUI client named
`newsbeat`. The separate `newsbeat-digest` batch processor lives outside this
directory in the root-level `newsbeat_digest/` Python package and
Docker/deployment files.

The app reads the published `feed/digest.json` contract. It does not collect,
rank, brief, or publish stories, and it does not access the backend SQLite
database.

The source layout keeps shared and platform-specific code explicit:

```text
app/Newsbeat/
├── src/
│   ├── shared/
│   ├── macOS/
│   └── iOS/
├── tests/
│   └── macOS/
└── project.yml
```

## Requirements

- Xcode 26.5 or newer
- Swift 6.3.2
- XcodeGen

Generate the project after changing `project.yml`:

```bash
cd app/Newsbeat
xcodegen generate
```

`Newsbeat.xcodeproj` and `generated/` are reproducible XcodeGen outputs and
are intentionally ignored. Keep source changes in `project.yml` and `src/`.

Build and test:

```bash
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

Select your development team in Xcode before installing on a physical iPhone
or distributing either target.

## Reader configuration

Open Settings in the app and select either:

- **Local file**: choose a `digest.json` file. This is the default on macOS.
- **Remote URL**: enter an HTTP or HTTPS URL. This is the default on iOS and
  is the mode intended for the VPS-hosted static feed.

Every successful load is saved atomically under Application Support. If the
next local or remote load fails, the app opens that cached feed and labels it
as offline data.

The app groups stories by `digest_date`. Story details include the summary,
importance, caution, source link, and copy-ready LinkedIn and Instagram text.
iOS also exposes native share-sheet buttons.

## macOS local host mode

The macOS settings include an optional local host mode. Configure:

- repository path, for example `~/Projects/newsbeat`
- Python executable, normally `<repository>/.venv/bin/python`
- optional Anthropic API key stored in Keychain

When enabled, the coordinator:

- runs once on launch when the local feed is stale
- checks the 08:00 and 17:00 local schedule while the app is running
- invokes the `newsbeat-digest` Python module in the configured repository
- prevents overlapping runs and exposes status and CLI output
- switches the reader to the generated `feed/digest.json` after success
- stops scheduling when the app exits

The CLI can also inherit `ANTHROPIC_API_KEY` from the app's environment. A
Keychain value takes precedence when one is saved.

The personal macOS target deliberately has App Sandbox disabled because it
must launch a user-configured Python executable and read the repository. This
is an interim local scheduler, not an embedded Python runtime or daemon. The
iOS target does not compile or contain the host coordinator.

Host mode does not make the Python processor part of the app. It only starts
the independently runnable backend CLI and reloads `digest.json` after a
successful run.

## VPS feed migration

After the VPS container has generated its first digest and the reverse proxy
serves it over HTTPS:

1. Copy the public VPS origin.
2. Append `/feed/digest.json`.
3. Open app Settings and select **Remote URL**.
4. Enter the complete feed URL and choose **Done** to reload it.
5. On macOS, turn off **Run newsbeat-digest while this app is open**.

For example:

```text
https://news.example.com/feed/digest.json
```

The iOS app remains feed-only. The macOS reader can use the same remote URL
with host mode disabled, so moving to the VPS container does not change the
reader UI, cache, or feed model.
