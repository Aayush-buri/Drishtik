import math
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict
try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo

class EventObservation(BaseModel):
    """
    An explicit forensic observation of an event on a specific camera.
    This is an externally supplied/matched input; this engine estimates
    temporal alignment rather than discovering events automatically.
    """
    camera_id: str
    event_id: str
    timestamp: datetime
    timezone: Optional[str] = None

class CameraSyncResult(BaseModel):
    camera_id: str
    offset_seconds: float = 0.0
    matched_observations_count: int = 0
    inlier_observations_count: int = 0
    residual_error: float = 0.0
    sync_confidence: float = 0.0
    warnings: List[str] = []

class SynchronizationResult(BaseModel):
    reference_camera_id: str
    camera_results: Dict[str, CameraSyncResult]
    warnings: List[str] = []

def _normalize_to_utc(dt: datetime, tz_str: Optional[str]) -> datetime:
    """Normalizes a timestamp to UTC for comparison, preserving the actual instant."""
    if dt.tzinfo is not None:
        return dt.astimezone(zoneinfo.ZoneInfo("UTC"))

    # Naive timestamp
    if tz_str:
        try:
            tz = zoneinfo.ZoneInfo(tz_str)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")
    else:
        tz = zoneinfo.ZoneInfo("UTC")

    return dt.replace(tzinfo=tz).astimezone(zoneinfo.ZoneInfo("UTC"))

def synchronize_cameras(
    observations: List[EventObservation],
    reference_camera_id: str,
    inlier_tolerance_seconds: float = 1.0
) -> SynchronizationResult:
    """
    Deterministic event-based synchronization engine.
    Estimates relative camera offsets to a reference camera using matched event observations.

    Does NOT modify original source timestamps.
    Does NOT infer missing cameras.
    """
    warnings = []

    if not observations:
        warnings.append("Zero usable observations provided.")
        return SynchronizationResult(
            reference_camera_id=reference_camera_id,
            camera_results={},
            warnings=warnings
        )

    # Group observations by event_id -> camera_id -> Observation
    # Sorting by event_id and camera_id to ensure determinism across different orderings
    events: Dict[str, Dict[str, EventObservation]] = {}
    for obs in observations:
        if not obs.camera_id or not obs.event_id:
            warnings.append(f"Missing camera ID or event ID in observation.")
            continue

        if obs.event_id not in events:
            events[obs.event_id] = {}

        if obs.camera_id in events[obs.event_id]:
            warnings.append(f"Multiple observations for event {obs.event_id} on camera {obs.camera_id}")
            continue

        events[obs.event_id][obs.camera_id] = obs

    # Check if reference camera has any observations
    ref_observations = 0
    for evt_id, cams in events.items():
        if reference_camera_id in cams:
            ref_observations += 1

    if ref_observations == 0:
        warnings.append("Reference camera absent or has no usable observations.")
        return SynchronizationResult(
            reference_camera_id=reference_camera_id,
            camera_results={},
            warnings=warnings
        )

    # Find all unique cameras
    camera_ids = sorted(list(set(obs.camera_id for obs in observations if obs.camera_id)))
    camera_results: Dict[str, CameraSyncResult] = {}

    for cam_id in camera_ids:
        cam_warnings = []
        if cam_id == reference_camera_id:
            camera_results[cam_id] = CameraSyncResult(
                camera_id=cam_id,
                offset_seconds=0.0,
                matched_observations_count=ref_observations,
                inlier_observations_count=ref_observations,
                residual_error=0.0,
                sync_confidence=1.0,
                warnings=cam_warnings
            )
            continue

        # Collect candidate offsets
        candidate_offsets = []
        # sort event ids to process deterministically
        for evt_id in sorted(events.keys()):
            cams = events[evt_id]
            if reference_camera_id in cams and cam_id in cams:
                ref_obs = cams[reference_camera_id]
                cam_obs = cams[cam_id]

                try:
                    ref_utc = _normalize_to_utc(ref_obs.timestamp, ref_obs.timezone)
                    cam_utc = _normalize_to_utc(cam_obs.timestamp, cam_obs.timezone)
                except Exception as e:
                    cam_warnings.append(f"Invalid timestamp data for event {evt_id}")
                    continue

                # We want T_c + offset = T_ref -> offset = T_ref - T_c
                diff = (ref_utc - cam_utc).total_seconds()
                candidate_offsets.append(diff)

        if not candidate_offsets:
            cam_warnings.append("Camera has insufficient matched events with reference camera.")
            camera_results[cam_id] = CameraSyncResult(
                camera_id=cam_id,
                offset_seconds=0.0,
                matched_observations_count=0,
                inlier_observations_count=0,
                residual_error=0.0,
                sync_confidence=0.0,
                warnings=cam_warnings
            )
            continue

        # Robust estimation: Median
        candidate_offsets.sort()
        n = len(candidate_offsets)
        if n % 2 == 1:
            median_offset = candidate_offsets[n // 2]
        else:
            median_offset = (candidate_offsets[n // 2 - 1] + candidate_offsets[n // 2]) / 2.0

        # Calculate inliers and residual
        inliers = []
        residuals = []
        for offset in candidate_offsets:
            error = abs(offset - median_offset)
            if error <= inlier_tolerance_seconds:
                inliers.append(offset)
                residuals.append(error)

        if not inliers:
            cam_warnings.append("Completely inconsistent matched observations.")
            camera_results[cam_id] = CameraSyncResult(
                camera_id=cam_id,
                offset_seconds=0.0,
                matched_observations_count=n,
                inlier_observations_count=0,
                residual_error=0.0,
                sync_confidence=0.0,
                warnings=cam_warnings
            )
            continue

        # Re-estimate with inliers only (mean of inliers)
        final_offset = sum(inliers) / len(inliers)
        final_residual = sum(abs(inc - final_offset) for inc in inliers) / len(inliers)

        if len(inliers) < n:
            cam_warnings.append(f"Rejected {n - len(inliers)} outlier observations.")

        confidence = float(len(inliers)) / n

        camera_results[cam_id] = CameraSyncResult(
            camera_id=cam_id,
            offset_seconds=final_offset,
            matched_observations_count=n,
            inlier_observations_count=len(inliers),
            residual_error=final_residual,
            sync_confidence=confidence,
            warnings=cam_warnings
        )

    return SynchronizationResult(
        reference_camera_id=reference_camera_id,
        camera_results=camera_results,
        warnings=warnings
    )
