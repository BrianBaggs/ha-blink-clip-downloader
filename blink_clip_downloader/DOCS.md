# Blink Clip Downloader — Documentation

## Overview

This add-on continuously polls the Blink API for new camera clips and saves them to
your local storage (under `/share/blink-clips` by default), so you have a local
copy in addition to any cloud storage.

---

## Installation

1. In Home Assistant go to **Settings → Add-ons → Add-on Store**.
2. Click **⋮** (top-right) → **Repositories** → add  
   `https://github.com/yourusername/ha-blink-clip-downloader`
3. Refresh the page; find **Blink Clip Downloader** and click **Install**.
4. Open the **Configuration** tab, fill in your Blink credentials, and save.
5. Click **Start**.

---

## Two-Factor Authentication (2FA)

If your Blink account has 2FA enabled, the add-on will pause after the first login
attempt and log:

```
2FA required! Write your 6-digit code to: /data/two_fa_code.txt
```

Connect to your Home Assistant instance via SSH or the Terminal add-on and run:

```bash
echo "123456" > /data/blink_clip_downloader/two_fa_code.txt
```

Replace `123456` with the actual code from your authenticator app or SMS.  
The add-on will detect the file, complete the login, and delete the file automatically.

After a successful login the auth tokens are cached in
`/data/blink_clip_downloader/auth_credentials.json` and reused on subsequent starts.
You will only be prompted for 2FA again if the refresh token expires (typically 30+ days
of the add-on being stopped).

---

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `username` | _(required)_ | Blink account email |
| `password` | _(required)_ | Blink account password |
| `download_path` | `/share/blink-clips` | Where to save clips |
| `organize_by_camera` | `true` | Sub-folder per camera |
| `organize_by_date` | `true` | Sub-folder per date (`YYYY-MM-DD`) |
| `filename_format` | `{camera}_{timestamp}` | Clip filename template |
| `poll_interval` | `300` | Seconds between polls (30–3600) |
| `max_clips_per_poll` | `50` | Clips downloaded per cycle |
| `retention_days` | `30` | Auto-delete clips older than N days (0 = off) |
| `max_storage_gb` | `10` | Stop downloading when folder exceeds N GB (0 = unlimited) |
| `camera_filter` | `[]` | Only download from these cameras (empty = all) |
| `motion_only` | `false` | Only download motion-triggered clips |
| `time_window_start` | `""` | HH:MM — only download clips after this time |
| `time_window_end` | `""` | HH:MM — only download clips before this time |
| `download_thumbnails` | `false` | Save JPEG thumbnail alongside each clip |
| `concurrent_downloads` | `3` | Parallel downloads (1–10) |
| `retry_attempts` | `3` | Retries per failed download |
| `notify_ha` | `true` | HA persistent notification when clips arrive |
| `ha_notification_title` | `"Blink Clip Downloaded"` | Notification title |
| `webhook_url` | `""` | POST clip metadata here after each download |
| `create_clip_manifest` | `true` | Append clip metadata to `/data/clip_manifest.json` |
| `log_level` | `info` | `debug`, `info`, `warning`, or `error` |

### Filename format tokens

| Token | Example | Meaning |
|-------|---------|---------|
| `{camera}` | `Front_Door` | Camera name (special chars replaced with `_`) |
| `{timestamp}` | `20240615_083000` | `YYYYMMDD_HHMMSS` in UTC |
| `{date}` | `2024-06-15` | Date part only |
| `{time}` | `083000` | Time part only |
| `{id}` | `99001` | Blink clip ID |

---

## Home Assistant Integration

### Sensor

The add-on writes a virtual sensor after every poll:

- **entity_id**: `sensor.blink_downloader_status`
- **state**: total clips downloaded (lifetime)
- **attributes**: `total_downloaded`, `session_downloads`, `used_mb`, `free_gb`,
  `last_download`

You can use this in automations or display it on a dashboard.

### Events

For every downloaded clip the add-on fires the event `blink_clip_downloaded` with:

```json
{
  "clip_id": "99001",
  "camera": "Front Door",
  "path": "/share/blink-clips/Front_Door/2024-06-15/Front_Door_20240615_083000.mp4",
  "timestamp": "2024-06-15T08:30:00+00:00",
  "size_bytes": 1048576,
  "duration": 5,
  "source": "pir"
}
```

Example automation to play a TTS alert when a doorbell clip arrives:

```yaml
alias: Announce doorbell clip
trigger:
  - platform: event
    event_type: blink_clip_downloaded
    event_data:
      camera: Doorbell
action:
  - service: tts.speak
    data:
      message: "Doorbell clip just downloaded"
```

---

## Manual Trigger

Touch the file `/data/blink_clip_downloader/trigger_download` to force an immediate
poll without waiting for the next interval:

```bash
touch /data/blink_clip_downloader/trigger_download
```

The add-on checks for this file every 10 seconds and deletes it after triggering.

---

## Accessing Your Clips

Downloaded clips are saved under the `share` folder, which is accessible via:

- **Media Browser** in the Home Assistant UI (Settings → Media)
- **Samba share** if the Samba add-on is installed
- **SSH** at `/share/blink-clips/`

---

## Data Files

| Path | Description |
|------|-------------|
| `/data/auth_credentials.json` | Cached Blink auth tokens (do not edit) |
| `/data/downloaded_clips.json` | Tracker of downloaded clip IDs |
| `/data/clip_manifest.json` | Newline-delimited JSON log of all downloads |
| `/data/stats.json` | Latest statistics snapshot |
| `/data/two_fa_code.txt` | Write your 2FA code here when prompted |
| `/data/trigger_download` | Touch to force an immediate poll |

---

## Troubleshooting

**Clips are not being downloaded**
- Check the add-on log for authentication errors.
- Verify your Blink credentials are correct.
- Ensure `/share/` is writable (the add-on requires `share:rw` in its mapping).

**2FA loop keeps triggering**
- Your refresh token may have expired. Delete `/data/auth_credentials.json` and restart.

**Storage keeps filling up**
- Lower `retention_days` or `max_storage_gb`.
- Consider adding cameras to `camera_filter` to limit which cameras are archived.

**Clips from only one camera are downloading**
- Check `camera_filter` — make sure the names match exactly (case-insensitive).
