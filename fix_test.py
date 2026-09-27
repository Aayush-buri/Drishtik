import sys
with open('backend/tests/test_recovery_and_ai.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update DHAV body to have valid structure
# b"DHAV" (4)
# frame_type (1) = 0xFD
# channel (1) = 0x00
# seq_num (2) = 0x0000
# payload_size (4) = 100
# timestamp (4) = 0
# unknown (8) = 0
# total header = 24 bytes
# payload = 100 bytes

valid_dhav_header = b"DHAV" + b"\\xFD\\x00\\x00\\x00" + b"\\x64\\x00\\x00\\x00" + b"\\x00" * 12
dhav_body = valid_dhav_header + b"\\x55" * 100

content = content.replace(
    'dhav_body = b"\\x01\\x00\\x00\\x00" + b"\\x00\\x00\\x00\\x01\\x67" + b"\\x55" * 1024 + b"DHAV" + b"\\x22" * 512',
    'dhav_body = b"\\xFD\\x00\\x00\\x00" + b"\\x64\\x00\\x00\\x00" + b"\\x00" * 12 + b"\\x55" * 100'
)

# test_4 validation test fix
content = content.replace(
    'valid_dhav_file.write_bytes(b"DHAV" + b"\\x01\\x00\\x00\\x00" + b"\\x00\\x00\\x00\\x01\\x67" + b"\\x55" * 100 + b"DHAV" + b"\\x00" * 50)',
    'valid_dhav_file.write_bytes(b"DHAV" + b"\\xFD\\x00\\x00\\x00" + b"\\x64\\x00\\x00\\x00" + b"\\x00" * 12 + b"\\x55" * 100)'
)
content = content.replace(
    'val_v = engine.validate_candidate_stream(valid_dhav_file, 0, 200, "DHAV")',
    'val_v = engine.validate_candidate_stream(valid_dhav_file, 0, 124, "DHAV")'
)

# Truncated
content = content.replace(
    'truncated_dhav_file.write_bytes(b"DHAV" + b"\\x01\\x00\\x00\\x00" + b"\\x00\\x00\\x00\\x01\\x67")',
    'truncated_dhav_file.write_bytes(b"DHAV" + b"\\xFD\\x00\\x00\\x00" + b"\\x64\\x00\\x00\\x00" + b"\\x00" * 12 + b"\\x55" * 20)'
)
content = content.replace(
    'val_p = engine.validate_candidate_stream(truncated_dhav_file, 0, 50, "DHAV")',
    'val_p = engine.validate_candidate_stream(truncated_dhav_file, 0, 44, "DHAV")'
)

content = content.replace(
    'frag_path.write_bytes(b"\\x00" * 128 + b"DHAV\\x00\\x00")',
    'frag_path.write_bytes(b"\\x00" * 128 + b"DHAV" + b"\\xFD\\x00\\x00\\x00" + b"\\x64\\x00\\x00\\x00" + b"\\x00" * 12 + b"\\x55" * 20)'
)

with open('backend/tests/test_recovery_and_ai.py', 'w', encoding='utf-8') as f:
    f.write(content)
