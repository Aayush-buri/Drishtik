import pytest
from datetime import datetime, timedelta
import zoneinfo
import math

from app.forensics.timeline.calibration import normalize_forensic_timeline, ClockModel, NormalizedTimestamp

def test_1_no_calibration_returns_original_instant():
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
    res = normalize_forensic_timeline(dt, None)
    assert res.normalized_timestamp == dt
    assert res.source_timestamp is dt
    assert not res.calibration_applied

def test_2_offset_only_calibration():
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
    model = ClockModel(offset_seconds=3600.0)
    res = normalize_forensic_timeline(dt, model)
    assert res.normalized_timestamp == dt + timedelta(seconds=3600)
    assert res.calibration_applied

def test_3_drift_only_calibration():
    ref = datetime(2023, 1, 1, 10, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")) # 2 hours after ref
    model = ClockModel(drift_scale=1.1, reference_timestamp=ref)
    res = normalize_forensic_timeline(dt, model)
    # 2 hours * 1.1 = 2.2 hours = 2 hours + 12 minutes
    expected = ref + timedelta(hours=2.2)
    assert res.normalized_timestamp == expected

def test_4_drift_offset_reference():
    ref = datetime(2023, 1, 1, 10, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
    model = ClockModel(drift_scale=1.1, offset_seconds=-60.0, reference_timestamp=ref)
    res = normalize_forensic_timeline(dt, model)
    expected = ref + timedelta(hours=2.2) - timedelta(seconds=60)
    assert res.normalized_timestamp == expected

def test_5_invalid_drift_scale_rejected():
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
    with pytest.raises(ValueError):
        normalize_forensic_timeline(dt, ClockModel(drift_scale=-1.0))
    with pytest.raises(ValueError):
        normalize_forensic_timeline(dt, ClockModel(drift_scale=float('inf')))

def test_6_non_1_drift_without_reference_rejected():
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
    with pytest.raises(ValueError, match="reference timestamp"):
        normalize_forensic_timeline(dt, ClockModel(drift_scale=1.1, reference_timestamp=None))

def test_7_positive_timezone_conversion():
    dt = datetime(2023, 1, 1, 12, 0, 0)
    model = ClockModel(source_timezone="UTC", target_timezone="Asia/Kolkata")
    res = normalize_forensic_timeline(dt, model)
    # UTC to UTC+5:30 -> target string should say 17:30
    assert res.normalized_timestamp.hour == 17
    assert res.normalized_timestamp.minute == 30

def test_8_negative_timezone_conversion():
    dt = datetime(2023, 1, 1, 12, 0, 0)
    model = ClockModel(source_timezone="UTC", target_timezone="America/New_York")
    res = normalize_forensic_timeline(dt, model)
    # New York is UTC-5 in winter
    assert res.normalized_timestamp.hour == 7

def test_9_iana_timezone():
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("Asia/Kolkata"))
    model = ClockModel(source_timezone="Asia/Kolkata", target_timezone="UTC")
    res = normalize_forensic_timeline(dt, model)
    assert res.normalized_timestamp.hour == 6
    assert res.normalized_timestamp.minute == 30

def test_10_source_timestamp_unchanged():
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
    dt_str = dt.isoformat()
    model = ClockModel(offset_seconds=100)
    res = normalize_forensic_timeline(dt, model)
    assert res.source_timestamp.isoformat() == dt_str

def test_11_microsecond_precision():
    dt = datetime(2023, 1, 1, 12, 0, 0, 123456, tzinfo=zoneinfo.ZoneInfo("UTC"))
    model = ClockModel(offset_seconds=0.0001)
    res = normalize_forensic_timeline(dt, model)
    assert res.normalized_timestamp.microsecond == 123556

def test_12_dst_aware_timezone():
    # US/Eastern EDT (summer) vs EST (winter)
    summer = datetime(2023, 7, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("America/New_York"))
    winter = datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("America/New_York"))

    model = ClockModel(source_timezone="America/New_York", target_timezone="UTC")
    res_s = normalize_forensic_timeline(summer, model)
    res_w = normalize_forensic_timeline(winter, model)

    # Summer offset is -4, so UTC is 16:00
    assert res_s.normalized_timestamp.hour == 16
    # Winter offset is -5, so UTC is 17:00
    assert res_w.normalized_timestamp.hour == 17

def test_13_calibration_provenance():
    dt = datetime(2023, 1, 1, 12, 0, 0)
    model = ClockModel(
        offset_seconds=10,
        calibration_method="MANUAL_SYNC",
        calibration_confidence=0.8,
        calibration_reason="Compared against verified external reference"
    )
    res = normalize_forensic_timeline(dt, model)
    assert res.confidence == 0.8
    assert any("manual_sync" in w.lower() for w in res.warnings)
    assert model.calibration_reason == "Compared against verified external reference"


def test_14_missing_timezone_explicit_warning():
    dt = datetime(2023, 1, 1, 12, 0, 0)
    model = ClockModel(offset_seconds=10, source_timezone=None)
    res = normalize_forensic_timeline(dt, model)
    assert any("timezone was not provided" in w for w in res.warnings)

def test_17_repeated_normalization_deterministic():
    dt = datetime(2023, 1, 1, 12, 0, 0)
    model = ClockModel(offset_seconds=123.456, source_timezone="UTC", target_timezone="Asia/Tokyo")
    res1 = normalize_forensic_timeline(dt, model)
    res2 = normalize_forensic_timeline(dt, model)
    assert res1.normalized_timestamp == res2.normalized_timestamp


def test_18_naive_reference_in_source_timezone_kolkata_to_utc():
    dt = datetime(2023, 1, 1, 12, 0, 0)
    ref = datetime(2023, 1, 1, 10, 0, 0)
    # T_camera is 12:00 in Asia/Kolkata
    # T_reference is 10:00 in Asia/Kolkata
    # delta is 2 hours.
    # Drift = 2.0 -> scaled delta is 4 hours.
    # T_normalized = T_reference (10:00 Kolkata) + 4 hours = 14:00 Kolkata.
    # Converted to UTC -> 14:00 - 5:30 = 08:30 UTC
    model = ClockModel(drift_scale=2.0, reference_timestamp=ref, source_timezone="Asia/Kolkata", target_timezone="UTC")
    res = normalize_forensic_timeline(dt, model)
    assert res.normalized_timestamp.hour == 8
    assert res.normalized_timestamp.minute == 30

def test_19_naive_reference_in_source_timezone_utc_to_kolkata():
    dt = datetime(2023, 1, 1, 12, 0, 0)
    ref = datetime(2023, 1, 1, 10, 0, 0)
    # T_camera is 12:00 in UTC
    # T_reference is 10:00 in UTC
    # delta is 2 hours.
    # Drift = 2.0 -> scaled delta is 4 hours.
    # T_normalized = T_reference (10:00 UTC) + 4 hours = 14:00 UTC.
    # Converted to Asia/Kolkata -> 14:00 + 5:30 = 19:30 Kolkata
    model = ClockModel(drift_scale=2.0, reference_timestamp=ref, source_timezone="UTC", target_timezone="Asia/Kolkata")
    res = normalize_forensic_timeline(dt, model)
    assert res.normalized_timestamp.hour == 19
    assert res.normalized_timestamp.minute == 30

def test_20_aware_reference_timestamp_with_different_timezone():
    # T_camera is 12:00 in UTC
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
    # Reference is 12:00 in Europe/London. Assuming winter (UTC+0), this is identical to 12:00 UTC.
    # delta is 0 hours.
    # Drift = 2.0 -> scaled delta is 0 hours.
    # T_normalized = T_reference + 0 hours = 12:00 UTC.
    ref = datetime(2023, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("Europe/London"))
    model = ClockModel(drift_scale=2.0, reference_timestamp=ref, source_timezone="UTC", target_timezone="UTC")
    res = normalize_forensic_timeline(dt, model)
    assert res.normalized_timestamp.hour == 12
    assert res.normalized_timestamp.minute == 0

def test_21_drift_offset_timezone_conversion_together():
    dt = datetime(2023, 1, 1, 12, 0, 0) # source UTC
    ref = datetime(2023, 1, 1, 10, 0, 0) # source UTC
    # delta = 2 hours.
    # Drift = 2.0 -> delta_scaled = 4 hours.
    # offset = 3600 seconds = 1 hour.
    # T_normalized (in UTC) = T_reference (10:00) + 4 hours + 1 hour = 15:00 UTC.
    # Convert to Asia/Tokyo (UTC+9) -> 15:00 + 9 = 24:00 -> Jan 2nd 00:00
    model = ClockModel(drift_scale=2.0, offset_seconds=3600, reference_timestamp=ref, source_timezone="UTC", target_timezone="Asia/Tokyo")
    res = normalize_forensic_timeline(dt, model)
    assert res.normalized_timestamp.hour == 0
    assert res.normalized_timestamp.minute == 0
    assert res.normalized_timestamp.day == 2

def test_22_calibration_method_not_specified():
    dt = datetime(2023, 1, 1, 12, 0, 0)
    model = ClockModel(offset_seconds=10, calibration_method=None)
    res = normalize_forensic_timeline(dt, model)
    assert any("Calibration method was not specified" in w for w in res.warnings)

def test_23_valid_and_invalid_confidence():
    with pytest.raises(ValueError):
        ClockModel(calibration_confidence=-0.1)
    with pytest.raises(ValueError):
        ClockModel(calibration_confidence=1.1)
    with pytest.raises(ValueError):
        ClockModel(calibration_confidence=float('nan'))
    with pytest.raises(ValueError):
        ClockModel(calibration_confidence=float('inf'))
    with pytest.raises(ValueError):
        ClockModel(calibration_confidence="high")

    model = ClockModel(calibration_confidence=0.85)
    assert model.calibration_confidence == 0.85
