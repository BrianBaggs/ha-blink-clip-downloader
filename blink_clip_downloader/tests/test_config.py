"""Tests for blink_downloader.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from blink_downloader.config import _parse_config, load_config


# ---------------------------------------------------------------------------
# _parse_config
# ---------------------------------------------------------------------------


def test_minimal_valid_config():
    cfg = _parse_config({"username": "u@x.com", "password": "secret"})
    assert cfg.username == "u@x.com"
    assert cfg.password == "secret"
    assert cfg.poll_interval == 300
    assert cfg.retention_days == 30
    assert cfg.log_level == "info"
    assert cfg.camera_filter == []


def test_full_config(tmp_path):
    data = {
        "username": "user@example.com",
        "password": "p@ssw0rd",
        "download_path": str(tmp_path),
        "poll_interval": 120,
        "retention_days": 7,
        "max_storage_gb": 5.0,
        "camera_filter": ["Front Door", "Backyard"],
        "motion_only": True,
        "time_window_start": "22:00",
        "time_window_end": "06:00",
        "download_thumbnails": True,
        "concurrent_downloads": 4,
        "retry_attempts": 5,
        "notify_ha": False,
        "ha_notification_title": "My Title",
        "webhook_url": "https://hooks.example.com/blink",
        "create_clip_manifest": False,
        "log_level": "debug",
        "max_clips_per_poll": 200,
        "organize_by_camera": False,
        "organize_by_date": False,
        "filename_format": "{id}_{camera}",
    }
    cfg = _parse_config(data)
    assert cfg.poll_interval == 120
    assert cfg.retention_days == 7
    assert cfg.camera_filter == ["Front Door", "Backyard"]
    assert cfg.motion_only is True
    assert cfg.time_window_start == "22:00"
    assert cfg.download_thumbnails is True
    assert cfg.concurrent_downloads == 4
    assert cfg.webhook_url == "https://hooks.example.com/blink"
    assert cfg.organize_by_camera is False
    assert cfg.filename_format == "{id}_{camera}"


def test_missing_username_raises():
    with pytest.raises(ValueError, match="username"):
        _parse_config({"password": "p"})


def test_empty_username_raises():
    with pytest.raises(ValueError, match="username"):
        _parse_config({"username": "  ", "password": "p"})


def test_missing_password_raises():
    with pytest.raises(ValueError, match="password"):
        _parse_config({"username": "u"})


def test_poll_interval_too_low():
    with pytest.raises(ValueError, match="poll_interval"):
        _parse_config({"username": "u", "password": "p", "poll_interval": 5})


def test_poll_interval_too_high():
    with pytest.raises(ValueError, match="poll_interval"):
        _parse_config({"username": "u", "password": "p", "poll_interval": 9999})


def test_retention_days_negative():
    with pytest.raises(ValueError, match="retention_days"):
        _parse_config({"username": "u", "password": "p", "retention_days": -1})


def test_max_clips_out_of_range():
    with pytest.raises(ValueError, match="max_clips_per_poll"):
        _parse_config({"username": "u", "password": "p", "max_clips_per_poll": 0})


def test_unknown_log_level_defaults_to_info():
    cfg = _parse_config({"username": "u", "password": "p", "log_level": "verbose"})
    assert cfg.log_level == "info"


def test_camera_filter_strips_whitespace():
    cfg = _parse_config(
        {
            "username": "u",
            "password": "p",
            "camera_filter": ["  Front Door  ", " Backyard "],
        }
    )
    assert cfg.camera_filter == ["Front Door", "Backyard"]


def test_camera_filter_skips_empty_strings():
    cfg = _parse_config(
        {"username": "u", "password": "p", "camera_filter": ["", "  ", "Cam1"]}
    )
    assert cfg.camera_filter == ["Cam1"]


def test_concurrent_downloads_clamped():
    cfg = _parse_config({"username": "u", "password": "p", "concurrent_downloads": 999})
    assert cfg.concurrent_downloads == 10


def test_download_path_as_path_object(tmp_path):
    cfg = _parse_config(
        {"username": "u", "password": "p", "download_path": str(tmp_path)}
    )
    assert isinstance(cfg.download_path, Path)


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_from_file(options_file):
    cfg = load_config(options_file)
    assert cfg.username == "user@test.com"
    assert cfg.poll_interval == 120


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/options.json"))


def test_load_config_invalid_json(tmp_path):
    bad_file = tmp_path / "options.json"
    bad_file.write_text("{not valid json}")
    with pytest.raises(Exception):
        load_config(bad_file)


def test_post_motion_delay_default():
    cfg = _parse_config({"username": "u", "password": "p"})
    assert cfg.post_motion_delay == 30


def test_post_motion_delay_clamped_to_min():
    cfg = _parse_config({"username": "u", "password": "p", "post_motion_delay": 1})
    assert cfg.post_motion_delay == 5


def test_post_motion_delay_clamped_to_max():
    cfg = _parse_config({"username": "u", "password": "p", "post_motion_delay": 9999})
    assert cfg.post_motion_delay == 300


def test_post_motion_delay_custom():
    cfg = _parse_config({"username": "u", "password": "p", "post_motion_delay": 60})
    assert cfg.post_motion_delay == 60


# ---------------------------------------------------------------------------
# startup_error field
# ---------------------------------------------------------------------------


def test_startup_error_defaults_to_empty_string():
    """startup_error is empty on a successfully parsed config."""
    cfg = _parse_config({"username": "u", "password": "p"})
    assert cfg.startup_error == ""


def test_appconfig_startup_error_can_be_set_directly():
    """AppConfig can be constructed with startup_error for web-only mode."""
    from blink_downloader.config import AppConfig

    cfg = AppConfig(username="", password="", startup_error="options.json not found")
    assert cfg.startup_error == "options.json not found"
    assert cfg.username == ""


# ---------------------------------------------------------------------------
# download_local_storage (v2.5.5)
# ---------------------------------------------------------------------------


def test_download_local_storage_defaults_to_false():
    cfg = _parse_config({"username": "u", "password": "p"})
    assert cfg.download_local_storage is False


def test_download_local_storage_can_be_enabled():
    cfg = _parse_config(
        {"username": "u", "password": "p", "download_local_storage": True}
    )
    assert cfg.download_local_storage is True
