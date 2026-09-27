with open('backend/app/forensics/recovery/engine.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'def scan_candidates' in line:
            break
        print(line, end='')
