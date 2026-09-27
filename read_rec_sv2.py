with open('backend/app/services/recovery_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 'sha256_hash, md5_hash = compute_file_hashes' in line:
            print("".join(lines[i:i+60]))
            break
