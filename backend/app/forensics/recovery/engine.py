"""Forensic recovery engine for signature carving and structural validation."""
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import struct

from parsers.common.demuxer import BufferedFileReader

logger = logging.getLogger(__name__)


@dataclass
class DiskImageInfo:
    image_format: str
    size_bytes: int
    is_supported: bool
    sector_size: Optional[int] = None
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
    def carve(self, image_path: Path, max_bytes: int) -> List[RecoveryCandidate]:
        """Scan file up to max_bytes and return structural candidates found."""
        pass


class DhavCarvingStrategy(CarvingStrategy):
    """Scans for Dahua DHAV frame sequences using structural boundaries."""

    strategy_name = "Dahua DHAV Carver"

    def carve(self, image_path: Path, max_bytes: int) -> List[RecoveryCandidate]:
        candidates: List[RecoveryCandidate] = []
        file_size = image_path.stat().st_size
        limit = min(max_bytes, file_size)

        with BufferedFileReader(image_path) as reader:
            while reader.global_offset < limit:
                if reader.size < 4:
                    if not reader.read_more(limit):
                        break

                dhav_pos = reader.find(b"DHAV")
                if dhav_pos == -1:
                    consume_len = max(0, reader.size - 3)
                    if reader.global_offset + consume_len >= limit:
                        break
                    reader.advance(consume_len)
                    if not reader.read_more(limit):
                        break
                    continue

                abs_offset = reader.global_offset + dhav_pos
                if abs_offset >= limit:
                    break

                reader.advance(dhav_pos)

                cand_channel = -1
                last_seq = -1
                frames = 0
                first_ts = None
                last_ts = None
                total_payload = 0
                current_cand_len = 0
                status = "VALID"
                scan_limit_hit = False

                while True:
                    while reader.size < 24:
                        if not reader.read_more(limit):
                            break
                    if reader.size < 24:
                        if frames > 0 and reader.size > 0:
                            status = "PARTIAL"
                        if frames == 0:
                            reader.advance(reader.size)
                        break

                    data = reader.data
                    if data[0:4] != b"DHAV":
                        break

                    frame_channel = data[5] + 1
                    seq_num = struct.unpack_from("<H", data, 6)[0]
                    payload_size = struct.unpack_from("<I", data, 8)[0]
                    raw_ts = struct.unpack_from("<I", data, 12)[0]

                    if payload_size == 0 or payload_size > 10 * 1024 * 1024:
                        if frames == 0:
                            reader.advance(4)
                        break

                    if cand_channel == -1:
                        cand_channel = frame_channel
                    elif frame_channel != cand_channel:
                        break

                    if last_seq != -1:
                        expected_seq = (last_seq + 1) % 65536
                        if seq_num != expected_seq and seq_num != 0:
                            break

                    frame_len = 24 + payload_size

                    # Check scan limit bounds
                    if abs_offset + current_cand_len + frame_len > limit:
                        scan_limit_hit = True
                        status = "PARTIAL"
                        allowed_bytes = limit - (abs_offset + current_cand_len)

                        while reader.size < allowed_bytes:
                            if not reader.read_more(limit):
                                break

                        available = min(reader.size, allowed_bytes)
                        current_cand_len += available
                        frames += 1
                        reader.advance(available)
                        break

                    while reader.size < frame_len:
                        if not reader.read_more(limit):
                            break

                    if reader.size < frame_len:
                        status = "PARTIAL"
                        current_cand_len += reader.size
                        frames += 1
                        reader.advance(reader.size)
                        break

                    current_cand_len += frame_len
                    frames += 1
                    last_seq = seq_num
                    if frames == 1:
                        first_ts = raw_ts
                    last_ts = raw_ts
                    total_payload += payload_size

                    reader.advance(frame_len)

                    if reader.size >= 4 and reader.data[0:4] == b"dhav":
                        if abs_offset + current_cand_len + 4 > limit:
                            # Skip footer if it exceeds limit
                            pass
                        else:
                            reader.advance(4)
                            current_cand_len += 4
                    elif reader.size < 4:
                        reader.read_more(limit)
                        if reader.size >= 4 and reader.data[0:4] == b"dhav":
                            if abs_offset + current_cand_len + 4 <= limit:
                                reader.advance(4)
                                current_cand_len += 4

                if frames > 0:
                    confidence = 0.95 if status == "VALID" and frames > 1 else (0.85 if frames == 1 else 0.70)
                    meta = {
                        "channel": cand_channel,
                        "first_sequence": seq_num if frames==1 else (last_seq - frames + 1)%65536,
                        "last_sequence": last_seq,
                        "frame_count": frames,
                        "first_timestamp": first_ts,
                        "last_timestamp": last_ts,
                        "payload_bytes": total_payload,
                        "structural_status": status,
                    }
                    if scan_limit_hit:
                        meta["scan_limit_truncated"] = True
                    candidates.append(
                        RecoveryCandidate(
                            candidate_id=f"REC-DHAV-{abs_offset:08X}",
                            offset_bytes=abs_offset,
                            length_bytes=current_cand_len,
                            detected_vendor="Dahua",
                            format_name="Dahua DAV Frame",
                            confidence=confidence,
                            signature_matched="DHAV",
                            metadata=meta,
                        )
                    )

        return candidates


class HikvisionCarvingStrategy(CarvingStrategy):
    """Scans for Hikvision HIKV / MPEG-PS stream signatures."""

    strategy_name = "Hikvision Carver"

    def carve(self, image_path: Path, max_bytes: int) -> List[RecoveryCandidate]:
        candidates: List[RecoveryCandidate] = []
        file_size = image_path.stat().st_size
        limit = min(max_bytes, file_size)

        with BufferedFileReader(image_path) as reader:
            while reader.global_offset < limit:
                if reader.size < 4:
                    if not reader.read_more(limit):
                        break

                pos_hikv = reader.find(b"HIKV")
                pos_ps = reader.find(b"\x00\x00\x01\xba")

                pos = -1
                is_hikv = False
                if pos_hikv != -1 and pos_ps != -1:
                    if pos_hikv < pos_ps:
                        pos = pos_hikv
                        is_hikv = True
                    else:
                        pos = pos_ps
                elif pos_hikv != -1:
                    pos = pos_hikv
                    is_hikv = True
                elif pos_ps != -1:
                    pos = pos_ps

                if pos == -1:
                    consume_len = max(0, reader.size - 3)
                    if reader.global_offset + consume_len >= limit:
                        break
                    reader.advance(consume_len)
                    if not reader.read_more(limit):
                        break
                    continue

                abs_offset = reader.global_offset + pos
                if abs_offset >= limit:
                    break

                reader.advance(pos)

                if is_hikv:
                    # Proprietary HIKV wrapper
                    current_cand_len = 4
                    reader.advance(4)
                    found_ps = False
                    status = "PARTIAL"

                    while True:
                        pos_ba = reader.find(b"\x00\x00\x01\xba")
                        if pos_ba != -1:
                            found_ps = True
                            break

                        consume_len = max(0, reader.size - 3)
                        if abs_offset + current_cand_len + consume_len >= limit:
                            # Hit limit without finding MPEG-PS
                            avail = limit - (abs_offset + current_cand_len)
                            current_cand_len += avail
                            reader.advance(avail)
                            break

                        reader.advance(consume_len)
                        current_cand_len += consume_len
                        if not reader.read_more(limit):
                            current_cand_len += reader.size
                            reader.advance(reader.size)
                            break

                    if found_ps:
                        current_cand_len += pos_ba
                        reader.advance(pos_ba)

                        ps_start_offset = abs_offset + current_cand_len
                        frames = 0
                        scan_limit_hit = False
                        status = "VALID"

                        # Parse MPEG-PS structurally
                        while True:
                            while reader.size < 14:
                                if not reader.read_more(limit):
                                    break
                            if reader.size < 14:
                                if frames > 0 and reader.size > 0: status = "PARTIAL"
                                break

                            data = reader.data
                            if data[0:4] != b"\x00\x00\x01\xba":
                                break

                            pack_len = 14 + (data[13] & 0x07)

                            while reader.size < pack_len + 6:
                                if not reader.read_more(limit):
                                    break
                            if reader.size < pack_len + 6:
                                status = "PARTIAL"
                                avail = reader.size
                                if abs_offset + current_cand_len + avail > limit:
                                    avail = limit - (abs_offset + current_cand_len)
                                    scan_limit_hit = True
                                current_cand_len += avail
                                reader.advance(avail)
                                frames += 1
                                break

                            data = reader.data
                            if data[pack_len:pack_len+3] != b"\x00\x00\x01":
                                pass

                            pes_start = pack_len
                            pes_code = data[pes_start+3]
                            pes_len = struct.unpack_from(">H", data, pes_start+4)[0]

                            if pes_len == 0:
                                next_ba = reader.find(b"\x00\x00\x01\xba", pes_start+4)
                                if next_ba != -1:
                                    frame_len = next_ba
                                else:
                                    found_next = False
                                    while reader.read_more(limit):
                                        next_ba = reader.find(b"\x00\x00\x01\xba", pes_start+4)
                                        if next_ba != -1:
                                            frame_len = next_ba
                                            found_next = True
                                            break
                                    if not found_next:
                                        status = "PARTIAL"
                                        frame_len = reader.size
                            else:
                                frame_len = pack_len + 6 + pes_len

                            if abs_offset + current_cand_len + frame_len > limit:
                                scan_limit_hit = True
                                status = "PARTIAL"
                                allowed = limit - (abs_offset + current_cand_len)
                                while reader.size < allowed:
                                    if not reader.read_more(limit):
                                        break
                                avail = min(reader.size, allowed)
                                current_cand_len += avail
                                reader.advance(avail)
                                frames += 1
                                break

                            while reader.size < frame_len:
                                if not reader.read_more(limit):
                                    break

                            if reader.size < frame_len:
                                status = "PARTIAL"
                                current_cand_len += reader.size
                                reader.advance(reader.size)
                                frames += 1
                                break

                            current_cand_len += frame_len
                            reader.advance(frame_len)
                            frames += 1

                        meta = {
                            "structural_status": status,
                            "wrapper_extent_known": False,
                            "mpeg_ps_start_offset": ps_start_offset,
                            "mpeg_ps_structural_length": (abs_offset + current_cand_len) - ps_start_offset,
                            "frame_count": frames,
                            "details": "HIKV wrapper boundary unverified; candidate bounded by MPEG-PS structure"
                        }
                        if scan_limit_hit:
                            meta["scan_limit_truncated"] = True

                        candidates.append(
                            RecoveryCandidate(
                                candidate_id=f"REC-HIK-{abs_offset:08X}",
                                offset_bytes=abs_offset,
                                length_bytes=current_cand_len,
                                detected_vendor="Hikvision",
                                format_name="Hikvision HIKV Frame",
                                confidence=0.85 if frames > 0 else 0.70,
                                signature_matched="HIKV",
                                metadata=meta,
                            )
                        )
                    else:
                        meta = {
                            "structural_status": "PARTIAL",
                            "wrapper_extent_known": False,
                            "details": "HIKV signature found but no subsequent MPEG-PS structure could be validated"
                        }
                        if current_cand_len > 4: # Hit limit or EOF while searching
                            meta["scan_limit_truncated"] = True

                        candidates.append(
                            RecoveryCandidate(
                                candidate_id=f"REC-HIK-{abs_offset:08X}",
                                offset_bytes=abs_offset,
                                length_bytes=current_cand_len,
                                detected_vendor="Hikvision",
                                format_name="Hikvision HIKV Header",
                                confidence=0.60,
                                signature_matched="HIKV",
                                metadata=meta,
                            )
                        )
                else:
                    # MPEG-PS Pack
                    current_cand_len = 0
                    status = "VALID"
                    frames = 0
                    scan_limit_hit = False

                    while True:
                        while reader.size < 14:
                            if not reader.read_more(limit):
                                break
                        if reader.size < 14:
                            if frames > 0 and reader.size > 0: status = "PARTIAL"
                            if frames == 0: reader.advance(reader.size)
                            break

                        data = reader.data
                        if data[0:4] != b"\x00\x00\x01\xba":
                            break

                        pack_len = 14 + (data[13] & 0x07)

                        while reader.size < pack_len + 6:
                            if not reader.read_more(limit):
                                break
                        if reader.size < pack_len + 6:
                            status = "PARTIAL"
                            avail = reader.size
                            if abs_offset + current_cand_len + avail > limit:
                                avail = limit - (abs_offset + current_cand_len)
                                scan_limit_hit = True
                            current_cand_len += avail
                            reader.advance(avail)
                            frames += 1
                            break

                        data = reader.data
                        pes_start = pack_len
                        pes_code = data[pes_start+3]
                        pes_len = struct.unpack_from(">H", data, pes_start+4)[0]

                        if pes_len == 0:
                            next_ba = reader.find(b"\x00\x00\x01\xba", pes_start+4)
                            if next_ba != -1:
                                frame_len = next_ba
                            else:
                                found_next = False
                                while reader.read_more(limit):
                                    next_ba = reader.find(b"\x00\x00\x01\xba", pes_start+4)
                                    if next_ba != -1:
                                        frame_len = next_ba
                                        found_next = True
                                        break
                                if not found_next:
                                    status = "PARTIAL"
                                    frame_len = reader.size
                        else:
                            frame_len = pack_len + 6 + pes_len

                        if abs_offset + current_cand_len + frame_len > limit:
                            scan_limit_hit = True
                            status = "PARTIAL"
                            allowed = limit - (abs_offset + current_cand_len)
                            while reader.size < allowed:
                                if not reader.read_more(limit):
                                    break
                            avail = min(reader.size, allowed)
                            current_cand_len += avail
                            reader.advance(avail)
                            frames += 1
                            break

                        while reader.size < frame_len:
                            if not reader.read_more(limit):
                                break

                        if reader.size < frame_len:
                            status = "PARTIAL"
                            current_cand_len += reader.size
                            reader.advance(reader.size)
                            frames += 1
                            break

                        current_cand_len += frame_len
                        reader.advance(frame_len)
                        frames += 1

                    if frames > 0:
                        meta = {"structural_status": status, "frame_count": frames}
                        if scan_limit_hit:
                            meta["scan_limit_truncated"] = True
                        candidates.append(
                            RecoveryCandidate(
                                candidate_id=f"REC-PS-{abs_offset:08X}",
                                offset_bytes=abs_offset,
                                length_bytes=current_cand_len,
                                detected_vendor="Hikvision",
                                format_name="MPEG-PS Pack",
                                confidence=0.90 if status == "VALID" else 0.70,
                                signature_matched="000001BA",
                                metadata=meta,
                            )
                        )

        return candidates


class Mp4FtypCarvingStrategy(CarvingStrategy):
    """Scans for ISO MP4 ftyp box boundaries."""

    strategy_name = "MP4 ftyp Carver"

    def carve(self, image_path: Path, max_bytes: int) -> List[RecoveryCandidate]:
        candidates: List[RecoveryCandidate] = []
        file_size = image_path.stat().st_size
        limit = min(max_bytes, file_size)

        with BufferedFileReader(image_path) as reader:
            while reader.global_offset < limit:
                if reader.size < 8:
                    if not reader.read_more(limit):
                        break

                pos = reader.find(b"ftyp")
                if pos >= 4:
                    abs_offset = reader.global_offset + pos - 4
                    if abs_offset >= limit:
                        break

                    reader.advance(pos - 4)

                    status = "VALID"
                    current_cand_len = 0
                    has_moov = False
                    has_mdat = False
                    scan_limit_hit = False

                    while True:
                        while reader.size < 8:
                            if not reader.read_more(limit):
                                break
                        if reader.size < 8:
                            if current_cand_len == 0: reader.advance(reader.size)
                            break

                        box_size = int.from_bytes(reader.data[0:4], "big")
                        box_type = reader.data[4:8]

                        if box_size < 8:
                            status = "CORRUPTED" if current_cand_len == 0 else "PARTIAL"
                            break

                        if abs_offset + current_cand_len + box_size > limit:
                            scan_limit_hit = True
                            status = "PARTIAL"
                            allowed = limit - (abs_offset + current_cand_len)
                            while reader.size < allowed:
                                if not reader.read_more(limit):
                                    break
                            avail = min(reader.size, allowed)
                            current_cand_len += avail
                            reader.advance(avail)
                            break

                        if box_type == b"moov":
                            has_moov = True
                        elif box_type == b"mdat":
                            has_mdat = True

                        while reader.size < box_size:
                            if not reader.read_more(limit):
                                break

                        if reader.size < box_size:
                            status = "PARTIAL"
                            current_cand_len += reader.size
                            reader.advance(reader.size)
                            break

                        current_cand_len += box_size
                        reader.advance(box_size)

                    confidence = 0.95
                    if not (has_moov and has_mdat):
                        status = "PARTIAL"
                        confidence = 0.70

                    if current_cand_len > 0:
                        meta = {"structural_status": status, "has_moov": has_moov, "has_mdat": has_mdat}
                        if scan_limit_hit:
                            meta["scan_limit_truncated"] = True
                        candidates.append(
                            RecoveryCandidate(
                                candidate_id=f"REC-MP4-{abs_offset:08X}",
                                offset_bytes=abs_offset,
                                length_bytes=current_cand_len,
                                detected_vendor="Generic",
                                format_name="ISO MP4 Container",
                                confidence=confidence,
                                signature_matched="ftyp",
                                metadata=meta,
                            )
                        )
                else:
                    consume_len = max(0, reader.size - 7)
                    if reader.global_offset + consume_len >= limit:
                        break
                    reader.advance(consume_len)
                    if not reader.read_more(limit):
                        break

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
        return self.strategies

    def is_supported_image(self, image_path: Path) -> bool:
        info = self.probe_image(Path(image_path))
        return info.is_supported

    def probe_image(self, image_path: Path) -> DiskImageInfo:
        if not image_path.is_file():
            return DiskImageInfo(image_format="UNKNOWN", size_bytes=0, is_supported=False, details="File not found")

        size = image_path.stat().st_size
        suffix = image_path.suffix.lower()

        with open(image_path, "rb") as f:
            header = f.read(512)

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
        return self.probe_image(image_path)

    def scan_candidates(
        self, image_path: Path, max_bytes: int = 10 * 1024 * 1024
    ) -> List[RecoveryCandidate]:
        candidates: List[RecoveryCandidate] = []
        if not image_path.is_file():
            return candidates

        for strat in self.strategies:
            found = strat.carve(image_path, max_bytes)
            candidates.extend(found)

        return candidates

    def validate_candidate_stream(
        self, image_path: Path, offset_bytes: int, length_bytes: int, detected_format: str
    ) -> Dict[str, Any]:
        if not image_path.is_file():
            return {"status": "UNKNOWN", "details": "Source image not found", "confidence": 0.0}

        try:
            with open(image_path, "rb") as f:
                f.seek(offset_bytes)
                sample = f.read(min(length_bytes, 64 * 1024))

            if not sample:
                return {"status": "CORRUPTED", "details": "Zero bytes read at offset", "confidence": 0.0}

            # If the strategy has already validated and determined length, we can rely on that as well.
            # 1. Dahua DHAV
            if "DHAV" in detected_format or sample.startswith(b"DHAV"):
                if not sample.startswith(b"DHAV"):
                    return {"status": "CORRUPTED", "details": "Missing DHAV magic bytes at offset", "confidence": 0.0}

                has_second_dhav = sample.find(b"DHAV", 4) != -1
                has_annex_b = b"\x00\x00\x00\x01" in sample or b"\x00\x00\x01" in sample

                if length_bytes < 24:
                    return {"status": "CORRUPTED", "details": "DHAV header present but payload data is severely truncated", "confidence": 0.30}

                payload_size = struct.unpack_from("<I", sample, 8)[0]
                if payload_size == 0 or payload_size > 10 * 1024 * 1024:
                    return {"status": "CORRUPTED", "details": "Invalid DHAV payload size", "confidence": 0.30}

                # If the length is equal to exactly what we carved, it means we reached the structural end!
                if (has_annex_b and has_second_dhav) or length_bytes == 24 + payload_size:
                    return {"status": "VALID", "details": f"Confirmed Dahua DHAV stream/frame ({length_bytes} bytes)", "confidence": 0.95}
                elif has_annex_b or has_second_dhav or length_bytes < 24 + payload_size:
                    return {"status": "PARTIAL", "details": f"Isolated or truncated Dahua DHAV frame detected ({length_bytes} bytes)", "confidence": 0.75}
                else:
                    return {"status": "CORRUPTED", "details": "DHAV header present but payload data is malformed", "confidence": 0.30}

            # 2. Hikvision
            if "Hikvision" in detected_format or sample.startswith(b"HIKV") or sample.startswith(b"\x00\x00\x01\xba"):
                if sample.startswith(b"HIKV"):
                    return {"status": "PARTIAL", "details": "Hikvision HIKV header fragment detected", "confidence": 0.70}
                elif sample.startswith(b"\x00\x00\x01\xba"):
                    has_pes = b"\x00\x00\x01\xe0" in sample or b"\x00\x00\x01\xc0" in sample
                    if has_pes and length_bytes > 32:
                        return {"status": "VALID", "details": f"Confirmed MPEG-PS stream ({length_bytes} bytes)", "confidence": 0.90}
                    return {"status": "PARTIAL", "details": "MPEG-PS Pack Header detected without complete PES payload", "confidence": 0.65}

            # 3. MP4
            if "MP4" in detected_format or b"ftyp" in sample[:16]:
                ftyp_idx = sample.find(b"ftyp")
                if ftyp_idx >= 4:
                    box_len = int.from_bytes(sample[ftyp_idx - 4 : ftyp_idx], "big")
                    has_moov = b"moov" in sample
                    has_mdat = b"mdat" in sample

                    if has_moov and has_mdat:
                        return {"status": "VALID", "details": f"Confirmed ISO MP4 container with ftyp, moov, and mdat boxes ({length_bytes} bytes)", "confidence": 0.98}
                    elif has_mdat or has_moov or box_len <= len(sample):
                        return {"status": "PARTIAL", "details": f"ISO MP4 fragment detected ({length_bytes} bytes)", "confidence": 0.80}
                    else:
                        return {"status": "CORRUPTED", "details": "Malformed MP4 ftyp atom box", "confidence": 0.25}

            return {"status": "UNKNOWN", "details": "Unrecognized stream format", "confidence": 0.50}

        except Exception as e:
            return {"status": "CORRUPTED", "details": f"Validation error: {str(e)}", "confidence": 0.0}

    def extract_candidate_bytes(
        self, image_path: Path, offset_bytes: int, length_bytes: int, output_path: Path
    ) -> int:
        if not image_path.is_file():
            raise FileNotFoundError(f"Source image not found: {image_path}")

        file_size = image_path.stat().st_size
        if offset_bytes < 0 or length_bytes <= 0 or offset_bytes >= file_size:
            return 0

        # Truncate length if it exceeds EOF safely
        safe_length = min(length_bytes, file_size - offset_bytes)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        chunk_size = 64 * 1024
        written = 0

        with open(image_path, "rb") as src, open(output_path, "wb") as dst:
            src.seek(offset_bytes)
            remaining = safe_length
            while remaining > 0:
                to_read = min(chunk_size, remaining)
                buf = src.read(to_read)
                if not buf:
                    break
                dst.write(buf)
                written += len(buf)
                remaining -= len(buf)

        return written
