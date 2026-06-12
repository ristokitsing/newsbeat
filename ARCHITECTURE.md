# Repository architecture

Newsbeat has two independently runnable components connected by one static
file contract. The native app is named `newsbeat`; the Python/Docker batch
processor is named `newsbeat-digest`. There is no backend API.

```text
newsbeat-digest batch processor
    collect -> score -> brief -> publish
                         |
                         v
                 feed/digest.json
                         |
                         v
Native SwiftUI app
    load -> cache -> read -> copy/share
```

## 1. Native app: `app/`

Everything under `app/` belongs to the macOS/iOS application.

```text
app/
├── README.md
└── Newsbeat/
    ├── project.yml
    ├── src/
    │   ├── shared/    # Reader UI, feed models, loading, and offline cache
    │   ├── macOS/     # macOS UI and optional local-process coordinator
    │   └── iOS/       # iOS-specific copy/share behavior
    └── tests/         # Native app tests
```

The app consumes `digest.json`; it does not collect news, run the pipeline,
score stories, write SQLite data, or generate feeds. It does call the
Anthropic Messages API directly for **on-demand** LinkedIn/Instagram drafts
(button press in the detail view), using the key in the device Keychain and
caching results locally — this is a per-item action, not the batch pipeline.

The macOS-only host coordinator is an adapter at the app boundary. It can
launch the separate Python CLI while the app is open, but the pipeline remains
owned by the backend processor. The iOS target never launches Python.

## 2. `newsbeat-digest`: Python and Docker

`newsbeat-digest` is a short-lived batch processor, not a web server.

```text
newsbeat_digest/        # Python import package
tests/                  # newsbeat-digest tests
pyproject.toml          # `newsbeat-digest` package and CLI configuration
sources.yaml            # Processor source configuration
profile.md              # Processor scoring profile
Dockerfile              # newsbeat-digest worker image
compose.yaml            # Batch worker plus static feed server
deploy/                 # VPS nginx and systemd configuration
```

The installed command is `newsbeat-digest`; its Python module is
`newsbeat_digest`. The same processor runs directly on macOS, inside Docker,
and from the VPS systemd timer. Each run exits after publishing.

## 3. Published contract and runtime state

These root directories are backend outputs rather than app source:

```text
feed/digest.json        # App source of truth and stable component contract
feed/digest.xml         # RSS output
digests/*.md            # Human-readable archives
data/digest.db          # Persistent Docker/VPS SQLite state
digest.db               # Local/manual-recovery SQLite state
```

All four paths are ignored by Git.

The feed stays at `version: 1`. Items always carry the summary fields
(`what_happened`, `why_it_matters`, `caution`); `linkedin_angle` and
`instagram_carousel` are optional — new summary-only items omit them, while
legacy items inside the seven-day window keep their pre-generated drafts. The
app decodes both shapes, so the two sides ship in lockstep without a version
bump.

The app may read a local `feed/digest.json` or the same file over HTTPS. Moving
from local host mode to VPS mode changes only the configured feed location.

## Where changes belong

| Change | Owner |
| --- | --- |
| Collection, dedupe, ranking, briefs, publishing | Backend: `newsbeat_digest/` |
| Source list or scoring profile | Backend: `sources.yaml`, `profile.md` |
| Container limits, static serving, schedules | Backend: `compose.yaml`, `deploy/` |
| Feed schema generation | Backend: `newsbeat_digest/publish/` |
| Feed schema decoding | App: `app/Newsbeat/src/shared/FeedModels.swift` |
| Reader UI, cache, copy/share actions | App: `app/Newsbeat/src/` |
| Launching the local CLI from macOS | App adapter: `app/Newsbeat/src/macOS/` |

When the feed schema changes, update and test both the backend encoder and the
app decoder. Other implementation details should not cross this boundary.
