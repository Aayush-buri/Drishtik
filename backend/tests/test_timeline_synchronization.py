import pytest
from datetime import datetime, timedelta
import zoneinfo
import itertools

from app.forensics.timeline.synchronization import (
    EventObservation,
    CameraSyncResult,
    SynchronizationResult,
    synchronize_cameras
)

def test_1_two_camera_fixed_offset():
    obs1 = EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")))
    obs2 = EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 59, 0, tzinfo=zoneinfo.ZoneInfo("UTC")))

    res = synchronize_cameras([obs1, obs2], reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 60.0
    assert res.camera_results["REF"].offset_seconds == 0.0

def test_2_three_camera_different_offsets():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 55, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="B", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 10, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 300.0
    assert res.camera_results["B"].offset_seconds == -600.0

def test_3_multiple_events_same_offset():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 50, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="REF", event_id="E2", timestamp=datetime(2023, 1, 1, 13, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E2", timestamp=datetime(2023, 1, 1, 12, 50, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 600.0
    assert res.camera_results["A"].matched_observations_count == 2
    assert res.camera_results["A"].inlier_observations_count == 2
    assert res.camera_results["A"].sync_confidence == 1.0

def test_4_inconsistent_outlier_rejected():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 58, 20, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="REF", event_id="E2", timestamp=datetime(2023, 1, 1, 13, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E2", timestamp=datetime(2023, 1, 1, 12, 58, 20, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="REF", event_id="E3", timestamp=datetime(2023, 1, 1, 14, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E3", timestamp=datetime(2023, 1, 1, 13, 58, 20, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="REF", event_id="E4", timestamp=datetime(2023, 1, 1, 15, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E4", timestamp=datetime(2023, 1, 1, 12, 13, 21, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 100.0
    assert res.camera_results["A"].matched_observations_count == 4
    assert res.camera_results["A"].inlier_observations_count == 3
    assert res.camera_results["A"].sync_confidence == 0.75
    assert any("outlier" in w.lower() for w in res.camera_results["A"].warnings)

def test_5_reference_camera_offset_zero():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 50, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["REF"].offset_seconds == 0.0
    assert res.camera_results["REF"].sync_confidence == 1.0

def test_6_utc_normalization_across_timezones():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 15, 30, 0), timezone="Asia/Kolkata"),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 10, 0, 0), timezone="UTC"),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 0.0

def test_7_aware_timestamps_preserve_instant():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 10, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 10, 0, 0, tzinfo=zoneinfo.ZoneInfo("Europe/London"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 0.0

def test_8_missing_invalid_event_data_rejected():
    events = [
        EventObservation(camera_id="", event_id="E1", timestamp=datetime(2023, 1, 1, 10, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="REF", event_id="", timestamp=datetime(2023, 1, 1, 10, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert len(res.camera_results) == 0
    assert any("Missing camera ID" in w for w in res.warnings)

def test_9_insufficient_matched_observations():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E2", timestamp=datetime(2023, 1, 1, 11, 50, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds is None
    assert res.camera_results["A"].sync_confidence == 0.0
    assert any("insufficient matched events" in w.lower() for w in res.camera_results["A"].warnings)

def test_10_reversing_ordering_deterministic():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 50, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="REF", event_id="E2", timestamp=datetime(2023, 1, 1, 13, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E2", timestamp=datetime(2023, 1, 1, 12, 50, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="B", event_id="E2", timestamp=datetime(2023, 1, 1, 12, 55, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="B", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 55, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]

    results = []
    for p in itertools.permutations(events):
        res = synchronize_cameras(list(p), reference_camera_id="REF")
        # Ensure we check complete serialization-equivalent properties
        key = (
            res.camera_results["A"].offset_seconds,
            res.camera_results["B"].offset_seconds,
            [obs.synchronized_utc for obs in res.synchronized_observations]
        )
        results.append(key)

    assert all(r == results[0] for r in results)

def test_11_source_timestamps_unchanged():
    dt_str = "2023-01-01T12:00:00+00:00"
    dt = datetime.fromisoformat(dt_str)
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=dt),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 50, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert events[0].timestamp.isoformat() == dt_str

def test_12_synchronized_timestamps_mutually_aligned():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 50, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="B", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 15, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")

    sync_map = {obs.camera_id: obs.synchronized_utc for obs in res.synchronized_observations if obs.event_id == "E1"}
    assert sync_map["REF"] == sync_map["A"] == sync_map["B"]

def test_13_completely_inconsistent_observations_rejected():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 50, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="REF", event_id="E2", timestamp=datetime(2023, 1, 1, 13, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E2", timestamp=datetime(2023, 1, 1, 12, 30, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="REF", event_id="E3", timestamp=datetime(2023, 1, 1, 14, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E3", timestamp=datetime(2023, 1, 1, 13, 10, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]
    # Offsets are E1: 600s, E2: 1800s, E3: 3000s
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds is None
    assert res.camera_results["A"].sync_confidence == 0.0

def test_14_invalid_timezone_rejected():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 15, 30, 0), timezone="Invalid/Timezone"),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 10, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds is None
    assert any("Invalid explicitly supplied timezone" in w for w in res.camera_results["A"].warnings)

def test_15_naive_timestamp_no_timezone_rejected():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 15, 30, 0)),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 10, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds is None
    assert any("Naive timestamp without a supplied timezone is rejected" in w for w in res.camera_results["A"].warnings)

def test_16_valid_zero_offset_is_not_none():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 15, 30, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 15, 30, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 0.0
    assert res.camera_results["A"].offset_seconds is not None

