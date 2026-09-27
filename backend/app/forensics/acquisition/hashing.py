import hashlib
from pathlib import Path
from typing import Tuple

def calculate_file_hashes(file_path: Path | str, chunk_size: int = 65536) -> Tuple[str, str, int]:
    """
    Calculates SHA-256 and MD5 hashes for a file incrementally.
    Never reads the entire large acquisition into RAM.
    Returns (sha256_hex, md5_hex, total_bytes_read).
    """
    file_path = Path(file_path)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    total_bytes = 0

    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
            md5.update(chunk)
            total_bytes += len(chunk)

    return sha256.hexdigest(), md5.hexdigest(), total_bytes
