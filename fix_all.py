import sys

# 2. Fix test_proprietary_parsers.py
with open('backend/tests/test_proprietary_parsers.py', 'r', encoding='utf-8') as f:
    t_content = f.read()

# I will find the exact string to replace. Let's just find the function def.
start_idx = t_content.find('    def test_14_recovery_carving_candidates_detection():')
end_idx = t_content.find('dhav_candidates = list(dhav_strategy.carve_candidates(cluster_buffer))', start_idx)
end_idx += len('dhav_candidates = list(dhav_strategy.carve_candidates(cluster_buffer))')

repl = '''    def test_14_recovery_carving_candidates_detection(tmp_path):
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
        fpath = tmp_path / "cluster.raw"
        fpath.write_bytes(cluster_buffer)
    
        dhav_candidates = list(dhav_strategy.carve(fpath, len(cluster_buffer)))'''

t_content = t_content[:start_idx] + repl + t_content[end_idx:]

with open('backend/tests/test_proprietary_parsers.py', 'w', encoding='utf-8') as f:
    f.write(t_content)

