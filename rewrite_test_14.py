import sys
import ast

with open('backend/tests/test_proprietary_parsers.py', 'r', encoding='utf-8') as f:
    content = f.read()

# I will just truncate the file before the first occurrence of test_14...
# wait, there might be other tests after it.
start_idx = content.find('    def test_14_recovery_carving_candidates_detection')
end_idx = content.find('    def test_', start_idx + 10)
if end_idx == -1:
    end_idx = len(content)

new_test = '''    def test_14_recovery_carving_candidates_detection(tmp_path):
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
        assert hik_candidates[0].offset_bytes == 1580
'''

new_content = content[:start_idx] + new_test + content[end_idx:]

with open('backend/tests/test_proprietary_parsers.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
