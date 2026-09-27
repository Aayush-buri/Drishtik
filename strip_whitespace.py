import sys

for path in ['backend/app/services/blockchain_service.py', 'backend/tests/test_blockchain_custody.py']:
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    with open(path, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(line.rstrip() + '\n')
