"""Binary magic-byte signature probe engine for forensic video and container identification.

Inspects the initial 16 to 4096 bytes of streams or files to determine
container formats, CCTV proprietary signatures, and playability independent
of file extensions.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union
import os


@dataclass
class SignatureProbeResult:
    format_name: str
    vendor: str
    is_proprietary: bool
    confidence: float
    is_natively_playable: bool
    recommended_action: str
    magic_hex: Optional[str] = None
    details: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "format_name": self.format_name,
            "vendor": self.vendor,
            "is_proprietary": self.is_proprietary,
            "confidence": round(self.confidence, 4),
            "is_natively_playable": self.is_natively_playable,
            "recommended_action": self.recommended_action,
            "magic_hex": self.magic_hex,
            "details": self.details,
        }


def _check_dahua_dav(data: bytes) -> Optional[SignatureProbeResult]:
    """Dahua DAV container identification: DHAV magic at offset 0 (or first 16 bytes)."""
    # Look for b'DHAV' at offset 0 or within the first 16 bytes
    dhav_pos = data[:32].find(b"DHAV")
    if dhav_pos != -1:
        # DHAV is a 4-byte ASCII marker 'DHAV' (0x44 0x48 0x41 0x56)
        magic_hex = data[dhav_pos : dhav_pos + 4].hex().upper()
        return SignatureProbeResult(
            format_name="Dahua DAV",
            vendor="Dahua",
            is_proprietary=True,
            confidence=0.98,
            is_natively_playable=False,
            recommended_action="TRANSMUX_PROXY",
            magic_hex=magic_hex,
            details=f"Dahua DHAV signature detected at offset {dhav_pos}",
        )
    return None


def _check_dahua_wfs(data: bytes) -> Optional[SignatureProbeResult]:
    """Dahua raw filesystem identification: WFS / WFS0."""
    if len(data) >= 4 and (data[:4] == b"WFS0" or data[:3] == b"WFS"):
        return SignatureProbeResult(
            format_name="Dahua WFS Filesystem",
            vendor="Dahua",
            is_proprietary=True,
            confidence=0.95,
            is_natively_playable=False,
            recommended_action="RAW_EXPORT / CARVE_STREAM",
            magic_hex=data[:4].hex().upper(),
            details="Dahua WFS filesystem partition header detected",
        )
    return None


def _check_hikvision(data: bytes) -> Optional[SignatureProbeResult]:
    """Hikvision container identification: HIKB, HIKV, HIKT, or Hikvision MPEG-PS."""
    # Check 4-byte HIK headers at offset 0
    if len(data) >= 4:
        tag4 = data[:4]
        if tag4 == b"HIKV":
            return SignatureProbeResult(
                format_name="Hikvision HIKV",
                vendor="Hikvision",
                is_proprietary=True,
                confidence=0.98,
                is_natively_playable=False,
                recommended_action="TRANSMUX_PROXY",
                magic_hex=tag4.hex().upper(),
                details="Hikvision video container signature (HIKV)",
            )
        elif tag4 == b"HIKB":
            return SignatureProbeResult(
                format_name="Hikvision HIKB",
                vendor="Hikvision",
                is_proprietary=True,
                confidence=0.98,
                is_natively_playable=False,
                recommended_action="TRANSMUX_PROXY",
                magic_hex=tag4.hex().upper(),
                details="Hikvision backup block container signature (HIKB)",
            )
        elif tag4 == b"HIKT":
            return SignatureProbeResult(
                format_name="Hikvision HIKT",
                vendor="Hikvision",
                is_proprietary=True,
                confidence=0.98,
                is_natively_playable=False,
                recommended_action="TRANSMUX_PROXY",
                magic_hex=tag4.hex().upper(),
                details="Hikvision time/track container signature (HIKT)",
            )

    # Check Hikvision / CCTV MPEG-PS pack header: 00 00 01 BA
    if len(data) >= 14 and data[:4] == b"\x00\x00\x01\xba":
        # Search for Hikvision private markers or stream indicators in first 1024 bytes
        search_window = data[:1024]
        if (
            b"\x00\x00\x01\xfd" in search_window
            or b"HK" in search_window
            or b"HIK" in search_window
        ):
            return SignatureProbeResult(
                format_name="Hikvision MPEG-PS",
                vendor="Hikvision",
                is_proprietary=True,
                confidence=0.92,
                is_natively_playable=False,
                recommended_action="TRANSMUX_PROXY",
                magic_hex="000001BA",
                details="MPEG-PS stream with Hikvision private packet indicators",
            )
        # Generic MPEG-PS
        return SignatureProbeResult(
            format_name="MPEG-PS",
            vendor="Generic",
            is_proprietary=False,
            confidence=0.88,
            is_natively_playable=False,
            recommended_action="TRANSMUX_PROXY",
            magic_hex="000001BA",
            details="Standard MPEG-PS container",
        )

    return None


def _check_standard_mp4(data: bytes) -> Optional[SignatureProbeResult]:
    """ISO Base Media File Format (MP4 / QuickTime MOV): 'ftyp' at offset 4."""
    if len(data) >= 8 and data[4:8] == b"ftyp":
        major_brand = data[8:12].decode("latin-1", errors="replace").strip()
        magic_hex = data[:8].hex().upper()
        return SignatureProbeResult(
            format_name="Standard MP4",
            vendor="Generic",
            is_proprietary=False,
            confidence=0.99,
            is_natively_playable=True,
            recommended_action="NATIVE_PLAYBACK",
            magic_hex=magic_hex,
            details=f"ISO/IEC 14496-12 MP4 container (brand: {major_brand})",
        )
    return None


def _check_mkv(data: bytes) -> Optional[SignatureProbeResult]:
    """Matroska / WebM EBML ID: 1A 45 DF A3."""
    if len(data) >= 4 and data[:4] == b"\x1a\x45\xdf\xa3":
        # WebM or MKV doc type check if available
        details = "Matroska / WebM container (EBML header)"
        if b"webm" in data[:64]:
            details = "WebM container (EBML header)"
        return SignatureProbeResult(
            format_name="Standard MKV",
            vendor="Generic",
            is_proprietary=False,
            confidence=0.98,
            is_natively_playable=True,
            recommended_action="NATIVE_PLAYBACK",
            magic_hex="1A45DFA3",
            details=details,
        )
    return None


def _check_avi(data: bytes) -> Optional[SignatureProbeResult]:
    """AVI container: RIFF....AVI ."""
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return SignatureProbeResult(
            format_name="Standard AVI",
            vendor="Generic",
            is_proprietary=False,
            confidence=0.98,
            is_natively_playable=False,
            recommended_action="TRANSMUX_PROXY",
            magic_hex=data[:4].hex().upper() + "..." + data[8:12].hex().upper(),
            details="Microsoft Audio Video Interleave (RIFF AVI)",
        )
    return None


def _check_raw_nal(data: bytes) -> Optional[SignatureProbeResult]:
    """Raw H.264 / H.265 Annex B Elementary Stream detection."""
    # Look for Annex B start code: 00 00 01 or 00 00 00 01
    offset = 0
    if data[:4] == b"\x00\x00\x00\x01":
        offset = 4
    elif data[:3] == b"\x00\x00\x01":
        offset = 3
    else:
        return None

    if len(data) <= offset:
        return None

    first_byte = data[offset]

    # H.264 NAL type is (first_byte & 0x1F)
    # 7 = SPS, 8 = PPS, 5 = IDR, 1 = non-IDR
    h264_nal_type = first_byte & 0x1F
    forbidden_zero_bit = (first_byte & 0x80) >> 7

    if forbidden_zero_bit == 0:
        # Check for SPS / PPS in initial bytes
        if h264_nal_type in (7, 8, 5, 1):
            # Verify if second start code exists in first 512 bytes for higher confidence
            has_second_start = (b"\x00\x00\x00\x01" in data[offset + 1 : 512]) or (
                b"\x00\x00\x01" in data[offset + 1 : 512]
            )
            if has_second_start or h264_nal_type in (7, 8):
                return SignatureProbeResult(
                    format_name="Raw H.264 Elementary Stream",
                    vendor="Generic",
                    is_proprietary=False,
                    confidence=0.88 if has_second_start else 0.70,
                    is_natively_playable=False,
                    recommended_action="TRANSMUX_PROXY",
                    magic_hex=data[:offset].hex().upper(),
                    details=f"Annex B H.264 NAL stream (initial NAL type {h264_nal_type})",
                )

        # H.265 (HEVC) NAL type is ((first_byte >> 1) & 0x3F)
        # 32 = VPS, 33 = SPS, 34 = PPS, 19/20 = IDR
        h265_nal_type = (first_byte >> 1) & 0x3F
        if h265_nal_type in (32, 33, 34, 19, 20):
            return SignatureProbeResult(
                format_name="Raw H.265 Elementary Stream",
                vendor="Generic",
                is_proprietary=False,
                confidence=0.85,
                is_natively_playable=False,
                recommended_action="TRANSMUX_PROXY",
                magic_hex=data[:offset].hex().upper(),
                details=f"Annex B H.265 NAL stream (initial NAL type {h265_nal_type})",
            )

    return None


def probe_bytes(
    data: bytes, filename: Optional[str] = None
) -> SignatureProbeResult:
    """Probe binary data (up to 4096 bytes) and return a SignatureProbeResult.

    Binary magic signatures strictly override filename extensions.
    """
    if not data or len(data) == 0:
        return SignatureProbeResult(
            format_name="Empty File",
            vendor="Unknown",
            is_proprietary=True,
            confidence=0.0,
            is_natively_playable=False,
            recommended_action="RAW_EXPORT / CARVE_STREAM",
            details="File has 0 bytes",
        )

    # 1. Dahua DAV
    dahua_dav = _check_dahua_dav(data)
    if dahua_dav:
        return dahua_dav

    # 2. Dahua WFS
    dahua_wfs = _check_dahua_wfs(data)
    if dahua_wfs:
        return dahua_wfs

    # 3. Hikvision
    hikvision = _check_hikvision(data)
    if hikvision:
        return hikvision

    # 4. Standard MP4
    mp4 = _check_standard_mp4(data)
    if mp4:
        return mp4

    # 5. Standard MKV / WebM
    mkv = _check_mkv(data)
    if mkv:
        return mkv

    # 6. Standard AVI
    avi = _check_avi(data)
    if avi:
        return avi

    # 7. Raw NAL streams
    nal = _check_raw_nal(data)
    if nal:
        return nal

    # Unknown binary
    initial_hex = data[:8].hex().upper() if len(data) >= 8 else data.hex().upper()
    return SignatureProbeResult(
        format_name="Unknown Proprietary Format",
        vendor="Unknown",
        is_proprietary=True,
        confidence=0.0,
        is_natively_playable=False,
        recommended_action="RAW_EXPORT / CARVE_STREAM",
        magic_hex=initial_hex,
        details=(
            f"Unrecognized binary header ({initial_hex}). "
            "Proprietary DVR container or non-standard bitstream."
        ),
    )


def probe_file(file_path: Union[Path, str]) -> SignatureProbeResult:
    """Probe the first 4096 bytes of a physical file."""
    path = Path(file_path)
    if not path.is_file():
        return SignatureProbeResult(
            format_name="Missing File",
            vendor="Unknown",
            is_proprietary=True,
            confidence=0.0,
            is_natively_playable=False,
            recommended_action="RAW_EXPORT / CARVE_STREAM",
            details=f"File does not exist: {path}",
        )

    try:
        with open(path, "rb") as f:
            header_bytes = f.read(4096)
        return probe_bytes(header_bytes, filename=path.name)
    except Exception as e:
        return SignatureProbeResult(
            format_name="Unreadable File",
            vendor="Unknown",
            is_proprietary=True,
            confidence=0.0,
            is_natively_playable=False,
            recommended_action="RAW_EXPORT / CARVE_STREAM",
            details=f"Error reading file header: {str(e)}",
        )
