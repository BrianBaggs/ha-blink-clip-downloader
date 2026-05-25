# Changelog

## 2.3.0

### Bug fixes

- **Definitive fix for `s6-svscan: fatal: another instance of s6-svscan is
  already running` and `s6-linux-init (child): warning: s6-svscan failed to
  send a notification byte!`** — Root-cause identified by reading the actual
  HA Supervisor source code (`supervisor/apps/app.py`).

  **Root cause:** The HA Supervisor has two container-restart code paths:
  - `ContainerState.FAILED` → `stop(remove_container=True)` then fresh `run()`
    — creates a brand-new container with a clean writable layer.
  - Any other state (e.g. `UNHEALTHY`) → `container.restart()` — restarts the
    same container **in place**, preserving its writable layer.

  `/run` is part of the Docker container's writable overlay layer — it is
  **not** a tmpfs in Docker's default configuration.  When the Supervisor
  takes the `container.restart()` path, `/run/service/.s6-svscan/lock` from
  the previous s6-svscan run survives into the restarted container.
  s6-overlay's preinit (`s6-rmrf /run/service ...`) runs but the write is
  effectively a no-op because the kernel already released the lock when the
  previous process died — the file still exists.  The new s6-svscan then
  calls `lock_exnb()` on the file, gets `EWOULDBLOCK`, and prints
  `"another instance already running"`.  The container exits, the Supervisor
  restarts it in-place again, and the cycle repeats.

  **Fix:** `rootfs/run.sh` is now the container `ENTRYPOINT`.  It runs first
  as PID 1, unconditionally removes `/run/s6`, `/run/service`, and
  `/run/s6-rc*` (these are always recreated by s6-overlay's own preinit
  immediately after), then `exec`s the real `/init` so s6-overlay takes over
  as PID 1 and the startup proceeds normally.  The AppArmor profile already
  has `rw` on `/run/` so the deletion is permitted.

  **Other changes included in this release:**
  - Switched from `rootfs/etc/services.d/` (v2.2.0) to the canonical
    `rootfs/etc/s6-overlay/s6-rc.d/blink-downloader/` structure
    (`type`, `run`, `finish`, `dependencies.d/base`) used by all official
    hassio-addons.
  - `rootfs/etc/s6-overlay/s6-rc.d/user/contents.d/blink-downloader` empty
    marker registers the service in the user bundle.  **No `user/type` file**
    — the base image already ships one; a duplicate causes `s6-rc-compile`
    to fail.
  - `finish` script follows the `hassio-addons/app-example` pattern: records
    the exit code in `/run/s6-linux-init-container-results/exitcode` and
    calls `exec /run/s6/basedir/bin/halt` on SIGTERM or unexpected crash.

## 2.2.0

### Bug fixes

- **Fixed `s6-svscan: fatal: another instance of s6-svscan is already running`**
  — The `s6-rc.d/user/contents.d` bundle registration approach used in v2.1.x
  conflicts with the supervision tree the HA base image already owns.  Switched
  to the **`/etc/services.d/`** legacy service format, which S6-overlay v3
  supports via its backward-compatibility layer and does not touch the user
  bundle or start a second svscan.  Also added a `finish` script to the service
  directory that prevents rapid crash-restart loops (10 s back-off on unexpected
  exits).

- **Fixed "App not running — Start?" ingress loop** — The Python process was
  calling `sys.exit(1)` on configuration errors and returning immediately on
  Blink authentication failures.  Both killed the aiohttp web server, leaving
  port 8099 silent and causing HA ingress to report the add-on as not running.
  Three code-path changes fix this:

  1. **`__main__.py`** — removed `sys.exit(1)`.  On any `load_config()` error
     the process now creates a minimal `AppConfig` with `startup_error` set and
     continues into the normal app lifecycle.

  2. **`app.py` — startup-error mode** — when `startup_error` is set the web
     server starts as normal, the auth state is set to `"error"` (visible on
     the Status tab), and the process sleeps in a loop until SIGTERM rather than
     exiting.  HA ingress sees port 8099 up and the sidebar panel loads.

  3. **`app.py` — `_connect_with_retry()`** — replaces the bare `try/except`
     that returned on auth failure.  On `TwoFARequired` or any other Blink
     exception the add-on sends the HA notification, logs the error, waits
     `_reconnect_interval` seconds (default 60), and retries indefinitely.
     The process never exits between retries; the web server stays up the whole
     time.  SIGTERM is responded to promptly because the wait loop checks
     `_running` every second.

### Improvements

- Added `startup_error: str = ""` field to `AppConfig`; set by `__main__` when
  `load_config()` raises, consumed by `app.run()` to enter web-only mode.
- `_reconnect_interval` and `_startup_poll_interval` instance attributes on
  `BlinkClipDownloaderApp` (default 60 s and 1 s respectively) can be overridden
  in tests to keep the suite fast without patching `asyncio.sleep`.
- `services.d` `finish` script: logs exit code and adds a 10 s sleep before S6
  restarts the service on unexpected crashes.

## 2.1.2

### Bug fixes

- **Fixed `/init: exec: line 45: s6-overlay-suexec: Permission Denied`** —
  Root cause identified through tarball inspection of the HA base image:

  **Why this error occurs:**  `s6-overlay-suexec` is a *setuid-root* ELF
  binary whose real path inside the container is
  `/package/admin/s6-overlay-helpers-<version>/command/s6-overlay-suexec`.
  It is exposed via a two-hop symlink chain:
  `/command/s6-overlay-suexec` →
  `/package/admin/s6-overlay-helpers/command/s6-overlay-suexec` →
  real binary.  AppArmor resolves symlinks to their real path when checking
  `execve` permissions — so the `/command/** mrix,` rule that was already
  in the profile covered only the *symlink name*, not the *binary the kernel
  actually loads*.  The `Permission Denied` was AppArmor denying exec on
  `/package/admin/s6-overlay-helpers-*/command/s6-overlay-suexec`.

  **Fixes applied to `apparmor.txt`:**

  1. Added `/package/** mrix,` — covers all S6-overlay real binary paths
     (`s6-overlay-helpers`, `s6`, `s6-rc`, `s6-linux-init`, `execline`,
     `s6-portable-utils`, etc.) regardless of version number.

  2. Added Linux capabilities block:
     `capability setuid, setgid, chown, dac_override, fowner,
     net_bind_service` — `s6-overlay-suexec` is setuid root and calls
     `setresuid()`/`setresgid()` to switch UIDs; without `capability setuid`
     and `capability setgid` the kernel refuses the UID-switch even after
     the `execve` succeeds.

  3. Expanded runtime path coverage: `/run/service/** rwix,`,
     `/etc/services.d/**`, `/etc/cont-init.d/**`, `/etc/cont-finish.d/**`,
     `/etc/fix-attrs.d/**` — all paths the S6 startup sequence reads and
     executes from.

  4. Added broad `/bin/** mrix,`, `/usr/bin/** mrix,`, `/sbin/** mrix,`,
     `/lib/** mr,`, `/usr/lib/** mr,` — S6 supervision scripts invoke many
     Alpine utilities; without these the shell inside S6 service scripts
     could not execute basic commands.

  5. Removed over-specific `deny /etc/** w,` / `deny /bin/** wl,` /
     `deny /sbin/** wl,` deny rules that conflicted with the new broad
     execute rules.  The profile relies on AppArmor's default-deny posture
     for anything not explicitly allowed; the only retained `deny` is
     `deny /root/** rw,` to protect the root home directory.

## 2.1.1

### Bug fixes

- **Fixed `/bin/sh: can't open /init: Permission denied` — root cause found and
  eliminated** — Thorough research against HA OS 17.3 / Supervisor 2026.x revealed
  three compounding issues that together produced the error:

  1. **AppArmor profile was blocking S6's own init binary.**  HA Supervisor 2026.x
     enforces AppArmor more strictly than earlier versions.  The profile was missing
     explicit allow rules for `/init` (the S6-overlay ELF binary), the `/command/`
     directory (where S6v3 stores `with-contenv` and all supervision binaries),
     `/bin/sh`, `/bin/bash`, and the full S6 runtime state paths
     (`/run/s6/**`, `/run/s6-rc*/**`, `/run/service/**`,
     `/run/container_environment/**`).  Without `/init mrix,`, the kernel denied
     `open()` on the init binary and the error surfaced exactly as seen.
     All missing rules have been added to `apparmor.txt`.

  2. **Wrong `with-contenv` shebang path.**  The service `run` script used
     `#!/usr/bin/with-contenv bashio`.  The canonical, forward-compatible path in
     S6-overlay v3 HA base images is `#!/command/with-contenv bashio` — this is
     what every official HA add-on uses and what the base image's own AppArmor
     baseline expects.  Updated in both
     `rootfs/etc/s6-overlay/s6-rc.d/blink-downloader/run` and `rootfs/run.sh`.

  3. **Missing `dependencies.d/base` declaration.**  S6-overlay v3 requires each
     longrun service to contain an empty file at
     `s6-rc.d/<service>/dependencies.d/base` to declare that it must not start
     until the base bundle has fully initialised.  Without it the service could
     be launched before the container environment (including `SUPERVISOR_TOKEN`)
     was ready.  The file has been added.

- **Git execute bit set on service `run` script** — `git update-index
  --chmod=+x` is now applied to
  `rootfs/etc/s6-overlay/s6-rc.d/blink-downloader/run` and `rootfs/run.sh`
  so the execute permission is embedded in the repository (`100755`) and
  survives a clean clone without relying solely on the Dockerfile `chmod`.

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
