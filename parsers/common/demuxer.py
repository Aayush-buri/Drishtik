"""Common demuxer interfaces and packet models for CCTV / DVR / NVR container parsing."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


class PacketType(str, Enum):
    VIDEO = "VIDEO"      # Generic Video
    VIDEO_I = "VIDEO_I"  # Keyframe / IDR
    VIDEO_P = "VIDEO_P"  # Predicted frame
    VIDEO_B = "VIDEO_B"  # Bi-directional frame
    AUDIO = "AUDIO"
    OSD = "OSD"          # On-Screen Display metadata / timestamp
    SYSTEM = "SYSTEM"    # Container headers / parameters
    UNKNOWN = "UNKNOWN"


@dataclass
class DemuxedPacket:
    packet_type: PacketType
    channel_index: int
    data: bytes
    timestamp_osd: Optional[datetime] = None
    timestamp_ticks: Optional[int] = None
    stream_offset: int = 0
    payload_size: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DemuxSummary:
    container_format: str
    codec: str = "H.264"
    total_packets: int = 0
    video_packets: int = 0
    audio_packets: int = 0
    keyframe_count: int = 0
    channel_index: Optional[int] = None
    start_time_osd: Optional[datetime] = None
    end_time_osd: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "container_format": self.container_format,
            "codec": self.codec,
            "total_packets": self.total_packets,
            "video_packets": self.video_packets,
            "audio_packets": self.audio_packets,
            "keyframe_count": self.keyframe_count,
            "channel_index": self.channel_index,
            "start_time_osd": self.start_time_osd.isoformat() if self.start_time_osd else None,
            "end_time_osd": self.end_time_osd.isoformat() if self.end_time_osd else None,
            "duration_seconds": self.duration_seconds,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "metadata": self.metadata,
        }


class BaseDemuxer(ABC):
    """Abstract base class for vendor container demuxers."""

    @abstractmethod
    def probe(self, file_path: Path) -> bool:
        """Return True if this demuxer can parse the file."""
        pass

    @abstractmethod
    def parse_packets(self, file_path: Path) -> Iterator[DemuxedPacket]:
        """Stream parsed packets from the container."""
        pass

    @abstractmethod
    def extract_elementary_stream(
        self, file_path: Path, output_stream_path: Path
    ) -> DemuxSummary:
        """Extract compressed video elementary stream (H.264/H.265 Annex B) and return summary."""
        pass
