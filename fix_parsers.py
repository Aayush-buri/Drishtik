import sys

with open('backend/tests/test_proprietary_parsers.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''def test_14_recovery_carving_candidates_detection():
    """14. Carving strategies detect proprietary CCTV candidates in unallocated stream buffer."""
    dhav_strategy = DhavCarvingStrategy()
    hik_strategy = HikvisionCarvingStrategy()

    # Synthetic unallocated cluster buffer with embedded CCTV streams
    cluster_buffer = (
        b"\\x00" * 1024 +
        b"DHAV\\xfd\\x00\\x00\\x00\\x20\\x00\\x00\\x00" + b"\\xaa" * 32 +
        b"\\x00" * 512 +
        b"HIKV\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00" + b"\\xbb" * 32
    )

    dhav_candidates = list(dhav_strategy.carve_candidates(cluster_buffer))
    assert len(dhav_candidates) >= 1
    assert dhav_candidates[0].detected_vendor == "Dahua"
    assert dhav_candidates[0].offset_bytes == 1024

    hik_candidates = list(hik_strategy.carve_candidates(cluster_buffer))
    assert len(hik_candidates) >= 1
    assert hik_candidates[0].detected_vendor == "Hikvision"
    assert hik_candidates[0].offset_bytes == 1580'''

new_block = '''def test_14_recovery_carving_candidates_detection(tmp_path):
    """14. Carving strategies detect proprietary CCTV candidates in unallocated stream buffer."""
    dhav_strategy = DhavCarvingStrategy()
    hik_strategy = HikvisionCarvingStrategy()

    cluster_buffer = (
        b"\\x00" * 1024 +
        b"DHAV\\xfd\\x00\\x00\\x00\\x20\\x00\\x00\\x00" + b"\\xaa" * 32 +
        b"\\x00" * 512 +
        b"HIKV\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00" + b"\\xbb" * 32
    )
    fpath = tmp_path / "cluster.raw"
    fpath.write_bytes(cluster_buffer)

    dhav_candidates = list(dhav_strategy.carve(fpath, len(cluster_buffer)))
    assert len(dhav_candidates) >= 1
    assert dhav_candidates[0].detected_vendor == "Dahua"
    assert dhav_candidates[0].offset_bytes == 1024

    hik_candidates = list(hik_strategy.carve(fpath, len(cluster_buffer)))
    assert len(hik_candidates) >= 1
    assert hik_candidates[0].detected_vendor == "Hikvision"
    assert hik_candidates[0].offset_bytes == 1580'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('backend/tests/test_proprietary_parsers.py', 'w', encoding='utf-8') as f:
        f.write(content)
else:
    print("Could not find the block to replace!")
    sys.exit(1)
