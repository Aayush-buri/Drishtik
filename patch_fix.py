import sys

path = 'backend/app/services/blockchain_service.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(')        if anchor_result.success', ')\n\n        if anchor_result.success')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
