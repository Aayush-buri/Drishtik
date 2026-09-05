"""Normalized internal representation for video evidence (Unified Video Representation).

Provides a vendor-agnostic foundation for metadata normalization, playback determination,
dual timestamp handling, and downstream forensic analysis without forcing unavailable fields.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class UnifiedVideoRepresentation:
    # Identity
    evidence_identifier: str
    source_device_identifier: Optional[str] = None
    acquisition_identifier: Optional[str] = None
    vendor: str = "Generic / Standard"
    container_format: str = "Standard MP4"
    is_proprietary: bool = False

    # CCTV
    channel_number: Optional[int] = 1
    channel_name: str = "CAM 01"
    source_start_time: Optional[datetime] = None
    source_end_time: Optional[datetime] = None
    timezone: str = "UTC"
    timestamp_confidence: float = 1.0
    has_discontinuous_timestamps: bool = False

    # Technical Media
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    bitrate: Optional[int] = None

    # Playback
    browser_playable: bool = True
    proxy_available: bool = False
    playback_source: Optional[str] = None
    parent_evidence_identifier: Optional[str] = None
    is_inspection_proxy: bool = False

    # Normalization / Calibration
    is_calibrated: bool = False
    offset_seconds: float = 0.0
    calibration_reason: Optional[str] = None

    metadata_attributes: Dict[str, Any] = field(default_factory=dict)

    # Aliases for backward compatibility with CommonVideoModel
    @property
    def start_time_osd(self) -> Optional[datetime]:
        return self.source_start_time

    @property
    def end_time_osd(self) -> Optional[datetime]:
        return self.source_end_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_identifier": self.evidence_identifier,
            "source_device_identifier": self.source_device_identifier,
            "acquisition_identifier": self.acquisition_identifier,
            "vendor": self.vendor,
            "container_format": self.container_format,
            "is_proprietary": self.is_proprietary,
            "channel_number": self.channel_number,
            "channel_name": self.channel_name,
            "source_start_time": self.source_start_time.isoformat() if self.source_start_time else None,
            "source_end_time": self.source_end_time.isoformat() if self.source_end_time else None,
            "timezone": self.timezone,
            "timestamp_confidence": self.timestamp_confidence,
            "has_discontinuous_timestamps": self.has_discontinuous_timestamps,
            "duration_seconds": self.duration_seconds,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "bitrate": self.bitrate,
            "browser_playable": self.browser_playable,
            "proxy_available": self.proxy_available,
            "playback_source": self.playback_source,
            "parent_evidence_identifier": self.parent_evidence_identifier,
            "is_inspection_proxy": self.is_inspection_proxy,
            "is_calibrated": self.is_calibrated,
            "offset_seconds": self.offset_seconds,
            "calibration_reason": self.calibration_reason,
            "metadata_attributes": self.metadata_attributes,
        }


# Backward compatibility alias
CommonVideoModel = UnifiedVideoRepresentation
