"""Hikvision DVR/NVR vendor adapter.

Provides identification of HIKB, HIKV, HIKT containers and Hikvision MPEG-PS streams,
with stream parsing and proxy transmuxing for supported PES video streams.
"""
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from app.forensics.signatures.signature_probe import probe_bytes, probe_file
from app.forensics.vendor_adapter import VendorAdapter, get_ffmpeg_executable
from parsers.hikvision.demuxer import HikvisionDemuxer


class HikvisionVendorAdapter(VendorAdapter):
    """Forensic adapter for Hikvision DVR/NVR evidence."""

    vendor_name = "Hikvision"
    supported_state = "PARTIAL"
    supported_signatures: List[str] = ["HIKB", "HIKV", "HIKT", "Hikvision MPEG-PS"]

    def __init__(self):
        self.demuxer = HikvisionDemuxer()

    def probe_stream(self, header_bytes: bytes) -> float:
        result = probe_bytes(header_bytes)
        if result.vendor == "Hikvision":
            return result.confidence
        return 0.0

    def probe_network(self, ip: str, port: int) -> Optional[dict]:
        return {
            "vendor": "Hikvision",
            "ip": ip,
            "port": port,
            "identified": False,
            "message": "Hikvision network discovery probe foundation (network discovery not active)",
        }

    def get_metadata(self, file_path: Path) -> Dict[str, Any]:
        probe = probe_file(file_path)
        decoder_status = "Available (Transmux Proxy)" if self.can_transmux(file_path) else "Unavailable (Encrypted / Unsupported Variant)"
        return {
            "vendor": self.vendor_name,
            "format": probe.format_name,
            "is_proprietary": True,
            "confidence": probe.confidence,
            "is_natively_playable": False,
            "recommended_action": probe.recommended_action,
            "parser_status": "Available",
            "decoder_status": decoder_status,
            "supported_state": self.supported_state,
            "details": probe.details,
            "magic_hex": probe.magic_hex,
        }

    def can_transmux(self, file_path: Path) -> bool:
        if not file_path.is_file() or file_path.stat().st_size < 16:
            return False

        if not get_ffmpeg_executable():
            return False

        probe = probe_file(file_path)
        # MPEG-PS and standard HIKV containers can be demuxed/transmuxed
        if probe.format_name in ("Hikvision MPEG-PS", "Hikvision HIKV"):
            return self.demuxer.probe(file_path)

        # HIKB or unknown variants without standard PES headers cannot yet be transmuxed
        return False

    def transmux_to_proxy(self, source_path: Path, destination_path: Path) -> Path:
        if not self.can_transmux(source_path):
            raise NotImplementedError(
                "Hikvision proprietary variant transmuxing is not supported for this file. "
                "The container requires proprietary Hikvision software for playback."
            )

        ffmpeg_bin = get_ffmpeg_executable()
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        temp_es = destination_path.parent / f"{destination_path.stem}_temp_hik.h264"
        try:
            self.demuxer.extract_elementary_stream(source_path, temp_es)
            if not temp_es.exists() or temp_es.stat().st_size == 0:
                raise ValueError("Hikvision demuxer could not extract video elementary stream.")

            cmd_remux = [
                ffmpeg_bin,
                "-y",
                "-f", "h264",
                "-i", str(temp_es.resolve()),
                "-c:v", "copy",
                "-movflags", "+faststart",
                str(destination_path.resolve())
            ]
            res = subprocess.run(cmd_remux, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0 or not destination_path.exists():
                # Fallback transcode
                cmd_transcode = [
                    ffmpeg_bin,
                    "-y",
                    "-f", "h264",
                    "-i", str(temp_es.resolve()),
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-movflags", "+faststart",
                    str(destination_path.resolve())
                ]
                subprocess.run(cmd_transcode, check=True)

            return destination_path
        finally:
            if temp_es.exists():
                temp_es.unlink(missing_ok=True)
