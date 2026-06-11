# newsbeat-digest deployment

This directory contains VPS deployment configuration for the
`newsbeat-digest` batch processor:

- `systemd/` starts the short-lived Docker worker on a timer and prevents
  overlapping runs.
- `nginx.conf` serves the generated `feed/` and `digests/` files as static
  content.

Nothing here is part of the native macOS/iOS app. The deployment exposes
static files only; it does not run a Python API. See the root
[`README.md`](../README.md#backend-docker-deployment) for setup commands.
