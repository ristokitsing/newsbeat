# newsbeat-digest deployment

This directory contains VPS deployment configuration for the
`newsbeat-digest` batch processor:

- `systemd/` starts the short-lived Docker worker four times daily (07:07,
  11:07, 16:07, 21:07 `Europe/Tallinn`) and uses `flock` to prevent
  overlapping runs.
- `nginx.conf` serves the generated `feed/` and `digests/` files as static
  content. It targets the `nginx-unprivileged` image: the pid and temp paths
  live under `/tmp`, and the server sends `server_tokens off`,
  `X-Content-Type-Options: nosniff`, and `Referrer-Policy: no-referrer`,
  GET/HEAD only.

The systemd unit only invokes `docker compose`; it provides little isolation
itself. The real confinement comes from the container settings in
`compose.yaml` (read-only rootfs, `/tmp` tmpfs, `cap_drop: [ALL]`,
`no-new-privileges`, non-root user, and the resource caps).

Nothing here is part of the native macOS/iOS app. The deployment exposes
static files only (intentionally public, non-secret content); it does not run
a Python API. See the root
[`README.md`](../README.md#backend-docker-deployment) for setup commands,
the public TLS reverse-proxy (Caddy/certbot) example, and `.env` handling.
