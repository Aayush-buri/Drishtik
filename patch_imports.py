import sys

path = 'backend/tests/test_blockchain_custody.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

imports = '''import pytest
from datetime import datetime, timezone, timedelta
from app.services.blockchain_service import BlockchainService
'''
content = content.replace('import pytest', imports)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
