"""Dahua Technology DVR/NVR vendor adapter.

Provides identification of DHAV containers and WFS filesystem headers,
real proprietary DHAV parsing, CCTV OSD timestamp extraction, and lossless
elementary stream transmuxing to web-compatible inspection proxies.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.forensics.signatures.signature_probe import probe_bytes, probe_file
from app.forensics.vendor_adapter import VendorAdapter, get_ffmpeg_executable
from parsers.common.demuxer import PacketType
from parsers.dahua.demuxer import DahuaDemuxer


class DahuaVendorAdapter(VendorAdapter):
    """Forensic adapter for Dahua DVR/NVR evidence."""

    vendor_name = "Dahua"
    supported_state = "SUPPORTED"
    supported_signatures: List[str] = ["DHAV", "WFS0", "WFS"]

    def __init__(self):
        self.demuxer = DahuaDemuxer()

    def probe_stream(self, header_bytes: bytes) -> float:
        """Inspect header bytes for Dahua DHAV or WFS magic bytes."""
        result = probe_bytes(header_bytes)
        if result.vendor == "Dahua":
            return result.confidence
        return 0.0

    def probe_network(self, ip: str, port: int) -> Optional[dict]:
        """Network probe foundation for Dahua DVR discovery."""
        return {
            "vendor": "Dahua",
            "ip": ip,
            "port": port,
            "identified": False,
            "message": "Dahua network discovery probe foundation (network discovery not active)",
        }

    def get_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from Dahua file header and DHAV frame sequence."""
        probe = probe_file(file_path)
        can_tx = self.can_transmux(file_path) if file_path.is_file() else False
        base_meta: Dict[str, Any] = {
            "vendor": self.vendor_name,
            "format": probe.format_name,
            "is_proprietary": True,
            "confidence": probe.confidence,
            "is_natively_playable": False,
            "recommended_action": probe.recommended_action,
            "parser_status": "Available",
            "decoder_status": "Available (Transmux Proxy)" if can_tx else "Not currently available",
            "supported_state": self.supported_state,
            "details": probe.details,
            "magic_hex": probe.magic_hex,
        }

        if probe.format_name == "Dahua DAV" and file_path.is_file():
            try:
                # Quickly inspect first few packets for channel and OSD timestamps
                packets = list(self.demuxer.parse_packets(file_path))
                if packets:
                    base_meta["total_packets"] = len(packets)
                    channels = {p.channel_index for p in packets if p.channel_index}
                    if channels:
                        base_meta["channel_index"] = list(channels)[0]

                    timestamps = [p.timestamp_osd for p in packets if p.timestamp_osd]
                    if timestamps:
                        base_meta["start_time_osd"] = min(timestamps).isoformat()
                        base_meta["end_time_osd"] = max(timestamps).isoformat()
            except Exception:
                pass

        return base_meta

    def can_transmux(self, file_path: Path) -> bool:
        """Check if this Dahua file can be safely transmuxed into a web proxy.

        Returns True if the file contains DHAV frames with valid H.264/H.265 video payload
        and FFmpeg is available on the workstation.
        """
        if not file_path.is_file() or file_path.stat().st_size < 16:
            return False

        if not get_ffmpeg_executable():
            return False

        probe = probe_file(file_path)
        if probe.format_name == "Dahua DAV":
            try:
                for pkt in self.demuxer.parse_packets(file_path):
                    if pkt.packet_type in (PacketType.VIDEO, PacketType.VIDEO_I, PacketType.VIDEO_P):
                        if b"\x00\x00\x01" in pkt.data[:64] or b"\x00\x00\x00\x01" in pkt.data[:64]:
                            return True
            except Exception:
                return False

        return False

    def transmux_to_proxy(self, source_path: Path, destination_path: Path) -> Path:
        """Transmux proprietary Dahua DHAV stream into standard MP4 proxy without modifying source."""
        if not self.can_transmux(source_path):
            raise ValueError(
                f"Cannot transmux Dahua evidence: {source_path.name}. "
                "File does not contain a valid DHAV stream or FFmpeg is unavailable."
            )

        from app.forensics.decoder import DahuaVideoDecoder
        decoder = DahuaVideoDecoder()
        decoder.open(source_path)
        try:
            return decoder.generate_web_proxy(destination_path)
        finally:
            decoder.close()
