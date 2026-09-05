"""Hikvision container parser and demuxer.

Handles Hikvision MPEG-PS containers and HIKV stream extraction.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from parsers.common.demuxer import BaseDemuxer, DemuxedPacket, DemuxSummary, PacketType


class HikvisionDemuxer(BaseDemuxer):
    """Forensic container parser and demuxer for Hikvision MPEG-PS and HIKV streams."""

    HIKV_MAGIC = b"HIKV"
    MPEG_PS_PACK = b"\x00\x00\x01\xba"
    PES_VIDEO_PREFIX = b"\x00\x00\x01\xe0"

    def probe(self, file_path: Path) -> bool:
        if not file_path.is_file():
            return False
        try:
            with open(file_path, "rb") as f:
                header = f.read(64)
            return header.startswith(self.HIKV_MAGIC) or header.startswith(self.MPEG_PS_PACK)
        except Exception:
            return False

    def parse_packets(self, file_path: Path) -> Iterator[DemuxedPacket]:
        if not file_path.is_file():
            return

        with open(file_path, "rb") as f:
            data = f.read()

        file_size = len(data)
        offset = 0

        # If HIKV header, skip header (typically 16 to 40 bytes)
        if data.startswith(self.HIKV_MAGIC):
            ps_pos = data.find(self.MPEG_PS_PACK, 4)
            if ps_pos != -1:
                offset = ps_pos
            else:
                offset = 16

        # Scan for PES video packets (00 00 01 E0) or PS packs
        while offset < file_size:
            pes_pos = data.find(self.PES_VIDEO_PREFIX, offset)
            if pes_pos == -1 or pes_pos + 6 > file_size:
                # If no PES packets, check if raw NAL stream follows
                break

            # PES packet length is in bytes 4..6
            pes_len = int.from_bytes(data[pes_pos + 4 : pes_pos + 6], "big")
            header_len = 6
            # PES optional header check
            if pes_pos + 9 <= file_size:
                opt_header_len = data[pes_pos + 8]
                header_len = 9 + opt_header_len

            payload_start = pes_pos + header_len
            payload_end = (pes_pos + 6 + pes_len) if pes_len > 0 else (payload_start + 4096)
            payload_end = min(payload_end, file_size)

            payload = data[payload_start:payload_end]

            yield DemuxedPacket(
                packet_type=PacketType.VIDEO_I if b"\x00\x00\x00\x01\x67" in payload or b"\x00\x00\x00\x01\x65" in payload else PacketType.VIDEO_P,
                channel_index=1,
                data=payload,
                stream_offset=pes_pos,
                payload_size=len(payload),
            )

            offset = max(payload_end, pes_pos + 6)

    def extract_elementary_stream(
        self, file_path: Path, output_stream_path: Path
    ) -> DemuxSummary:
        output_stream_path.parent.mkdir(parents=True, exist_ok=True)
        summary = DemuxSummary(container_format="Hikvision MPEG-PS / HIKV")
        packets_found = 0

        with open(output_stream_path, "wb") as out_f:
            for packet in self.parse_packets(file_path):
                packets_found += 1
                summary.total_packets += 1
                summary.video_packets += 1
                if packet.packet_type == PacketType.VIDEO_I:
                    summary.keyframe_count += 1

                payload = packet.data
                if len(payload) > 4 and payload[:4] != b"\x00\x00\x00\x01" and payload[:3] != b"\x00\x00\x01":
                    payload = b"\x00\x00\x00\x01" + payload
                out_f.write(payload)

        summary.channel_index = 1
        summary.codec = "H.264"
        return summary
