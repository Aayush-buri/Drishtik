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
    model = ClockModel(offset_seconds=10, calibration_method="MANUAL_SYNC", calibration_confidence=0.8)
    res = normalize_forensic_timeline(dt, model)
    assert res.confidence == 0.8
    assert any("manual" in w.lower() for w in res.warnings)

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

