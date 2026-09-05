"""Vendor Adapter Base Interface and Extensible Registry for CCTV / DVR / NVR platforms.

Provides an NTRO-compliant vendor-agnostic foundation for format probing,
metadata inspection, and proxy generation without claiming unsupported decoding.
"""
from abc import ABC, abstractmethod
import logging
from pathlib import Path
import shutil
import subprocess
from typing import Dict, Optional, Union

from app.forensics.signatures.signature_probe import (
    SignatureProbeResult,
    probe_bytes,
    probe_file,
)

logger = logging.getLogger(__name__)


def get_ffmpeg_executable() -> Optional[str]:
    """Resolve FFmpeg executable from PATH or imageio_ffmpeg bundled binary."""
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).is_file():
            return exe
    except Exception:
        pass
    return None


class VendorAdapter(ABC):
    """Abstract base class for DVR/NVR vendor adapters."""

    vendor_name: str = "AbstractVendor"

    @abstractmethod
    def probe_stream(self, header_bytes: bytes) -> float:
        """Probe the initial stream bytes and return a confidence score between 0.0 and 1.0."""
        pass

    @abstractmethod
    def probe_network(self, ip: str, port: int) -> Optional[dict]:
        """Attempt discovery or identify manufacturer over network port."""
        pass

    @abstractmethod
    def get_metadata(self, file_path: Path) -> dict:
        """Extract container and stream metadata without decoding video."""
        pass

    @abstractmethod
    def can_transmux(self, file_path: Path) -> bool:
        """Return True if the container payload can be safely transmuxed to a web-compatible proxy."""
        pass

    @abstractmethod
    def transmux_to_proxy(self, source_path: Path, destination_path: Path) -> Path:
        """Transmux standard payloads in container to MP4 proxy.

        Must NOT fake playback if unsupported. Raises ValueError or NotImplementedError if unavailable.
        """
        pass


class GenericVendorAdapter(VendorAdapter):
    """Generic adapter for standard ISO/IEC formats (MP4, MKV, AVI, raw elementary streams)."""

    vendor_name = "Generic"

    def probe_stream(self, header_bytes: bytes) -> float:
        result = probe_bytes(header_bytes)
        if result.vendor == "Generic":
            return result.confidence
        return 0.0

    def probe_network(self, ip: str, port: int) -> Optional[dict]:
        return None

    def get_metadata(self, file_path: Path) -> dict:
        probe = probe_file(file_path)
        stat = file_path.stat() if file_path.exists() else None
        return {
            "vendor": self.vendor_name,
            "format": probe.format_name,
            "is_proprietary": probe.is_proprietary,
            "size_bytes": stat.st_size if stat else 0,
            "confidence": probe.confidence,
            "is_natively_playable": probe.is_natively_playable,
            "recommended_action": probe.recommended_action,
        }

    def can_transmux(self, file_path: Path) -> bool:
        probe = probe_file(file_path)
        # If standard format and ffmpeg is available, transmux is supported
        ffmpeg_bin = get_ffmpeg_executable()
        if not ffmpeg_bin:
            return False
        # If already natively playable standard MP4, it can easily be proxied/copied
        # If AVI/MKV/Raw elementary stream, ffmpeg can package it
        return probe.vendor == "Generic" and not probe.is_proprietary

    def transmux_to_proxy(self, source_path: Path, destination_path: Path) -> Path:
        ffmpeg_bin = get_ffmpeg_executable()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg executable not available on host system for transmuxing.")

        if not self.can_transmux(source_path):
            raise ValueError(f"Generic adapter cannot transmux non-standard file: {source_path}")

        destination_path.parent.mkdir(parents=True, exist_ok=True)

        # Attempt safe copy first (-c copy)
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(source_path.resolve()),
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(destination_path.resolve()),
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0 or not destination_path.exists() or destination_path.stat().st_size == 0:
            # Fallback to fast H.264 transcode if direct container copy failed
            cmd_transcode = [
                ffmpeg_bin,
                "-y",
                "-i",
                str(source_path.resolve()),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(destination_path.resolve()),
            ]
            result2 = subprocess.run(
                cmd_transcode, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if result2.returncode != 0 or not destination_path.exists():
                raise RuntimeError(
                    f"Transmuxing failed for {source_path.name}: {result2.stderr[-300:]}"
                )

        return destination_path


# --- Registry Management ---
_ADAPTER_REGISTRY: Dict[str, VendorAdapter] = {}


def register_vendor_adapter(adapter: VendorAdapter) -> None:
    """Register an adapter instance in the global registry."""
    _ADAPTER_REGISTRY[adapter.vendor_name.lower()] = adapter
    logger.info(f"Registered forensic vendor adapter: {adapter.vendor_name}")


def get_vendor_adapter(name_or_vendor: str) -> Optional[VendorAdapter]:
    """Retrieve an adapter by vendor name (case-insensitive)."""
    return _ADAPTER_REGISTRY.get(name_or_vendor.lower())


def get_best_adapter_for_file(file_path: Union[Path, str]) -> VendorAdapter:
    """Determine the best vendor adapter for a given file based on binary inspection.

    Binary signature analysis strictly takes precedence over file extension.
    Falls back to GenericVendorAdapter if no vendor-specific adapter matches.
    """
    path = Path(file_path)
    probe_result = probe_file(path)

    # First check if an adapter exists matching probe_result.vendor
    vendor_key = probe_result.vendor.lower()
    if vendor_key in _ADAPTER_REGISTRY:
        return _ADAPTER_REGISTRY[vendor_key]

    # Otherwise probe all registered adapters for highest stream confidence
    best_adapter: Optional[VendorAdapter] = None
    highest_confidence = 0.0

    header_bytes = b""
    if path.is_file():
        try:
            with open(path, "rb") as f:
                header_bytes = f.read(4096)
        except Exception:
            pass

    for adapter in _ADAPTER_REGISTRY.values():
        conf = adapter.probe_stream(header_bytes)
        if conf > highest_confidence:
            highest_confidence = conf
            best_adapter = adapter

    if best_adapter and highest_confidence > 0.5:
        return best_adapter

    return _ADAPTER_REGISTRY.get("generic", GenericVendorAdapter())


# Register standard Generic adapter
register_vendor_adapter(GenericVendorAdapter())

# Ensure project root is in sys.path so parsers can be imported
import sys
_project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from parsers.dahua.adapter import DahuaVendorAdapter
    register_vendor_adapter(DahuaVendorAdapter())
except Exception as _e:
    logger.warning(f"Could not auto-register Dahua adapter: {_e}")

try:
    from parsers.hikvision.adapter import HikvisionVendorAdapter
    register_vendor_adapter(HikvisionVendorAdapter())
except Exception as _e:
    logger.warning(f"Could not auto-register Hikvision adapter: {_e}")

try:
    from parsers.cpplus.adapter import CPPlusVendorAdapter
    register_vendor_adapter(CPPlusVendorAdapter())
except Exception as _e:
    logger.warning(f"Could not auto-register CP Plus adapter: {_e}")


