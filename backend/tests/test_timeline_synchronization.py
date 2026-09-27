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
    # Ref camera observes at 12:00:00
    # Cam A observes at 11:59:00
    # Offset of Cam A should be +60 seconds.
    obs1 = EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0))
    obs2 = EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 59, 0))

    res = synchronize_cameras([obs1, obs2], reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 60.0
    assert res.camera_results["REF"].offset_seconds == 0.0

def test_2_three_camera_different_offsets():
    # REF observes E1 at 12:00:00
    # A observes E1 at 11:55:00 (offset = +300s)
    # B observes E1 at 12:10:00 (offset = -600s)
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0)),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 55, 0)),
        EventObservation(camera_id="B", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 10, 0)),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 300.0
    assert res.camera_results["B"].offset_seconds == -600.0

def test_3_multiple_events_same_offset():
    # E1: REF 12:00, A 11:50 -> offset 600s
    # E2: REF 13:00, A 12:50 -> offset 600s
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0)),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 50, 0)),
        EventObservation(camera_id="REF", event_id="E2", timestamp=datetime(2023, 1, 1, 13, 0, 0)),
        EventObservation(camera_id="A", event_id="E2", timestamp=datetime(2023, 1, 1, 12, 50, 0)),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 600.0
    assert res.camera_results["A"].matched_observations_count == 2
    assert res.camera_results["A"].inlier_observations_count == 2
    assert res.camera_results["A"].sync_confidence == 1.0

def test_4_inconsistent_outlier_rejected():
    # E1: offset 100s
    # E2: offset 100s
    # E3: offset 100s
    # E4: offset 9999s (outlier)
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0)),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 58, 20)),
        EventObservation(camera_id="REF", event_id="E2", timestamp=datetime(2023, 1, 1, 13, 0, 0)),
        EventObservation(camera_id="A", event_id="E2", timestamp=datetime(2023, 1, 1, 12, 58, 20)),
        EventObservation(camera_id="REF", event_id="E3", timestamp=datetime(2023, 1, 1, 14, 0, 0)),
        EventObservation(camera_id="A", event_id="E3", timestamp=datetime(2023, 1, 1, 13, 58, 20)),
        EventObservation(camera_id="REF", event_id="E4", timestamp=datetime(2023, 1, 1, 15, 0, 0)),
        EventObservation(camera_id="A", event_id="E4", timestamp=datetime(2023, 1, 1, 12, 13, 21)),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 100.0
    assert res.camera_results["A"].matched_observations_count == 4
    assert res.camera_results["A"].inlier_observations_count == 3
    assert res.camera_results["A"].sync_confidence == 0.75
    assert any("outlier" in w.lower() for w in res.camera_results["A"].warnings)

def test_5_reference_camera_offset_zero():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0)),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 50, 0)),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["REF"].offset_seconds == 0.0
    assert res.camera_results["REF"].sync_confidence == 1.0

def test_6_utc_normalization_across_timezones():
    # REF observes in Kolkata (UTC+5:30) at 15:30
    # A observes in UTC at 10:00 (this is the EXACT SAME instant, so offset should be 0)
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 15, 30, 0), timezone="Asia/Kolkata"),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 10, 0, 0), timezone="UTC"),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 0.0

def test_7_aware_timestamps_preserve_instant():
    # REF observes with aware UTC timezone at 10:00:00
    # A observes with aware London timezone at 10:00:00 (Winter = UTC, offset = 0)
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 10, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 10, 0, 0, tzinfo=zoneinfo.ZoneInfo("Europe/London"))),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 0.0

def test_8_missing_invalid_event_data_rejected():
    events = [
        EventObservation(camera_id="", event_id="E1", timestamp=datetime(2023, 1, 1, 10, 0, 0)),
        EventObservation(camera_id="REF", event_id="", timestamp=datetime(2023, 1, 1, 10, 0, 0)),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert len(res.camera_results) == 0
    assert any("Missing camera ID" in w for w in res.warnings)

def test_9_insufficient_matched_observations():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0)),
        EventObservation(camera_id="A", event_id="E2", timestamp=datetime(2023, 1, 1, 11, 50, 0)),
    ]
    # They don't match on event_id, so A has 0 matches
    res = synchronize_cameras(events, reference_camera_id="REF")
    assert res.camera_results["A"].offset_seconds == 0.0
    assert res.camera_results["A"].sync_confidence == 0.0
    assert any("insufficient matched events" in w.lower() for w in res.camera_results["A"].warnings)

def test_10_reversing_ordering_deterministic():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0)),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 50, 0)),
        EventObservation(camera_id="REF", event_id="E2", timestamp=datetime(2023, 1, 1, 13, 0, 0)),
        EventObservation(camera_id="A", event_id="E2", timestamp=datetime(2023, 1, 1, 12, 50, 0)),
        EventObservation(camera_id="B", event_id="E2", timestamp=datetime(2023, 1, 1, 12, 55, 0)),
        EventObservation(camera_id="B", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 55, 0)),
    ]

    results = []
    for p in itertools.permutations(events):
        res = synchronize_cameras(list(p), reference_camera_id="REF")
        # Ensure we just grab the dict representation for equality check
        results.append((res.camera_results["A"].offset_seconds, res.camera_results["B"].offset_seconds))

    assert all(r == results[0] for r in results)

def test_11_source_timestamps_unchanged():
    dt_str = "2023-01-01T12:00:00"
    dt = datetime.fromisoformat(dt_str)
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=dt),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 50, 0)),
    ]
    synchronize_cameras(events, reference_camera_id="REF")
    assert events[0].timestamp.isoformat() == dt_str

def test_12_synchronized_timestamps_mutually_aligned():
    events = [
        EventObservation(camera_id="REF", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 0, 0)),
        EventObservation(camera_id="A", event_id="E1", timestamp=datetime(2023, 1, 1, 11, 50, 0)),
        EventObservation(camera_id="B", event_id="E1", timestamp=datetime(2023, 1, 1, 12, 15, 0)),
    ]
    res = synchronize_cameras(events, reference_camera_id="REF")

    # Calculate synchronized timestamps manually as expected by higher layer
    # T_c_sync = T_c + offset_c
    t_ref_sync = events[0].timestamp + timedelta(seconds=res.camera_results["REF"].offset_seconds)
    t_a_sync = events[1].timestamp + timedelta(seconds=res.camera_results["A"].offset_seconds)
    t_b_sync = events[2].timestamp + timedelta(seconds=res.camera_results["B"].offset_seconds)

    # All should be exactly aligned to 12:00:00
    assert t_ref_sync == t_a_sync == t_b_sync

