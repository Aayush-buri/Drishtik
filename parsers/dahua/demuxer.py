"""Dahua DHAV container parser and demuxer.

Parses proprietary Dahua DAV containers, decodes 32-bit packed OSD timestamps,
extracts camera channel numbers, and demuxes raw H.264/H.265 elementary bitstreams.
"""
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from parsers.common.demuxer import BaseDemuxer, DemuxedPacket, DemuxSummary, PacketType


def decode_dahua_timestamp(raw_val: int) -> Optional[datetime]:
    """Decode Dahua 32-bit packed OSD timestamp bitfield.

    Bit layout:
    - bits 26..31 (6 bits): Year offset from 2000 (0..63 -> 2000..2063)
    - bits 22..25 (4 bits): Month (1..12)
    - bits 17..21 (5 bits): Day (1..31)
    - bits 12..16 (5 bits): Hour (0..23)
    - bits 6..11  (6 bits): Minute (0..59)
    - bits 0..5   (6 bits): Second (0..59)
    """
    try:
        year = ((raw_val >> 26) & 0x3F) + 2000
        month = (raw_val >> 22) & 0x0F
        day = (raw_val >> 17) & 0x1F
        hour = (raw_val >> 12) & 0x1F
        minute = (raw_val >> 6) & 0x3F
        second = raw_val & 0x3F

        if 2000 <= year <= 2060 and 1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
            return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def encode_dahua_timestamp(dt: datetime) -> int:
    """Encode datetime into Dahua 32-bit packed timestamp."""
    year_offset = max(0, min(63, dt.year - 2000))
    val = (year_offset & 0x3F) << 26
    val |= (dt.month & 0x0F) << 22
    val |= (dt.day & 0x1F) << 17
    val |= (dt.hour & 0x1F) << 12
    val |= (dt.minute & 0x3F) << 6
    val |= (dt.second & 0x3F)
    return val


class DahuaDemuxer(BaseDemuxer):
    """Forensic container parser and demuxer for Dahua DHAV streams."""

    HEADER_MAGIC = b"DHAV"
    FOOTER_MAGIC = b"dhav"

    def probe(self, file_path: Path) -> bool:
        """Inspect if the file starts with or contains DHAV frame headers."""
        if not file_path.is_file():
            return False
        try:
            with open(file_path, "rb") as f:
                header = f.read(64)
            return self.HEADER_MAGIC in header[:32]
        except Exception:
            return False

    def parse_packets(self, file_path: Path) -> Iterator[DemuxedPacket]:
        """Stream parsed DHAV frames from the file."""
        if not file_path.is_file():
            return

        with open(file_path, "rb") as f:
            data = f.read()

        file_size = len(data)
        offset = 0

        while offset < file_size:
            dhav_pos = data.find(self.HEADER_MAGIC, offset)
            if dhav_pos == -1 or dhav_pos + 16 > file_size:
                break

            # Parse 16+ byte header
            # Offset 0..4: 'DHAV'
            # Offset 4: type (0xfd/0xfb: I-frame, 0xfc: P-frame, 0xf0: audio)
            frame_type_byte = data[dhav_pos + 4]
            channel = data[dhav_pos + 5] + 1  # 1-indexed channel
            seq_num = struct.unpack_from("<H", data, dhav_pos + 6)[0]
            payload_size = struct.unpack_from("<I", data, dhav_pos + 8)[0]
            raw_ts = struct.unpack_from("<I", data, dhav_pos + 12)[0]

            dt_osd = decode_dahua_timestamp(raw_ts)

            # Determine packet type
            if frame_type_byte in (0xFD, 0xFB, 0x80, 0x81):
                packet_type = PacketType.VIDEO_I
            elif frame_type_byte in (0xFC, 0x82):
                packet_type = PacketType.VIDEO_P
            elif frame_type_byte in (0xF0, 0x90):
                packet_type = PacketType.AUDIO
            elif frame_type_byte in (0xF1,):
                packet_type = PacketType.OSD
            else:
                packet_type = PacketType.VIDEO_I if (seq_num == 0) else PacketType.VIDEO_P

            # Header size is standard 24 or 32 bytes in DHAV
            header_size = 24
            if dhav_pos + 32 <= file_size:
                header_size = 24

            payload_start = dhav_pos + header_size
            # Sanity check payload size against file bounds
            if payload_size == 0 or payload_start + payload_size > file_size:
                # Search next DHAV or dhav
                next_dhav = data.find(self.HEADER_MAGIC, dhav_pos + 4)
                if next_dhav != -1:
                    actual_payload_size = next_dhav - payload_start
                    # Check if footer exists
                    footer_pos = data.find(self.FOOTER_MAGIC, payload_start, next_dhav)
                    if footer_pos != -1:
                        actual_payload_size = footer_pos - payload_start
                else:
                    actual_payload_size = file_size - payload_start
            else:
                actual_payload_size = payload_size

            payload = data[payload_start : payload_start + max(0, actual_payload_size)]

            yield DemuxedPacket(
                packet_type=packet_type,
                channel_index=channel,
                data=payload,
                timestamp_osd=dt_osd,
                timestamp_ticks=raw_ts,
                stream_offset=dhav_pos,
                payload_size=len(payload),
                extra={"seq_num": seq_num, "frame_type_byte": hex(frame_type_byte)},
            )

            # Move forward
            offset = payload_start + len(payload)
            # Skip trailing 'dhav' footer (8 bytes: 'dhav' + 4-byte size) if present
            if offset + 8 <= file_size and data[offset : offset + 4] == self.FOOTER_MAGIC:
                offset += 8

    def extract_elementary_stream(
        self, file_path: Path, output_stream_path: Path
    ) -> DemuxSummary:
        """Extract Annex B elementary bitstream from DHAV frames and write to disk."""
        output_stream_path.parent.mkdir(parents=True, exist_ok=True)

        summary = DemuxSummary(container_format="Dahua DAV (DHAV)")
        start_ts: Optional[datetime] = None
        end_ts: Optional[datetime] = None
        detected_channel: Optional[int] = None
        detected_codec = "H.264"

        with open(output_stream_path, "wb") as out_f:
            for packet in self.parse_packets(file_path):
                summary.total_packets += 1

                if packet.channel_index:
                    detected_channel = packet.channel_index

                if packet.timestamp_osd:
                    if start_ts is None or packet.timestamp_osd < start_ts:
                        start_ts = packet.timestamp_osd
                    if end_ts is None or packet.timestamp_osd > end_ts:
                        end_ts = packet.timestamp_osd

                if packet.packet_type in (PacketType.VIDEO_I, PacketType.VIDEO_P):
                    summary.video_packets += 1
                    if packet.packet_type == PacketType.VIDEO_I:
                        summary.keyframe_count += 1

                    # Check NAL start code
                    payload = packet.data
                    if len(payload) > 4:
                        if payload[:4] != b"\x00\x00\x00\x01" and payload[:3] != b"\x00\x00\x01":
                            # Prepend Annex B 4-byte start code if missing
                            payload = b"\x00\x00\x00\x01" + payload

                        # Check if H.265 (HEVC) or H.264
                        first_nal = payload[4] if payload[:4] == b"\x00\x00\x00\x01" else payload[3]
                        if ((first_nal >> 1) & 0x3F) in (32, 33, 34):
                            detected_codec = "H.265"

                    out_f.write(payload)

                elif packet.packet_type == PacketType.AUDIO:
                    summary.audio_packets += 1

        summary.codec = detected_codec
        summary.channel_index = detected_channel
        summary.start_time_osd = start_ts
        summary.end_time_osd = end_ts
        if start_ts and end_ts:
            summary.duration_seconds = max(1.0, (end_ts - start_ts).total_seconds())

        return summary
