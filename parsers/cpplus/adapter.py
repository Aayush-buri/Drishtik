"""CP Plus CCTV / DVR vendor adapter.

Supports CP Plus surveillance recordings, recognizing Dahua OEM compatibility
(DHAV container format) and reusing the Dahua demuxer pipeline when justified
by the actual binary structure.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.forensics.signatures.signature_probe import probe_bytes, probe_file
from app.forensics.vendor_adapter import VendorAdapter, get_ffmpeg_executable
from parsers.dahua.demuxer import DahuaDemuxer


class CPPlusVendorAdapter(VendorAdapter):
    """Forensic adapter for CP Plus DVR/NVR evidence."""

    vendor_name = "CP Plus"
    supported_state = "PARTIAL"
    supported_signatures: List[str] = ["DHAV", "CPPLUS", "WFS"]

    def __init__(self):
        self.dahua_demuxer = DahuaDemuxer()

    def probe_stream(self, header_bytes: bytes) -> float:
        """Inspect header for CP Plus indicators or Dahua OEM compatibility."""
        if b"CPPLUS" in header_bytes[:64]:
            return 0.95
        # If DHAV magic, check if filename or tag hints at CP Plus
        if b"DHAV" in header_bytes[:32]:
            return 0.85  # Highly compatible Dahua OEM stream
        return 0.0

    def probe_network(self, ip: str, port: int) -> Optional[dict]:
        return {
            "vendor": "CP Plus",
            "ip": ip,
            "port": port,
            "identified": False,
            "message": "CP Plus network probe foundation (discovery inactive)",
        }

    def get_metadata(self, file_path: Path) -> Dict[str, Any]:
        probe = probe_file(file_path)
        is_dahua_compatible = self.dahua_demuxer.probe(file_path)
        decoder_status = "Available (Dahua OEM Transmux)" if is_dahua_compatible else "Unavailable"

        return {
            "vendor": self.vendor_name,
            "format": f"CP Plus ({'Dahua OEM DHAV' if is_dahua_compatible else probe.format_name})",
            "is_proprietary": True,
            "confidence": probe.confidence if probe.confidence > 0 else 0.85,
            "is_natively_playable": False,
            "recommended_action": "TRANSMUX_PROXY" if is_dahua_compatible else "RAW_EXPORT / CARVE_STREAM",
            "parser_status": "Available" if is_dahua_compatible else "Unavailable",
            "decoder_status": decoder_status,
            "supported_state": self.supported_state,
            "details": "CP Plus DVR footage using Dahua-compatible DHAV container format" if is_dahua_compatible else "Proprietary CP Plus recording format",
            "magic_hex": probe.magic_hex,
        }

    def can_transmux(self, file_path: Path) -> bool:
        if not file_path.is_file() or file_path.stat().st_size < 16:
            return False

        if not get_ffmpeg_executable():
            return False

        # If it is Dahua-compatible DHAV container, we can transmux it!
        return self.dahua_demuxer.probe(file_path)

    def transmux_to_proxy(self, source_path: Path, destination_path: Path) -> Path:
        if not self.can_transmux(source_path):
            raise NotImplementedError(
                "CP Plus proprietary variant cannot be transmuxed directly. "
                "Only Dahua-compatible CP Plus DHAV recordings are currently supported for proxy generation."
            )

        from app.forensics.decoder import DahuaVideoDecoder
        decoder = DahuaVideoDecoder()
        decoder.open(source_path)
        try:
            return decoder.generate_web_proxy(destination_path)
        finally:
            decoder.close()
