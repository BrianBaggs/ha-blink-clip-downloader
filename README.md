# Home Assistant Blink Clip Downloader

A Home Assistant OS add-on that continuously downloads Blink camera clips to your
local hard drive using [blinkpy](https://github.com/fronzbot/blinkpy).

## Add-ons

### [Blink Clip Downloader](blink_clip_downloader/DOCS.md)

Periodically polls the Blink API for new clips and saves them to `/share/blink-clips`
(or a path you configure). Supports per-camera organisation, retention policies, storage
quotas, Home Assistant notifications, and much more.

## Installation

1. In Home Assistant go to **Settings → Add-ons → Add-on Store**.
2. Click the three-dot menu (⋮) → **Repositories**.
3. Paste `https://github.com/yourusername/ha-blink-clip-downloader` and click **Add**.
4. Search for **Blink Clip Downloader** and click **Install**.
5. Fill in your Blink credentials and click **Save**, then **Start**.

## Support

Open an issue at <https://github.com/yourusername/ha-blink-clip-downloader/issues>.
