"""Tests for blink_downloader.app."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blink_downloader.app import BlinkClipDownloaderApp, STATS_FILE, TRIGGER_FILE
from blink_downloader.downloader import TwoFARequired


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app(base_config):
    a = BlinkClipDownloaderApp(base_config)
    # Replace heavy collaborators with lightweight mocks.
    a._downloader.connect = AsyncMock()
    a._downloader.disconnect = AsyncMock()
    a._downloader.download_new_clips = AsyncMock(return_value=[])
    a._notifier.notify = AsyncMock(return_value=True)
    a._notifier.fire_event = AsyncMock(return_value=True)
    a._notifier.update_sensor = AsyncMock(return_value=True)
    a._notifier.call_webhook = AsyncMock(return_value=True)
    a._notifier.close = AsyncMock()
    a._storage.apply_retention_policy = MagicMock(return_value=0)
    a._storage.is_over_quota = MagicMock(return_value=False)
    a._storage.disk_stats = MagicMock(return_value={"used_mb": 1.0, "free_gb": 99.0})
    return a


# ---------------------------------------------------------------------------
# _poll_cycle
# ---------------------------------------------------------------------------


async def test_poll_cycle_no_new_clips(app):
    await app._poll_cycle()
    app._downloader.download_new_clips.assert_awaited_once()
    app._notifier.notify.assert_not_awaited()


async def test_poll_cycle_with_new_clips(app):
    clips = [
        {
            "id": "1",
            "camera": "Porch",
            "path": "/share/blink-clips/1.mp4",
            "timestamp": "2024-06-01T08:30:00+00:00",
            "size_bytes": 1024,
        }
    ]
    app._downloader.download_new_clips = AsyncMock(return_value=clips)

    await app._poll_cycle()

    app._notifier.notify.assert_awaited_once()
    assert app._session_downloads == 1


async def test_poll_cycle_quota_exceeded_skips_download(app):
    app._storage.is_over_quota = MagicMock(return_value=True)

    await app._poll_cycle()

    app._downloader.download_new_clips.assert_not_awaited()
    app._notifier.notify.assert_awaited_once()
    notify_call = app._notifier.notify.call_args
    assert "quota" in notify_call[0][0].lower() or "storage" in notify_call[0][0].lower()


async def test_poll_cycle_calls_retention(app):
    await app._poll_cycle()
    app._storage.apply_retention_policy.assert_called_once()


# ---------------------------------------------------------------------------
# _on_clips_downloaded
# ---------------------------------------------------------------------------


async def test_on_clips_downloaded_fires_event_per_clip(app):
    clips = [
        {"id": "a", "camera": "Cam1", "path": "/p/a.mp4", "timestamp": "t", "size_bytes": 10},
        {"id": "b", "camera": "Cam2", "path": "/p/b.mp4", "timestamp": "t", "size_bytes": 20},
    ]
    await app._on_clips_downloaded(clips)
    assert app._notifier.fire_event.await_count == 2


async def test_on_clips_downloaded_lists_cameras_in_notification(app):
    clips = [
        {"id": "1", "camera": "Alpha", "path": "/x", "timestamp": "t", "size_bytes": 1},
        {"id": "2", "camera": "Beta", "path": "/y", "timestamp": "t", "size_bytes": 1},
    ]
    await app._on_clips_downloaded(clips)
    notify_msg = app._notifier.notify.call_args[0][0]
    assert "Alpha" in notify_msg
    assert "Beta" in notify_msg


async def test_on_clips_downloaded_updates_sensor(app):
    clips = [{"id": "1", "camera": "C", "path": "/p", "timestamp": "t", "size_bytes": 5}]
    await app._on_clips_downloaded(clips)
    app._notifier.update_sensor.assert_awaited_once()
    entity_id = app._notifier.update_sensor.call_args[0][0]
    assert entity_id == "sensor.blink_downloader_status"


async def test_on_clips_downloaded_calls_webhook(app):
    clips = [{"id": "1", "camera": "C", "path": "/p", "timestamp": "t", "size_bytes": 5}]
    await app._on_clips_downloaded(clips)
    app._notifier.call_webhook.assert_awaited_once()


async def test_on_clips_downloaded_appends_manifest(app):
    app._config.create_clip_manifest = True
    app._manifest.append = MagicMock()
    clips = [{"id": "1", "camera": "C", "path": "/p", "timestamp": "t", "size_bytes": 5}]
    await app._on_clips_downloaded(clips)
    app._manifest.append.assert_called_once_with(clips[0])


async def test_on_clips_downloaded_skips_manifest_when_disabled(app):
    app._config.create_clip_manifest = False
    app._manifest.append = MagicMock()
    clips = [{"id": "1", "camera": "C", "path": "/p", "timestamp": "t", "size_bytes": 5}]
    await app._on_clips_downloaded(clips)
    app._manifest.append.assert_not_called()


# ---------------------------------------------------------------------------
# _write_stats
# ---------------------------------------------------------------------------


async def test_write_stats_creates_file(app, tmp_path):
    stats_path = tmp_path / "stats.json"
    with patch("blink_downloader.app.STATS_FILE", stats_path):
        await app._write_stats()

    data = json.loads(stats_path.read_text())
    assert "last_poll" in data
    assert "total_downloaded" in data
    assert "disk" in data


async def test_write_stats_handles_oserror(app, tmp_path):
    # Should not raise even if the file can't be written.
    with patch("blink_downloader.app.STATS_FILE", Path("/nonexistent/deep/stats.json")):
        await app._write_stats()  # no exception


# ---------------------------------------------------------------------------
# _wait_with_trigger_check
# ---------------------------------------------------------------------------


async def test_trigger_file_causes_early_return(app, tmp_path):
    trigger = tmp_path / "trigger"
    trigger.write_text("")
    app._config.poll_interval = 300
    app._running = True

    with patch("blink_downloader.app.TRIGGER_FILE", trigger):
        await app._wait_with_trigger_check()

    assert not trigger.exists()


async def test_no_trigger_waits_full_interval(app):
    # Use a very short interval so the test is fast.
    app._config.poll_interval = 0
    app._running = True
    # Should return quickly without error.
    await app._wait_with_trigger_check()


async def test_running_false_exits_wait_early(app):
    app._config.poll_interval = 300
    app._running = False
    # Should return immediately because _running is False.
    await app._wait_with_trigger_check()


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


async def test_shutdown_disconnects_and_saves_tracker(app):
    app._tracker.save = MagicMock()

    await app._shutdown()

    app._downloader.disconnect.assert_awaited_once()
    app._notifier.close.assert_awaited_once()
    app._tracker.save.assert_called_once()


# ---------------------------------------------------------------------------
# run() – 2FA failure path
# ---------------------------------------------------------------------------


async def test_run_2fa_required_sends_notification_and_returns(app):
    app._downloader.connect = AsyncMock(side_effect=TwoFARequired("needs code"))
    app._storage.ensure_directory = MagicMock()

    await app.run()

    app._notifier.notify.assert_awaited_once()
    title = app._notifier.notify.call_args.kwargs.get("title", "")
    assert "2FA" in title


# ---------------------------------------------------------------------------
# run() – connect error path
# ---------------------------------------------------------------------------


async def test_run_generic_connect_error_returns(app):
    app._downloader.connect = AsyncMock(side_effect=RuntimeError("network down"))
    app._storage.ensure_directory = MagicMock()

    await app.run()

    # Should have returned without calling download_new_clips
    app._downloader.download_new_clips.assert_not_awaited()


# ---------------------------------------------------------------------------
# run() – single successful iteration
# ---------------------------------------------------------------------------


async def test_run_one_iteration_then_stop(app, tmp_path):
    """run() polls once then exits because _running is set to False."""
    app._storage.ensure_directory = MagicMock()
    # Give the tracker a writable file so _shutdown() can save it.
    from blink_downloader.tracker import ClipTracker
    app._tracker = ClipTracker(tmp_path / "tracker.json")
    poll_count = 0

    async def _fake_poll():
        nonlocal poll_count
        poll_count += 1
        app._running = False  # Stop after first cycle

    app._poll_cycle = _fake_poll
    app._wait_with_trigger_check = AsyncMock()

    await app.run()

    assert poll_count == 1
    app._downloader.connect.assert_awaited_once()
    app._downloader.disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# Signal handler
# ---------------------------------------------------------------------------


def test_handle_shutdown_sets_running_false(app):
    app._running = True
    app._handle_shutdown()
    assert app._running is False


# ---------------------------------------------------------------------------
# Fast-poll / motion helpers
# ---------------------------------------------------------------------------


import time as _time


def test_on_blink_motion_sets_fast_poll_until(app):
    app._config.fast_poll_duration = 60
    before = _time.monotonic()
    app._on_blink_motion("Front Door")
    assert app._fast_poll_until >= before + 59


def test_activate_fast_poll_sets_fast_poll_until(app):
    app._config.fast_poll_duration = 30
    before = _time.monotonic()
    app._activate_fast_poll()
    assert app._fast_poll_until >= before + 29


def test_on_blink_motion_cleared_schedules_timer(app):
    """_on_blink_motion_cleared should call loop.call_later without raising."""
    import asyncio
    called_with = {}
    loop = asyncio.get_event_loop()
    original = loop.call_later

    def fake_call_later(delay, callback, *args):
        called_with["delay"] = delay
        called_with["callback"] = callback
        return original(delay, callback, *args)

    loop.call_later = fake_call_later
    app._config.post_motion_delay = 15
    try:
        app._on_blink_motion_cleared("Garage")
    finally:
        loop.call_later = original

    assert called_with.get("delay") == 15
    assert called_with.get("callback") == app._activate_fast_poll
