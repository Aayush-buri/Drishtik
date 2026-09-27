import sys
with open('backend/tests/test_recovery_v1.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'detected_format="DHAV",',
    'detected_format="DHAV", vendor="Dahua",'
)

with open('backend/tests/test_recovery_v1.py', 'w', encoding='utf-8') as f:
    f.write(content)
