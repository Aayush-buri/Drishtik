import pytest
from pathlib import Path
import hashlib
from datetime import datetime, timezone
import struct

from parsers.common.demuxer import PacketType, BufferedFileReader
from parsers.dahua.demuxer import DahuaDemuxer, encode_dahua_timestamp
from parsers.hikvision.demuxer import HikvisionDemuxer

def create_dahua_frame(seq, payload, frame_type_byte=0xFD):
    ts_val = encode_dahua_timestamp(datetime(2026, 9, 5, 10, 0, seq))
    header = bytearray(24)
    header[0:4] = b"DHAV"
    header[4] = frame_type_byte
    header[5] = 0x00
    header[6:8] = seq.to_bytes(2, "little")
    header[8:12] = len(payload).to_bytes(4, "little")
    header[12:16] = ts_val.to_bytes(4, "little")

    footer = bytearray(8)
    footer[0:4] = b"dhav"
    footer[4:8] = (len(payload) + 32).to_bytes(4, "little")

    return bytes(header) + payload + bytes(footer)

def test_dahua_streaming_parser_basic(tmp_path: Path):
    demuxer = DahuaDemuxer()
    file_path = tmp_path / "test_dahua.dav"

    payload1 = b"\x00\x00\x00\x01\x67" + b"A" * 100
    payload2 = b"\x00\x00\x00\x01\x65" + b"B" * 200
    frame1 = create_dahua_frame(0, payload1)
    frame2 = create_dahua_frame(1, payload2)

    file_path.write_bytes(frame1 + frame2)
    original_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

    packets = list(demuxer.parse_packets(file_path))
    assert len(packets) == 2

    assert packets[0].packet_type == PacketType.VIDEO_I
    assert packets[0].payload_size == len(payload1)
    assert packets[0].data == payload1
    assert packets[0].stream_offset == 0

    assert packets[1].packet_type == PacketType.VIDEO_I
    assert packets[1].payload_size == len(payload2)
    assert packets[1].data == payload2
    assert packets[1].stream_offset == len(frame1)

    final_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    assert original_hash == final_hash

def test_dahua_streaming_buffer_split(tmp_path: Path, monkeypatch):
    demuxer = DahuaDemuxer()
    file_path = tmp_path / "test_split.dav"

    payload1 = b"C" * 100
    frame1 = create_dahua_frame(0, payload1)
    file_path.write_bytes(frame1)

    with monkeypatch.context() as m:
        original_init = BufferedFileReader.__init__
        def mocked_init(self, f_path, buffer_size=1048576):
            original_init(self, f_path, buffer_size=2)
        m.setattr(BufferedFileReader, "__init__", mocked_init)

        packets = list(demuxer.parse_packets(file_path))
        assert len(packets) == 1
        assert packets[0].data == payload1

def test_dahua_truncated_frame(tmp_path: Path):
    demuxer = DahuaDemuxer()
    file_path = tmp_path / "test_trunc.dav"
    payload = b"D" * 100
    frame = create_dahua_frame(0, payload)

    file_path.write_bytes(frame[:50])

    packets = list(demuxer.parse_packets(file_path))
    assert len(packets) == 1
    assert len(packets[0].data) == 26

def test_dahua_invalid_payload_large_tail_no_next_dhav(tmp_path: Path, monkeypatch):
    """A. Invalid payload_size with a very large tail containing NO next DHAV.
    F. Verify that the fallback does not call read_more() enough times to effectively consume the entire synthetic multi-GB tail.
    """
    demuxer = DahuaDemuxer()
    file_path = tmp_path / "test_invalid_tail.dav"

    # Create a frame with 0 payload_size (invalid)
    ts_val = encode_dahua_timestamp(datetime(2026, 9, 5, 10, 0, 0))
    header = bytearray(24)
    header[0:4] = b"DHAV"
    header[4] = 0xFD
    header[6:8] = (0).to_bytes(2, "little")
    header[8:12] = (0).to_bytes(4, "little") # INVALID PAYLOAD SIZE
    header[12:16] = ts_val.to_bytes(4, "little")

    # Very large tail, NO next DHAV
    # To keep the test fast but prove bounded reads, we make a 10MB tail
    # but monkeypatch read_more to count how many times it was called.
    # The max search window is 4MB. The buffer size is 1MB.
    # It should call read_more ~4-5 times, NOT 10 times.
    tail = b"X" * (10 * 1024 * 1024)
    file_path.write_bytes(bytes(header) + tail)

    read_more_calls = 0
    with monkeypatch.context() as m:
        original_read_more = BufferedFileReader.read_more
        def mocked_read_more(self):
            nonlocal read_more_calls
            read_more_calls += 1
            return original_read_more(self)
        m.setattr(BufferedFileReader, "read_more", mocked_read_more)

        packets = list(demuxer.parse_packets(file_path))

        # It should cap the search at 4MB, so it should read ~4-5 times.
        # Definitely not 10 times.
        assert read_more_calls <= 6
        assert len(packets) == 1
        # The actual payload size yielded should be whatever was in the buffer (up to 4MB + original 1MB = ~5MB max)
        assert len(packets[0].data) <= 5 * 1024 * 1024

def test_dahua_invalid_payload_next_dhav_across_buffer(tmp_path: Path, monkeypatch):
    """B. Invalid payload_size where the next DHAV signature crosses the artificial reader buffer boundary."""
    demuxer = DahuaDemuxer()
    file_path = tmp_path / "test_invalid_cross.dav"

    ts_val = encode_dahua_timestamp(datetime(2026, 9, 5, 10, 0, 0))
    header = bytearray(24)
    header[0:4] = b"DHAV"
    header[4] = 0xFD
    header[8:12] = (0).to_bytes(4, "little") # INVALID
    header[12:16] = ts_val.to_bytes(4, "little")

    # We will set buffer size to 50 bytes.
    # We place the next DHAV right at offset 72 so "DHAV" spans across 50 and 100.
    # Wait, if buffer is 50, first read is 50.
    # Let's just put it at 48 so "DH" is in first chunk, "AV" in second.
    padding = b"X" * (48 - len(header))

    payload2 = b"VALID_PAYLOAD"
    frame2 = create_dahua_frame(1, payload2)

    file_path.write_bytes(bytes(header) + padding + frame2)

    with monkeypatch.context() as m:
        original_init = BufferedFileReader.__init__
        def mocked_init(self, f_path, buffer_size=1048576):
            original_init(self, f_path, buffer_size=50)
        m.setattr(BufferedFileReader, "__init__", mocked_init)

        packets = list(demuxer.parse_packets(file_path))

        # We expect 2 packets. First one is the broken one spanning until next DHAV.
        assert len(packets) == 2
        # Broken packet size should be exactly len(padding)
        assert len(packets[0].data) == len(padding)
        # Second packet should be perfectly valid
        assert packets[1].data == payload2

def test_hikvision_streaming_basic(tmp_path: Path):
    demuxer = HikvisionDemuxer()
    file_path = tmp_path / "test_hik.hik"

    hikv_wrapper = b"HIKV\x01\x00\x00\x00\x00\x00\x00\x00" + b"\x00" * 20
    ps_pack = b"\x00\x00\x01\xba" + b"X" * 10

    payload = b"\x00\x00\x00\x01\x67" + b"HIK" * 20
    pes_len = len(payload) + 3
    pes_header = bytearray(b"\x00\x00\x01\xe0")
    pes_header += pes_len.to_bytes(2, "big")
    pes_header += b"\x80\x00\x00"
    pes_packet = bytes(pes_header) + payload

    file_path.write_bytes(hikv_wrapper + ps_pack + pes_packet + pes_packet)
    original_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

    packets = list(demuxer.parse_packets(file_path))
    assert len(packets) == 2
    assert packets[0].data == payload
    assert packets[1].data == payload

    final_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    assert original_hash == final_hash

def test_hikvision_buffer_split_and_large_payload(tmp_path: Path, monkeypatch):
    demuxer = HikvisionDemuxer()
    file_path = tmp_path / "test_hik_split.hik"

    payload = b"LARGE" * 1000
    pes_len = len(payload) + 3
    pes_header = bytearray(b"\x00\x00\x01\xe0")
    pes_header += pes_len.to_bytes(2, "big")
    pes_header += b"\x80\x00\x00"
    pes_packet = bytes(pes_header) + payload

    file_path.write_bytes(pes_packet)

    with monkeypatch.context() as m:
        original_init = BufferedFileReader.__init__
        def mocked_init(self, f_path, buffer_size=1048576):
            original_init(self, f_path, buffer_size=50)
        m.setattr(BufferedFileReader, "__init__", mocked_init)

        packets = list(demuxer.parse_packets(file_path))
        assert len(packets) == 1
        assert packets[0].data == payload

def test_hikvision_truncated_pes(tmp_path: Path):
    demuxer = HikvisionDemuxer()
    file_path = tmp_path / "test_hik_trunc.hik"

    payload = b"TRUNCATED" * 10
    pes_len = len(payload) + 3
    pes_header = bytearray(b"\x00\x00\x01\xe0")
    pes_header += pes_len.to_bytes(2, "big")
    pes_header += b"\x80\x00\x00"
    pes_packet = bytes(pes_header) + payload

    file_path.write_bytes(pes_packet[:30])

    packets = list(demuxer.parse_packets(file_path))
    assert len(packets) == 1
    assert len(packets[0].data) == 30 - 9
