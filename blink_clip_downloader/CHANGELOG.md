# Changelog

## 2.1.0

### Bug fixes

- **Fixed `/bin/sh: can't open /init: Permission denied` crash on HA OS** —
  Switched from the S6-overlay v3 `CMD`-based one-shot mechanism to a proper
  S6v3 **longrun service definition** at
  `/etc/s6-overlay/s6-rc.d/blink-downloader/`.  The old `CMD ["/run.sh"]`
  approach triggered an S6v3 internal shutdown path that calls `/init` via
  `/bin/sh`; `/init` is mode 711 in the base image so the shell read fails.
  Using a named longrun service bypasses that shutdown path entirely.
- **AppArmor updated** — added `/etc/s6-overlay/**` read and
  `/run/s6*/**` read-write rules so the S6v3 runtime state directories are
  accessible within the add-on's AppArmor sandbox.
- **Fixed `webhook_url` schema** — changed from `"url?"` to `"str?"` so
  leaving the field blank no longer causes `expected a URL` validation errors
  when saving add-on configuration.
- **Fixed base image tag** — corrected `build.yaml` and `Dockerfile` to use
  the full arch-prefixed Alpine tag
  (`ghcr.io/home-assistant/{arch}-base-python:3.12-alpine3.20`), resolving
  the `image not found` build error.
- **Fixed UTC date mismatch in stats** — `get_stats()` and `get_camera_stats()`
  now use `datetime.now(timezone.utc).date()` instead of `date.today()`,
  preventing incorrect "today" counts in US timezones after 5 pm UTC−5/−8.

### Improvements

- **Web 2FA UI** — a sanitised 6-digit input overlay appears automatically in
  the Blink Clips web panel whenever Blink requires a verification code; no
  more manual `/data/two_fa_code.txt` file editing.
- **HA Blink integration coexistence** — the add-on and the built-in HA Blink
  integration can run side-by-side without conflict.  They use independent API
  sessions and separate credential storage (`/data/auth_credentials.json` vs.
  HA's own storage); the add-on does not touch any Blink-integration entities.

## 2.0.0

### New features

- **Web library UI** — built-in Video.js media server (port 8099 / HA ingress sidebar panel)
  with clip grid, thumbnails, search, camera/date/source/tag filters, sort, starred filter,
  and a camera sidebar.
- **SQLite clip library** — all downloaded clips are indexed in `/data/clip_library.db`,
  enabling fast filtering, tag management, and starred clips.
- **Video.js player** — in-browser streaming with seek, fullscreen, PiP, loop,
  theater mode, autoplay-next, and configurable playback rates.
- **Bulk ZIP export** — select multiple clips and download them as a single ZIP archive.
- **Tag support** — add/remove freeform tags per clip; filter the library by tag.
- **Keyboard shortcuts** — Space/F/M/L/Esc/↑↓/←→ with a `?` help overlay.
- **Browser notifications** — opt-in desktop notifications when new clips arrive.
- **Activity heatmap** — 7-day clip count chart on the Status tab.
- **Event-driven instant download** — subscribe to HA `state_changed` events and
  trigger a fast-poll immediately when a Blink motion sensor fires.
- **Fast-poll mode** — configurable burst polling after motion events
  (`fast_poll_interval`, `fast_poll_duration`, `post_motion_delay`).
- **Daily digest** — scheduled HA notification summarising downloads and storage.
- **ZIP archiving** — compress clips older than a threshold into monthly ZIPs.
- **Minimum clip duration filter** — skip clips shorter than N seconds.
- **HA ingress panel** — automatic sidebar entry "Blink Clips" via `ingress: true`;
  all web UI API calls use the `X-Ingress-Path` prefix so ingress and direct access
  both work correctly.
- **Retry delay** — configurable `retry_delay` (base seconds, multiplied per attempt).

### Improvements

- `config.yaml`: added ingress, panel icon/title, `retry_delay` option, corrected
  `max_storage_gb` type to `float`, removed placeholder `image` field.
- `Dockerfile`: added `io.hass.*` OCI labels and `BUILD_ARCH` / `BUILD_VERSION` ARGs
  for multi-arch HA OS builds.
- `apparmor.txt`: added `/tmp/`, `/run/s6-linux-init-container-results/exitcode`,
  and `site-packages` paths required for Python and S6-overlay operation.
- `translations/en.yaml`: added `retry_delay` translation.
- Test coverage raised to 88 % across 245 tests; event_watcher coverage 98 %.

## 1.0.0 — Initial release

- Continuous polling for new Blink camera clips
- Organise by camera name and date
- Configurable filename format with `{camera}`, `{timestamp}`, `{date}`, `{time}`, `{id}` tokens
- Storage quota management and auto-retention policy
- Camera whitelist filtering
- Motion-only clip filter
- Time-window filter (e.g. nighttime only)
- Download JPEG thumbnails alongside clips (optional)
- Configurable concurrent downloads with retry/back-off
- Home Assistant persistent notifications
- HA custom event `blink_clip_downloaded` per clip
- Virtual sensor `sensor.blink_downloader_status`
- Webhook URL support
- Newline-delimited JSON clip manifest at `/data/clip_manifest.json`
- Statistics snapshot at `/data/stats.json`
- File-based 2FA code entry via `/data/two_fa_code.txt`
- Manual trigger via `/data/trigger_download`
- Cached auth tokens for restart-free operation
- Graceful shutdown on SIGTERM / SIGINT
