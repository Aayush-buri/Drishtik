"""Recovery engine and carving foundation for deleted/raw CCTV storage.

Provides safe stream-carving candidate identification on raw disk images
(.raw, .dd, .img, .e01) without modifying the source image or falsely claiming
full automated filesystem recovery.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class DiskImageInfo:
    image_format: str
    size_bytes: int
    sector_size: int = 512
    is_supported: bool = True
    details: str = ""


@dataclass
class RecoveryCandidate:
    candidate_id: str
    offset_bytes: int
    length_bytes: int
    detected_vendor: str
    format_name: str
    confidence: float
    signature_matched: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "offset_bytes": self.offset_bytes,
            "length_bytes": self.length_bytes,
            "detected_vendor": self.detected_vendor,
            "format_name": self.format_name,
            "confidence": self.confidence,
            "signature_matched": self.signature_matched,
            "metadata": self.metadata,
        }


class CarvingStrategy(ABC):
    """Abstract base class for carving specific vendor stream structures."""

    strategy_name: str = "BaseCarver"

    @abstractmethod
    def scan_chunk(self, data: bytes, base_offset: int) -> List[RecoveryCandidate]:
        """Scan a chunk of bytes and return candidates found."""
        pass

    def carve_candidates(self, data: bytes, base_offset: int = 0) -> List[RecoveryCandidate]:
        """Convenience alias for scan_chunk."""
        return self.scan_chunk(data, base_offset)


class DhavCarvingStrategy(CarvingStrategy):
    """Scans for Dahua DHAV frame sequences within raw disk/storage chunks."""

    strategy_name = "Dahua DHAV Carver"

    def scan_chunk(self, data: bytes, base_offset: int) -> List[RecoveryCandidate]:
        candidates: List[RecoveryCandidate] = []
        offset = 0
        while offset < len(data):
            pos = data.find(b"DHAV", offset)
            if pos == -1:
                break

            abs_offset = base_offset + pos
            # Inspect DHAV structure
            channel = data[pos + 5] + 1 if pos + 5 < len(data) else 1
            candidates.append(
                RecoveryCandidate(
                    candidate_id=f"REC-DHAV-{abs_offset:08X}",
                    offset_bytes=abs_offset,
                    length_bytes=1024,  # Estimated block size
                    detected_vendor="Dahua",
                    format_name="Dahua DAV Frame",
                    confidence=0.90,
                    signature_matched="DHAV",
                    metadata={"channel_index": channel, "offset": abs_offset},
                )
            )
            offset = pos + 4
        return candidates


class HikvisionCarvingStrategy(CarvingStrategy):
    """Scans for Hikvision HIKV / MPEG-PS stream signatures."""

    strategy_name = "Hikvision Carver"

    def scan_chunk(self, data: bytes, base_offset: int) -> List[RecoveryCandidate]:
        candidates: List[RecoveryCandidate] = []
        offset = 0
        while offset < len(data):
            # Check for HIKV container
            hikv_pos = data.find(b"HIKV", offset)
            if hikv_pos != -1:
                abs_offset = base_offset + hikv_pos
                candidates.append(
                    RecoveryCandidate(
                        candidate_id=f"REC-HIK-{abs_offset:08X}",
                        offset_bytes=abs_offset,
                        length_bytes=2048,
                        detected_vendor="Hikvision",
                        format_name="Hikvision HIKV Frame",
                        confidence=0.90,
                        signature_matched="HIKV",
                        metadata={"offset": abs_offset},
                    )
                )
                offset = hikv_pos + 4
                continue

            # Check for MPEG-PS Pack header
            ps_pos = data.find(b"\x00\x00\x01\xba", offset)
            if ps_pos != -1:
                abs_offset = base_offset + ps_pos
                candidates.append(
                    RecoveryCandidate(
                        candidate_id=f"REC-PS-{abs_offset:08X}",
                        offset_bytes=abs_offset,
                        length_bytes=2048,
                        detected_vendor="Hikvision",
                        format_name="MPEG-PS Pack Header",
                        confidence=0.80,
                        signature_matched="000001BA",
                        metadata={"offset": abs_offset},
                    )
                )
                offset = ps_pos + 4
                continue

            break
        return candidates


class Mp4FtypCarvingStrategy(CarvingStrategy):
    """Scans for ISO MP4 ftyp box boundaries."""

    strategy_name = "MP4 ftyp Carver"

    def scan_chunk(self, data: bytes, base_offset: int) -> List[RecoveryCandidate]:
        candidates: List[RecoveryCandidate] = []
        offset = 0
        while offset < len(data):
            pos = data.find(b"ftyp", offset)
            if pos >= 4:
                abs_offset = base_offset + pos - 4
                candidates.append(
                    RecoveryCandidate(
                        candidate_id=f"REC-MP4-{abs_offset:08X}",
                        offset_bytes=abs_offset,
                        length_bytes=4096,
                        detected_vendor="Generic",
                        format_name="ISO MP4 Container",
                        confidence=0.95,
                        signature_matched="ftyp",
                        metadata={"offset": abs_offset},
                    )
                )
            if pos == -1:
                break
            offset = pos + 4
        return candidates


class RecoveryEngine:
    """Forensic carving and candidate recovery engine."""

    def __init__(self, strategies: Optional[List[CarvingStrategy]] = None):
        self.strategies = strategies or [
            DhavCarvingStrategy(),
            HikvisionCarvingStrategy(),
            Mp4FtypCarvingStrategy(),
        ]

    @property
    def carving_strategies(self) -> List[CarvingStrategy]:
        """Convenience property exposing registered carving strategies."""
        return self.strategies

    def is_supported_image(self, image_path: Path) -> bool:
        """Returns True if the image is an identified/supported disk image."""
        info = self.probe_image(Path(image_path))
        return info.is_supported

    def probe_image(self, image_path: Path) -> DiskImageInfo:
        """Inspect and identify forensic disk image type."""
        if not image_path.is_file():
            return DiskImageInfo(image_format="UNKNOWN", size_bytes=0, is_supported=False, details="File not found")

        size = image_path.stat().st_size
        suffix = image_path.suffix.lower()

        # Read header
        with open(image_path, "rb") as f:
            header = f.read(512)

        # Check Expert Witness Compression Format (E01): 'EVF\x09\x0d\x0a\xff\x00'
        if header.startswith(b"EVF") or suffix == ".e01":
            return DiskImageInfo(
                image_format="E01 (Expert Witness Format)",
                size_bytes=size,
                is_supported=True,
                details="EnCase / E01 compressed forensic disk image header identified",
            )

        if suffix in (".raw", ".dd"):
            return DiskImageInfo(
                image_format="Raw / DD Bitstream Image",
                size_bytes=size,
                is_supported=True,
                details="Raw uncompressed block device bitstream image",
            )

        if suffix == ".img":
            return DiskImageInfo(
                image_format="Raw Disk Image (.img)",
                size_bytes=size,
                is_supported=True,
                details="Generic raw disk/partition image",
            )

        return DiskImageInfo(
            image_format="Binary Image / File",
            size_bytes=size,
            is_supported=True,
            details="Generic binary storage stream",
        )

    def identify_disk_image(self, image_path: Path) -> DiskImageInfo:
        """Convenience alias for probe_image."""
        return self.probe_image(image_path)

    def scan_candidates(
        self, image_path: Path, max_bytes: int = 10 * 1024 * 1024
    ) -> List[RecoveryCandidate]:
        """Scan up to max_bytes of the disk image using registered carving strategies."""
        candidates: List[RecoveryCandidate] = []
        if not image_path.is_file():
            return candidates

        chunk_size = 512 * 1024  # 512 KB chunks
        overlap = 64             # 64 bytes overlap

        with open(image_path, "rb") as f:
            total_read = 0
            while total_read < max_bytes:
                read_amount = min(chunk_size, max_bytes - total_read)
                chunk = f.read(read_amount)
                if not chunk:
                    break

                for strat in self.strategies:
                    found = strat.scan_chunk(chunk, total_read)
                    candidates.extend(found)

                total_read += len(chunk)
                if len(chunk) < read_amount:
                    break

        return candidates

    def validate_candidate_stream(
        self, image_path: Path, offset_bytes: int, length_bytes: int, detected_format: str
    ) -> Dict[str, Any]:
        """Validates stream structure at candidate offset and distinguishes VALID, PARTIAL, CORRUPTED."""
        if not image_path.is_file():
            return {"status": "UNKNOWN", "details": "Source image not found", "confidence": 0.0}

        try:
            with open(image_path, "rb") as f:
                f.seek(offset_bytes)
                sample = f.read(min(length_bytes, 64 * 1024))

            if not sample:
                return {"status": "CORRUPTED", "details": "Zero bytes read at offset", "confidence": 0.0}

            # 1. Dahua DHAV Stream Validation
            if "DHAV" in detected_format or sample.startswith(b"DHAV"):
                if not sample.startswith(b"DHAV"):
                    return {"status": "CORRUPTED", "details": "Missing DHAV magic bytes at offset", "confidence": 0.0}

                # Check if sample contains Annex B NAL start codes or subsequent DHAV blocks
                has_annex_b = b"\x00\x00\x00\x01" in sample or b"\x00\x00\x01" in sample
                has_second_dhav = sample.find(b"DHAV", 4) != -1

                if has_annex_b and has_second_dhav:
                    return {
                        "status": "VALID",
                        "details": "Confirmed multi-frame Dahua DHAV stream with Annex B video payload",
                        "confidence": 0.95,
                    }
                elif has_annex_b or has_second_dhav:
                    return {
                        "status": "PARTIAL",
                        "details": "Isolated Dahua DHAV frame fragment detected",
                        "confidence": 0.75,
                    }
                else:
                    return {
                        "status": "CORRUPTED",
                        "details": "DHAV header present but payload data is truncated or corrupt",
                        "confidence": 0.30,
                    }

            # 2. Hikvision HIKV / MPEG-PS Validation
            if "Hikvision" in detected_format or sample.startswith(b"HIKV") or sample.startswith(b"\x00\x00\x01\xba"):
                if sample.startswith(b"HIKV"):
                    if len(sample) > 32 and (b"\x00\x00\x01" in sample or sample.find(b"HIKV", 4) != -1):
                        return {
                            "status": "VALID",
                            "details": "Confirmed Hikvision HIKV stream container structure",
                            "confidence": 0.92,
                        }
                    return {
                        "status": "PARTIAL",
                        "details": "Hikvision HIKV header fragment detected",
                        "confidence": 0.70,
                    }
                elif sample.startswith(b"\x00\x00\x01\xba"):
                    # MPEG-PS Pack Header check
                    has_pes = b"\x00\x00\x01\xe0" in sample or b"\x00\x00\x01\xc0" in sample
                    if has_pes:
                        return {
                            "status": "VALID",
                            "details": "Confirmed MPEG-PS stream with video/audio PES packets",
                            "confidence": 0.90,
                        }
                    return {
                        "status": "PARTIAL",
                        "details": "MPEG-PS Pack Header detected without complete PES payload",
                        "confidence": 0.65,
                    }

            # 3. ISO MP4 Container Validation
            if "MP4" in detected_format or b"ftyp" in sample[:16]:
                ftyp_idx = sample.find(b"ftyp")
                if ftyp_idx >= 4:
                    box_len = int.from_bytes(sample[ftyp_idx - 4 : ftyp_idx], "big")
                    has_moov = b"moov" in sample
                    has_mdat = b"mdat" in sample

                    if has_moov and has_mdat:
                        return {
                            "status": "VALID",
                            "details": "Confirmed ISO MP4 container with ftyp, moov, and mdat boxes",
                            "confidence": 0.98,
                        }
                    elif has_mdat or has_moov or box_len < len(sample):
                        return {
                            "status": "PARTIAL",
                            "details": "ISO MP4 fragment detected (partial atom boxes)",
                            "confidence": 0.80,
                        }
                    else:
                        return {
                            "status": "CORRUPTED",
                            "details": "Malformed MP4 ftyp atom box",
                            "confidence": 0.25,
                        }

            return {
                "status": "UNKNOWN",
                "details": "Unrecognized or unsupported stream format for deep validation",
                "confidence": 0.50,
            }

        except Exception as e:
            return {"status": "CORRUPTED", "details": f"Validation error: {str(e)}", "confidence": 0.0}

    def extract_candidate_bytes(
        self, image_path: Path, offset_bytes: int, length_bytes: int, output_path: Path
    ) -> int:
        """Safely carves bytes from source disk image to output path without modifying source."""
        if not image_path.is_file():
            raise FileNotFoundError(f"Source image not found: {image_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        chunk_size = 64 * 1024
        written = 0

        with open(image_path, "rb") as src, open(output_path, "wb") as dst:
            src.seek(offset_bytes)
            remaining = length_bytes
            while remaining > 0:
                to_read = min(chunk_size, remaining)
                buf = src.read(to_read)
                if not buf:
                    break
                dst.write(buf)
                written += len(buf)
                remaining -= len(buf)

        return written

