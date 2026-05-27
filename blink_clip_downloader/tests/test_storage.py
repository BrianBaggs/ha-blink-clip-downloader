"""Tests for blink_downloader.storage."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path


from blink_downloader.storage import StorageManager, _cleanup_empty_dirs, _safe_name


def make_storage(
    tmp_path: Path,
    base_path: Path | None = None,
    max_storage_gb: float = 1.0,
    retention_days: int = 30,
    organize_by_camera: bool = True,
    organize_by_date: bool = True,
    filename_format: str = "{camera}_{timestamp}",
) -> StorageManager:
    return StorageManager(
        base_path=base_path or tmp_path / "clips",
        max_storage_gb=max_storage_gb,
        retention_days=retention_days,
        organize_by_camera=organize_by_camera,
        organize_by_date=organize_by_date,
        filename_format=filename_format,
    )


TS = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# ensure_directory
# ---------------------------------------------------------------------------


def test_ensure_directory_creates_base(tmp_path):
    s = make_storage(tmp_path)
    base = tmp_path / "clips"
    assert not base.exists()
    s.ensure_directory()
    assert base.is_dir()


def test_ensure_directory_idempotent(tmp_path):
    s = make_storage(tmp_path)
    s.ensure_directory()
    s.ensure_directory()  # should not raise


# ---------------------------------------------------------------------------
# resolve_path
# ---------------------------------------------------------------------------


def test_resolve_path_full_organisation(tmp_path):
    s = make_storage(tmp_path)
    p = s.resolve_path("Front Door", TS, "clip123")
    assert p.suffix == ".mp4"
    assert "Front_Door" in str(p)
    assert "2024-06-15" in str(p)
    assert "20240615_103000" in p.name


def test_resolve_path_no_camera_org(tmp_path):
    s = make_storage(tmp_path, organize_by_camera=False, organize_by_date=True)
    p = s.resolve_path("Front Door", TS, "clip123")
    assert "Front_Door" not in str(p.parent)
    assert "2024-06-15" in str(p.parent)


def test_resolve_path_flat(tmp_path):
    s = make_storage(tmp_path, organize_by_camera=False, organize_by_date=False)
    p = s.resolve_path("Front Door", TS, "clip123")
    assert p.parent == tmp_path / "clips"


def test_resolve_path_custom_format_tokens(tmp_path):
    s = make_storage(
        tmp_path,
        filename_format="{id}_{date}",
        organize_by_camera=False,
        organize_by_date=False,
    )
    p = s.resolve_path("Cam", TS, "abc99")
    assert p.stem == "abc99_2024-06-15"


def test_resolve_path_thumbnail_extension(tmp_path):
    s = make_storage(tmp_path)
    p = s.resolve_path("Cam", TS, "1", extension=".jpg")
    assert p.suffix == ".jpg"


def test_safe_name_in_path(tmp_path):
    s = make_storage(tmp_path)
    p = s.resolve_path("Camera/With\\Specials!", TS, "1")
    assert "/" not in p.parent.name
    assert "\\" not in p.parent.name


# ---------------------------------------------------------------------------
# Quota
# ---------------------------------------------------------------------------


def test_used_bytes_empty(tmp_path):
    s = make_storage(tmp_path)
    s.ensure_directory()
    assert s.used_bytes() == 0


def test_used_bytes_sums_files(tmp_path):
    s = make_storage(tmp_path)
    s.ensure_directory()
    (tmp_path / "clips" / "a.mp4").write_bytes(b"x" * 1000)
    (tmp_path / "clips" / "b.mp4").write_bytes(b"y" * 500)
    assert s.used_bytes() == 1500


def test_is_over_quota_false_when_within(tmp_path):
    s = make_storage(tmp_path, max_storage_gb=1.0)
    s.ensure_directory()
    (tmp_path / "clips" / "small.mp4").write_bytes(b"x" * 100)
    assert not s.is_over_quota()


def test_is_over_quota_true_when_exceeded(tmp_path):
    # 1 byte quota → any file exceeds it
    s = make_storage(tmp_path, max_storage_gb=0.000000001)
    s.ensure_directory()
    (tmp_path / "clips" / "f.mp4").write_bytes(b"x" * 1000)
    assert s.is_over_quota()


def test_quota_zero_never_exceeded(tmp_path):
    s = make_storage(tmp_path, max_storage_gb=0)
    s.ensure_directory()
    (tmp_path / "clips" / "huge.mp4").write_bytes(b"x" * 10_000_000)
    assert not s.is_over_quota()


def test_bytes_remaining_unlimited(tmp_path):
    s = make_storage(tmp_path, max_storage_gb=0)
    assert s.bytes_remaining() > 0


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


def _age_file(path: Path, days_old: float) -> None:
    old_ts = time.time() - days_old * 86400
    os.utime(path, (old_ts, old_ts))


def test_retention_deletes_old_clips(tmp_path):
    s = make_storage(tmp_path, retention_days=7)
    s.ensure_directory()
    old = tmp_path / "clips" / "old.mp4"
    old.write_bytes(b"data")
    _age_file(old, 10)

    deleted = s.apply_retention_policy()
    assert deleted == 1
    assert not old.exists()


def test_retention_keeps_recent_clips(tmp_path):
    s = make_storage(tmp_path, retention_days=30)
    s.ensure_directory()
    recent = tmp_path / "clips" / "recent.mp4"
    recent.write_bytes(b"data")

    deleted = s.apply_retention_policy()
    assert deleted == 0
    assert recent.exists()


def test_retention_zero_keeps_all(tmp_path):
    s = make_storage(tmp_path, retention_days=0)
    s.ensure_directory()
    old = tmp_path / "clips" / "ancient.mp4"
    old.write_bytes(b"data")
    _age_file(old, 400)

    deleted = s.apply_retention_policy()
    assert deleted == 0
    assert old.exists()


def test_retention_removes_thumbnails_too(tmp_path):
    s = make_storage(tmp_path, retention_days=7)
    s.ensure_directory()
    clip = tmp_path / "clips" / "old.mp4"
    thumb = tmp_path / "clips" / "old.jpg"
    clip.write_bytes(b"c")
    thumb.write_bytes(b"t")
    _age_file(clip, 10)
    _age_file(thumb, 10)

    deleted = s.apply_retention_policy()
    assert deleted == 2


def test_retention_cleans_empty_dirs(tmp_path):
    s = make_storage(tmp_path, retention_days=7)
    subdir = tmp_path / "clips" / "2024-01-01"
    subdir.mkdir(parents=True)
    only_file = subdir / "clip.mp4"
    only_file.write_bytes(b"x")
    _age_file(only_file, 10)

    s.apply_retention_policy()
    assert not subdir.exists()


# ---------------------------------------------------------------------------
# disk_stats
# ---------------------------------------------------------------------------


def test_disk_stats_shape(tmp_path):
    s = make_storage(tmp_path)
    s.ensure_directory()
    stats = s.disk_stats()
    for key in ("used_bytes", "used_mb", "free_gb", "total_gb", "quota_gb"):
        assert key in stats


# ---------------------------------------------------------------------------
# _safe_name
# ---------------------------------------------------------------------------


def test_safe_name_alphanumeric():
    assert _safe_name("Camera01") == "Camera01"


def test_safe_name_replaces_slashes():
    assert "/" not in _safe_name("A/B")


def test_safe_name_preserves_dashes_dots():
    assert _safe_name("cam-01.outdoor") == "cam-01.outdoor"


def test_safe_name_empty_becomes_unknown():
    assert _safe_name("") == "unknown"
    assert _safe_name("!!!") == "unknown"


# ---------------------------------------------------------------------------
# _cleanup_empty_dirs
# ---------------------------------------------------------------------------


def test_cleanup_empty_dirs_removes_empties(tmp_path):
    empty = tmp_path / "a" / "b"
    empty.mkdir(parents=True)
    _cleanup_empty_dirs(tmp_path)
    assert not (tmp_path / "a").exists()


def test_cleanup_empty_dirs_keeps_non_empty(tmp_path):
    d = tmp_path / "a"
    d.mkdir()
    (d / "file.mp4").write_bytes(b"x")
    _cleanup_empty_dirs(tmp_path)
    assert d.exists()
