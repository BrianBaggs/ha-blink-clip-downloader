"""Tests for HAEventWatcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from blink_downloader.event_watcher import HAEventWatcher


# ------------------------------------------------------------------
# extract_blink_camera (pure static, no I/O)
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "entity_id,expected",
    [
        ("binary_sensor.blink_front_door_motion", "front door"),
        ("binary_sensor.blink_back_yard_motion", "back yard"),
        ("binary_sensor.blink_garage_motion", "garage"),
        # Not a Blink motion entity → None
        ("binary_sensor.smoke_detector", None),
        ("sensor.blink_front_door_motion", None),  # wrong prefix domain
        ("binary_sensor.blink_motion", None),       # no inner slug
        ("binary_sensor.blink__motion", None),      # empty slug
    ],
)
def test_extract_blink_camera(entity_id: str, expected: str | None) -> None:
    result = HAEventWatcher.extract_blink_camera(entity_id)
    assert result == expected


# ------------------------------------------------------------------
# _handle_state_changed — motion ON
# ------------------------------------------------------------------

def _make_watcher(
    cameras: list[str] | None = None,
    with_cleared: bool = False,
) -> tuple[HAEventWatcher, MagicMock, MagicMock | None]:
    cb = MagicMock()
    cb_cleared = MagicMock() if with_cleared else None
    w = HAEventWatcher(
        supervisor_token="tok",
        on_motion=cb,
        on_motion_cleared=cb_cleared,
        event_cameras=cameras or [],
    )
    return w, cb, cb_cleared


def _motion_event(entity_id: str, state: str) -> dict:
    return {
        "event_type": "state_changed",
        "data": {"entity_id": entity_id, "new_state": {"state": state}},
    }


def test_handle_motion_on_fires_callback() -> None:
    w, cb, _ = _make_watcher()
    w._handle_state_changed(_motion_event("binary_sensor.blink_front_door_motion", "on"))
    cb.assert_called_once_with("front door")


def test_handle_motion_off_fires_cleared_callback() -> None:
    w, cb, cb_cleared = _make_watcher(with_cleared=True)
    w._handle_state_changed(_motion_event("binary_sensor.blink_front_door_motion", "off"))
    cb.assert_not_called()
    cb_cleared.assert_called_once_with("front door")


def test_handle_motion_off_no_cleared_callback_is_safe() -> None:
    w, cb, _ = _make_watcher(with_cleared=False)
    # Should not raise even though no cleared callback is registered
    w._handle_state_changed(_motion_event("binary_sensor.blink_front_door_motion", "off"))
    cb.assert_not_called()


def test_handle_motion_state_unavailable_ignored() -> None:
    w, cb, _ = _make_watcher()
    w._handle_state_changed(_motion_event("binary_sensor.blink_front_door_motion", "unavailable"))
    cb.assert_not_called()


def test_handle_wrong_event_type_ignored() -> None:
    w, cb, _ = _make_watcher()
    event = {
        "event_type": "call_service",
        "data": {
            "entity_id": "binary_sensor.blink_front_door_motion",
            "new_state": {"state": "on"},
        },
    }
    w._handle_state_changed(event)
    cb.assert_not_called()


def test_handle_non_blink_entity_ignored() -> None:
    w, cb, _ = _make_watcher()
    w._handle_state_changed(_motion_event("binary_sensor.smoke_alarm", "on"))
    cb.assert_not_called()


def test_camera_whitelist_allows_matching() -> None:
    w, cb, _ = _make_watcher(cameras=["front door"])
    w._handle_state_changed(_motion_event("binary_sensor.blink_front_door_motion", "on"))
    cb.assert_called_once()


def test_camera_whitelist_blocks_non_matching() -> None:
    w, cb, _ = _make_watcher(cameras=["back yard"])
    w._handle_state_changed(_motion_event("binary_sensor.blink_front_door_motion", "on"))
    cb.assert_not_called()


def test_camera_whitelist_also_applies_to_cleared() -> None:
    w, cb, cb_cleared = _make_watcher(cameras=["back yard"], with_cleared=True)
    w._handle_state_changed(_motion_event("binary_sensor.blink_front_door_motion", "off"))
    cb_cleared.assert_not_called()


def test_empty_camera_list_allows_all() -> None:
    w, cb, _ = _make_watcher(cameras=[])
    for entity in [
        "binary_sensor.blink_cam_a_motion",
        "binary_sensor.blink_cam_b_motion",
    ]:
        w._handle_state_changed(_motion_event(entity, "on"))
    assert cb.call_count == 2


def test_handle_missing_new_state_ignored() -> None:
    w, cb, _ = _make_watcher()
    event = {
        "event_type": "state_changed",
        "data": {
            "entity_id": "binary_sensor.blink_front_door_motion",
            "new_state": None,
        },
    }
    w._handle_state_changed(event)
    cb.assert_not_called()


# ------------------------------------------------------------------
# stop
# ------------------------------------------------------------------

async def test_stop_closes_session() -> None:
    w, _, _ = _make_watcher()
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.close = AsyncMock()
    w._session = mock_session
    w._running = True

    await w.stop()

    assert w._running is False
    mock_session.close.assert_awaited_once()


async def test_stop_skips_already_closed_session() -> None:
    w, _, _ = _make_watcher()
    mock_session = MagicMock()
    mock_session.closed = True
    w._session = mock_session
    await w.stop()  # should not raise


# ------------------------------------------------------------------
# start — exits cleanly on CancelledError
# ------------------------------------------------------------------

async def test_start_exits_cleanly_on_cancel() -> None:
    import asyncio
    w, _, _ = _make_watcher()

    async def fake_connect_and_watch():
        raise asyncio.CancelledError()

    w._connect_and_watch = fake_connect_and_watch
    await w.start()
    assert w._running is True
