"""Tests for blink_downloader.downloader."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blink_downloader.downloader import BlinkDownloader, TwoFARequired
from blink_downloader.storage import StorageManager
from blink_downloader.tracker import ClipTracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def storage(tmp_path):
    s = StorageManager(
        base_path=tmp_path / "clips",
        max_storage_gb=10,
        retention_days=30,
        organize_by_camera=True,
        organize_by_date=True,
        filename_format="{camera}_{timestamp}",
    )
    s.ensure_directory()
    return s


@pytest.fixture
def tracker(tmp_path):
    return ClipTracker(tmp_path / "tracker.json")


@pytest.fixture
def dl(base_config, storage, tracker):
    return BlinkDownloader(base_config, storage, tracker)


# ---------------------------------------------------------------------------
# _apply_filters
# ---------------------------------------------------------------------------


def test_filter_by_camera_whitelist(dl, sample_clip):
    dl._config.camera_filter = ["Front Door"]
    clips = [
        {**sample_clip, "id": 1, "device_name": "Front Door"},
        {**sample_clip, "id": 2, "device_name": "Backyard"},
    ]
    result = dl._apply_filters(clips)
    assert len(result) == 1
    assert result[0]["device_name"] == "Front Door"


def test_filter_camera_case_insensitive(dl, sample_clip):
    dl._config.camera_filter = ["front door"]
    clips = [{**sample_clip, "device_name": "Front Door"}]
    result = dl._apply_filters(clips)
    assert len(result) == 1


def test_no_camera_filter_keeps_all(dl, sample_clip):
    dl._config.camera_filter = []
    clips = [
        {**sample_clip, "id": 1, "device_name": "A"},
        {**sample_clip, "id": 2, "device_name": "B"},
    ]
    assert len(dl._apply_filters(clips)) == 2


def test_motion_only_filter(dl, sample_clip):
    dl._config.motion_only = True
    clips = [
        {**sample_clip, "id": 1, "source": "pir"},
        {**sample_clip, "id": 2, "source": "liveview"},
        {**sample_clip, "id": 3, "source": ""},
    ]
    result = dl._apply_filters(clips)
    assert len(result) == 1
    assert result[0]["id"] == 1


def test_motion_only_false_keeps_all(dl, sample_clip):
    dl._config.motion_only = False
    clips = [
        {**sample_clip, "id": 1, "source": "pir"},
        {**sample_clip, "id": 2, "source": "liveview"},
    ]
    assert len(dl._apply_filters(clips)) == 2


def test_time_window_filter_in_window(dl, sample_clip):
    dl._config.time_window_start = "08:00"
    dl._config.time_window_end = "20:00"
    # sample_clip created_at = 08:30 UTC → inside window
    clips = [sample_clip]
    assert len(dl._apply_filters(clips)) == 1


def test_time_window_filter_outside_window(dl, sample_clip):
    dl._config.time_window_start = "22:00"
    dl._config.time_window_end = "06:00"
    # sample_clip at 08:30 → outside 22:00-06:00 window
    clips = [sample_clip]
    assert len(dl._apply_filters(clips)) == 0


def test_time_window_invalid_timestamp_keeps_clip(dl):
    dl._config.time_window_start = "08:00"
    dl._config.time_window_end = "20:00"
    clip = {"id": 1, "device_name": "Cam", "created_at": "not-a-date"}
    result = dl._apply_filters([clip])
    assert len(result) == 1


# ---------------------------------------------------------------------------
# _resolve_url
# ---------------------------------------------------------------------------


def test_resolve_url_absolute_unchanged(dl):
    dl._blink = MagicMock()
    assert (
        dl._resolve_url("https://example.com/clip.mp4")
        == "https://example.com/clip.mp4"
    )


def test_resolve_url_relative_uses_base_url(dl):
    mock_blink = MagicMock()
    mock_blink.urls.base_url = "https://rest-prod.immedia-semi.com"
    dl._blink = mock_blink
    result = dl._resolve_url("/api/v1/clip.mp4")
    assert result == "https://rest-prod.immedia-semi.com/api/v1/clip.mp4"


def test_resolve_url_fallback_when_no_blink(dl):
    dl._blink = None
    result = dl._resolve_url("/clip.mp4")
    assert "immedia-semi.com" in result


# ---------------------------------------------------------------------------
# _stream_to_file
# ---------------------------------------------------------------------------


async def test_stream_to_file_writes_content(dl, tmp_path):
    dest = tmp_path / "clip.mp4"
    content = b"fake video" * 1000

    async def _iter_chunks(chunk_size):
        yield content

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.content.iter_chunked = _iter_chunks
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.closed = False
    dl._session = mock_session

    mock_blink = MagicMock()
    mock_blink.auth.header = {"Authorization": "Bearer tok"}
    dl._blink = mock_blink

    size = await dl._stream_to_file("https://host/clip.mp4", dest)
    assert size == len(content)
    assert dest.read_bytes() == content


async def test_stream_to_file_non_200_returns_none(dl, tmp_path):
    dest = tmp_path / "clip.mp4"

    mock_resp = AsyncMock()
    mock_resp.status = 403
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.closed = False
    dl._session = mock_session
    dl._blink = MagicMock()
    dl._blink.auth.header = {}

    result = await dl._stream_to_file("https://host/clip.mp4", dest)
    assert result is None


async def test_stream_to_file_deletes_partial_on_failure(dl, tmp_path):
    import aiohttp as _aiohttp

    dest = tmp_path / "clip.mp4"
    dl._config.retry_attempts = 1
    dl._config.retry_delay = 0.0

    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=_aiohttp.ClientError("boom"))
    mock_session.closed = False
    dl._session = mock_session
    dl._blink = MagicMock()
    dl._blink.auth.header = {}

    # Create partial file to simulate incomplete prior download
    dest.write_bytes(b"partial")
    result = await dl._stream_to_file("https://host/clip.mp4", dest)
    assert result is None
    assert not dest.exists()


# ---------------------------------------------------------------------------
# download_new_clips
# ---------------------------------------------------------------------------


async def test_download_new_clips_skips_already_tracked(dl, tracker, sample_clip):
    tracker.mark_downloaded(str(sample_clip["id"]))
    dl._tracker = tracker

    dl._blink = MagicMock()
    with patch.object(dl, "_fetch_clip_list", AsyncMock(return_value=[sample_clip])):
        results = await dl.download_new_clips()

    assert results == []


async def test_download_new_clips_respects_max_clips(dl, sample_clip):
    dl._config.max_clips_per_poll = 2
    dl._blink = MagicMock()
    # 5 new clips, but limit is 2
    clips = [{**sample_clip, "id": i} for i in range(1, 6)]

    downloaded = []

    async def _fake_download(clip, sem):
        downloaded.append(clip["id"])
        return {"id": str(clip["id"]), "camera": "Cam", "path": "/x", "timestamp": "t"}

    with (
        patch.object(dl, "_fetch_clip_list", AsyncMock(return_value=clips)),
        patch.object(dl, "_download_clip", side_effect=_fake_download),
    ):
        await dl.download_new_clips()

    assert len(downloaded) == 2


async def test_download_new_clips_no_clips(dl):
    dl._blink = MagicMock()
    with patch.object(dl, "_fetch_clip_list", AsyncMock(return_value=[])):
        results = await dl.download_new_clips()
    assert results == []


# ---------------------------------------------------------------------------
# 2FA waiting
# ---------------------------------------------------------------------------


async def test_handle_2fa_reads_code_from_file(dl, tmp_path):
    two_fa_path = tmp_path / "2fa.txt"
    two_fa_path.write_text("123456")
    dl._blink = AsyncMock()
    dl._blink.send_2fa_code = AsyncMock()
    dl._config.two_fa_timeout = 30.0

    with patch("blink_downloader.downloader.TWO_FA_FILE", two_fa_path):
        await dl._handle_2fa()

    dl._blink.send_2fa_code.assert_awaited_once_with("123456")
    assert not two_fa_path.exists()


async def test_handle_2fa_times_out(dl, tmp_path):
    missing_file = tmp_path / "no_2fa.txt"
    dl._blink = AsyncMock()
    dl._config.two_fa_timeout = 0.1  # extremely short timeout

    with patch("blink_downloader.downloader.TWO_FA_FILE", missing_file):
        with pytest.raises(TwoFARequired):
            await dl._handle_2fa()


# ---------------------------------------------------------------------------
# connect() — happy path (cached credentials)
# ---------------------------------------------------------------------------


async def test_connect_uses_cached_credentials(dl, tmp_path):
    """connect() merges cached auth data into the login_data dict."""
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(json.dumps({"token": "cached_token", "host": "rest-us"}))

    mock_blink = AsyncMock()
    mock_blink.start = AsyncMock()
    mock_blink.account_id = 42
    mock_blink.auth = MagicMock()
    mock_blink.auth.login_attributes = {"token": "cached_token"}

    with (
        patch("blink_downloader.downloader.AUTH_FILE", auth_file),
        patch("blink_downloader.downloader.Blink", return_value=mock_blink),
        patch("blink_downloader.downloader.Auth") as MockAuth,
    ):
        await dl.connect()

    # Auth was called with merged login_data including the cached token
    call_kwargs = MockAuth.call_args[1]
    assert call_kwargs["login_data"]["token"] == "cached_token"


async def test_connect_proceeds_without_cached_file(dl, tmp_path):
    """connect() works fine when no auth cache file exists."""
    missing_auth = tmp_path / "no_auth.json"

    mock_blink = AsyncMock()
    mock_blink.start = AsyncMock()
    mock_blink.account_id = 1
    mock_blink.auth = MagicMock()
    mock_blink.auth.login_attributes = {}

    with (
        patch("blink_downloader.downloader.AUTH_FILE", missing_auth),
        patch("blink_downloader.downloader.Blink", return_value=mock_blink),
        patch("blink_downloader.downloader.Auth") as MockAuth,
    ):
        await dl.connect()

    call_kwargs = MockAuth.call_args[1]
    assert call_kwargs["login_data"]["username"] == "test@example.com"


# ---------------------------------------------------------------------------
# _fetch_clip_list — pagination
# ---------------------------------------------------------------------------


async def test_fetch_clip_list_paginates(dl, sample_clip):
    """_fetch_clip_list fetches page 1 when page 0 is full (_PAGE_SIZE=25 items)."""
    full_page = [{**sample_clip, "id": i} for i in range(25)]

    resp_page0 = AsyncMock()
    resp_page0.status = 200
    resp_page0.json = AsyncMock(return_value={"media": full_page})

    resp_page1 = AsyncMock()
    resp_page1.status = 200
    resp_page1.json = AsyncMock(return_value={"media": []})

    dl._blink = MagicMock()
    dl._blink.account_id = 1

    with patch(
        "blink_downloader.downloader.blink_api.request_videos",
        side_effect=[resp_page0, resp_page1],
    ):
        result = await dl._fetch_clip_list(datetime.now(timezone.utc))

    assert len(result) == 25


async def test_fetch_clip_list_handles_api_error(dl):
    """Returns an empty list when the Blink API returns a non-200 status."""
    error_resp = AsyncMock()
    error_resp.status = 500

    dl._blink = MagicMock()
    with patch(
        "blink_downloader.downloader.blink_api.request_videos",
        return_value=error_resp,
    ):
        result = await dl._fetch_clip_list(datetime.now(timezone.utc))

    assert result == []


# ---------------------------------------------------------------------------
# _persist_auth
# ---------------------------------------------------------------------------


def test_persist_auth_writes_file(dl, tmp_path):
    auth_path = tmp_path / "auth.json"
    mock_blink = MagicMock()
    mock_blink.auth.login_attributes = {"token": "tok123", "host": "prod"}
    dl._blink = mock_blink

    with patch("blink_downloader.downloader.AUTH_FILE", auth_path):
        dl._persist_auth()

    data = json.loads(auth_path.read_text())
    assert data["token"] == "tok123"


def test_persist_auth_handles_exception(dl):
    """_persist_auth should not raise even if writing fails."""
    dl._blink = MagicMock()
    dl._blink.auth.login_attributes = None  # will cause json.dumps to fail

    with patch(
        "blink_downloader.downloader.AUTH_FILE", Path("/nonexistent/deep/auth.json")
    ):
        dl._persist_auth()  # no exception
