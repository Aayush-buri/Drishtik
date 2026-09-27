import sys
with open('backend/tests/test_proprietary_parsers.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'assert hik_candidates[0].offset_bytes == 1580    def test_14_recovery_carving_candidates_detection' in line:
        new_lines.append('        assert hik_candidates[0].offset_bytes == 1580\n')
        continue
    new_lines.append(line)

with open('backend/tests/test_proprietary_parsers.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
