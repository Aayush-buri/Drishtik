from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, timedelta
import math

try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo

class ClockModel(BaseModel):
    """
    ClockModel represents the forensic affine drift and offset parameters.

    Terminology:
    - source/camera time: Timestamp embedded/provided by the CCTV system.
    - reference time: An established true-time point used to anchor the drift scale.
      If reference_timestamp is naive, it is interpreted in the source/camera timezone.
    - normalized time: Timestamp transformed using a documented timezone/clock calibration model.
    - synchronized time: A future higher-level result derived from matching events across cameras.
      Note explicitly: normalized time != synchronized time.

    The affine drift model applies calibration in this order:
    1. Interpret source_timestamp and reference_timestamp in the source timezone.
    2. delta = T_camera - T_reference
    3. delta_scaled = delta * drift_scale
    4. T_normalized = T_reference + delta_scaled + offset
    5. Convert T_normalized to target timezone.

    calibration_confidence represents certainty in the calibration values.
    calibration_provenance tracks the method (e.g. MANUAL_SYNC) and reason.
    """
    offset_seconds: float = 0.0
    drift_scale: float = 1.0
    reference_timestamp: Optional[datetime] = None
    source_timezone: Optional[str] = None
    target_timezone: Optional[str] = None
    calibration_method: Optional[str] = None
    calibration_confidence: float = 1.0
    calibration_reason: Optional[str] = None

    @field_validator("calibration_confidence")
    @classmethod
    def validate_confidence(cls, v):
        if not isinstance(v, (int, float)):
            raise ValueError("Confidence must be a number")
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Confidence must be finite")
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return float(v)

class NormalizedTimestamp(BaseModel):
    source_timestamp: Optional[datetime] = None
    normalized_timestamp: Optional[datetime] = None
    source_timezone: Optional[str] = None
    normalized_timezone: Optional[str] = None
    offset_seconds: float = 0.0
    drift_scale: float = 1.0
    reference_timestamp: Optional[datetime] = None
    calibration_applied: bool = False
    confidence: float = 1.0
    warnings: List[str] = []

def normalize_forensic_timeline(
    source_timestamp: Optional[datetime],
    clock_model: Optional[ClockModel]
) -> NormalizedTimestamp:
    warnings = []

    if source_timestamp is None:
        return NormalizedTimestamp(warnings=["No source timestamp provided"])

    if clock_model is None:
        # No calibration
        norm = source_timestamp
        if norm.tzinfo is None:
            norm = norm.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        return NormalizedTimestamp(
            source_timestamp=source_timestamp,
            normalized_timestamp=norm,
            source_timezone=None,
            normalized_timezone="UTC",
            calibration_applied=False,
            warnings=["No calibration applied", "Source timezone was not provided"]
        )

    # Validate clock model drift scale
    if clock_model.drift_scale <= 0 or math.isinf(clock_model.drift_scale) or math.isnan(clock_model.drift_scale):
        raise ValueError("Invalid drift scale")

    if clock_model.drift_scale != 1.0 and clock_model.reference_timestamp is None:
        raise ValueError("Drift correction requires a valid reference timestamp")

    # Timezone parsing
    src_tz_str = clock_model.source_timezone
    if not src_tz_str:
        src_tz_str = "UTC"
        warnings.append("Source timezone was not provided")

    tgt_tz_str = clock_model.target_timezone or "UTC"

    try:
        src_tz = zoneinfo.ZoneInfo(src_tz_str)
    except Exception:
        src_tz = zoneinfo.ZoneInfo("UTC")
        src_tz_str = "UTC"
        warnings.append("Source timezone was invalid, defaulting to UTC")

    try:
        tgt_tz = zoneinfo.ZoneInfo(tgt_tz_str)
    except Exception:
        tgt_tz = zoneinfo.ZoneInfo("UTC")
        tgt_tz_str = "UTC"
        warnings.append("Target timezone was invalid, defaulting to UTC")

    # Bind source timezone
    t_camera = source_timestamp
    if t_camera.tzinfo is None:
        t_camera = t_camera.replace(tzinfo=src_tz)
    else:
        # If it already had a timezone, we logically represent it in the source timezone
        t_camera = t_camera.astimezone(src_tz)

    offset = timedelta(seconds=clock_model.offset_seconds)

    t_reference = clock_model.reference_timestamp
    if t_reference is not None:
        if t_reference.tzinfo is None:
            # Correct behavior: interpret naive reference in source timezone
            t_reference = t_reference.replace(tzinfo=src_tz)
        else:
            # Preserve its instant by converting into source timezone for delta math
            t_reference = t_reference.astimezone(src_tz)

    if t_reference is None or clock_model.drift_scale == 1.0:
        # No drift
        t_normalized = t_camera + offset
        if t_reference is None and clock_model.drift_scale != 1.0:
            warnings.append("Drift correction unavailable because reference timestamp is missing")
    else:
        # T_normalized = T_reference + (T_camera - T_reference) * drift_scale + offset
        delta = t_camera - t_reference
        delta_seconds = delta.total_seconds() * clock_model.drift_scale
        # timedelta seconds supports microseconds as a float
        t_normalized = t_reference + timedelta(seconds=delta_seconds) + offset

    # Convert normalized to target timezone
    t_normalized = t_normalized.astimezone(tgt_tz)

    if clock_model.calibration_method:
        method_str = clock_model.calibration_method.lower()
        warnings.append(f"Normalization based on {method_str} calibration")
    else:
        warnings.append("Calibration method was not specified")

    return NormalizedTimestamp(
        source_timestamp=source_timestamp,
        normalized_timestamp=t_normalized,
        source_timezone=src_tz_str,
        normalized_timezone=tgt_tz_str,
        offset_seconds=clock_model.offset_seconds,
        drift_scale=clock_model.drift_scale,
        reference_timestamp=clock_model.reference_timestamp,
        calibration_applied=True,
        confidence=clock_model.calibration_confidence,
        warnings=warnings
    )
