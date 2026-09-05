"""Video Decoder Adapter Interface and concrete implementations for CCTV forensic workflows.

Provides standard interfaces for container inspection, frame-by-frame decoding,
seeking, metadata extraction, and web inspection proxy generation.
"""
from abc import ABC, abstractmethod
import json
import logging
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, Optional

from app.forensics.vendor_adapter import get_ffmpeg_executable
from parsers.dahua.demuxer import DahuaDemuxer
from parsers.hikvision.demuxer import HikvisionDemuxer

logger = logging.getLogger(__name__)


class VideoDecoderAdapter(ABC):
    """Abstract base class for forensic video decoders."""

    @abstractmethod
    def probe(self, file_path: Path) -> bool:
        """Return True if this decoder can open and decode the video."""
        pass

    @abstractmethod
    def open(self, file_path: Path) -> None:
        """Open the video stream or file for inspection."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return technical media metadata (resolution, fps, duration, codecs)."""
        pass

    @abstractmethod
    def seek(self, timestamp_seconds: float) -> bool:
        """Seek to a specified timestamp in seconds."""
        pass

    @abstractmethod
    def decode_next_frame(self) -> Optional[Dict[str, Any]]:
        """Decode and return the next video frame dictionary (timestamp, width, height, data)."""
        pass

    @abstractmethod
    def generate_web_proxy(self, destination_path: Path) -> Path:
        """Generate a browser-compatible standard MP4 inspection proxy."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Release any open file descriptors or processes."""
        pass


class GenericVideoDecoder(VideoDecoderAdapter):
    """Decoder adapter for standard media files (MP4, MKV, AVI, etc.) using FFmpeg."""

    def __init__(self):
        self.file_path: Optional[Path] = None
        self._meta: Dict[str, Any] = {}

    def probe(self, file_path: Path) -> bool:
        return file_path.is_file() and file_path.stat().st_size > 0

    def open(self, file_path: Path) -> None:
        self.file_path = file_path
        self._meta = self._probe_ffprobe()

    def _probe_ffprobe(self) -> Dict[str, Any]:
        ffmpeg_bin = get_ffmpeg_executable()
        if not ffmpeg_bin or not self.file_path:
            return {}
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            # Fall back to ffmpeg -i info inspection
            cmd = [ffmpeg_bin, "-i", str(self.file_path.resolve())]
            res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            output = res.stderr
            meta = {}
            if "Video:" in output:
                meta["has_video"] = True
            return meta

        cmd = [
            ffprobe_bin,
            "-v", "error",
            "-show_entries", "format=duration,bit_rate:stream=width,height,codec_name,r_frame_rate",
            "-of", "json",
            str(self.file_path.resolve())
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return json.loads(res.stdout)
        except Exception:
            return {}

    def get_metadata(self) -> Dict[str, Any]:
        return self._meta

    def seek(self, timestamp_seconds: float) -> bool:
        return True

    def decode_next_frame(self) -> Optional[Dict[str, Any]]:
        # Frame decoding foundation
        return None

    def generate_web_proxy(self, destination_path: Path) -> Path:
        ffmpeg_bin = get_ffmpeg_executable()
        if not ffmpeg_bin or not self.file_path:
            raise RuntimeError("FFmpeg executable not available for proxy generation.")

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(self.file_path.resolve()),
            "-c:v", "copy",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(destination_path.resolve())
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0 or not destination_path.exists():
            # Fallback to libx264 transcode
            cmd_transcode = [
                ffmpeg_bin,
                "-y",
                "-i", str(self.file_path.resolve()),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-c:a", "aac",
                "-movflags", "+faststart",
                str(destination_path.resolve())
            ]
            res2 = subprocess.run(cmd_transcode, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res2.returncode != 0 or not destination_path.exists():
                raise RuntimeError(f"Proxy generation failed: {res2.stderr[-300:]}")

        return destination_path

    def close(self) -> None:
        self.file_path = None


class DahuaVideoDecoder(VideoDecoderAdapter):
    """Decoder adapter for Dahua DHAV proprietary containers.

    Uses DahuaDemuxer to extract compressed H.264/H.265 elementary streams and
    packages or decodes them into standard proxy containers.
    """

    def __init__(self):
        self.file_path: Optional[Path] = None
        self.demuxer = DahuaDemuxer()
        self._summary: Optional[Any] = None

    def probe(self, file_path: Path) -> bool:
        return self.demuxer.probe(file_path)

    def open(self, file_path: Path) -> None:
        self.file_path = file_path

    def get_metadata(self) -> Dict[str, Any]:
        if not self.file_path:
            return {}
        # Parse packets to gather summary
        temp_dir = self.file_path.parent / ".temp_demux"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_es = temp_dir / f"{self.file_path.stem}.es"
        try:
            self._summary = self.demuxer.extract_elementary_stream(self.file_path, temp_es)
            return self._summary.to_dict()
        finally:
            if temp_es.exists():
                temp_es.unlink(missing_ok=True)
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def seek(self, timestamp_seconds: float) -> bool:
        return True

    def decode_next_frame(self) -> Optional[Dict[str, Any]]:
        return None

    def generate_web_proxy(self, destination_path: Path) -> Path:
        """Demux DHAV container to Annex B elementary stream, then transmux to standard MP4."""
        if not self.file_path or not self.file_path.exists():
            raise FileNotFoundError("Source Dahua evidence file does not exist.")

        ffmpeg_bin = get_ffmpeg_executable()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg executable not available for DHAV transmuxing.")

        destination_path.parent.mkdir(parents=True, exist_ok=True)

        # Step 1: Demux DHAV packets to elementary video stream
        temp_es = destination_path.parent / f"{destination_path.stem}_temp.h264"
        try:
            summary = self.demuxer.extract_elementary_stream(self.file_path, temp_es)
            if not temp_es.exists() or temp_es.stat().st_size == 0:
                raise ValueError("Dahua DHAV demuxer did not extract any video packets.")

            # Step 2: Lossless remux to MP4 container via FFmpeg
            codec_flag = "hevc" if summary.codec == "H.265" else "h264"
            cmd_remux = [
                ffmpeg_bin,
                "-y",
                "-f", codec_flag,
                "-i", str(temp_es.resolve()),
                "-c:v", "copy",
                "-movflags", "+faststart",
                str(destination_path.resolve())
            ]
            res = subprocess.run(cmd_remux, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if res.returncode != 0 or not destination_path.exists() or destination_path.stat().st_size == 0:
                # Fallback to fast transcode if direct copy requires container parameter interpolation
                cmd_transcode = [
                    ffmpeg_bin,
                    "-y",
                    "-f", codec_flag,
                    "-i", str(temp_es.resolve()),
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-movflags", "+faststart",
                    str(destination_path.resolve())
                ]
                res2 = subprocess.run(cmd_transcode, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res2.returncode != 0 or not destination_path.exists():
                    raise RuntimeError(f"Dahua DHAV transmuxing failed: {res2.stderr[-300:]}")

            return destination_path

        finally:
            if temp_es.exists():
                temp_es.unlink(missing_ok=True)

    def close(self) -> None:
        self.file_path = None
