with open('backend/tests/test_recovery_and_ai.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'def create_synthetic_raw_image' in line:
            for j in range(20):
                print(next(f), end='')
            break
