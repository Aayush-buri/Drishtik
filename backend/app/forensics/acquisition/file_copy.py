import hashlib
import os
from pathlib import Path
from typing import Optional, Callable
from app.forensics.acquisition.base import AcquisitionAdapter, AcquisitionResult

CHUNK_SIZE = 65536  # 64 KB

class FileCopyAdapter(AcquisitionAdapter):
    """
    Forensic single-file acquisition adapter.
    Preserves source strictly read-only, computes dual cryptographic hashes
    (SHA-256 and MD5) concurrently during streaming, and verifies post-copy integrity.
    """

    def validate_source(self) -> bool:
        return self.source_path.exists() and self.source_path.is_file()

    def estimate_size(self) -> int:
        if not self.validate_source():
            raise FileNotFoundError(f"Source file not found: {self.source_path}")
        return self.source_path.stat().st_size

    def acquire(
        self,
        destination_dir: Path,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> AcquisitionResult:
        if not self.validate_source():
            raise FileNotFoundError(f"Source file does not exist or is not a file: {self.source_path}")

        total_bytes = self.estimate_size()
        destination_dir = Path(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)

        target_filename = self.source_path.name
        destination_path = destination_dir / target_filename

        # Read-only stream from source to destination with dual hashing
        src_sha256 = hashlib.sha256()
        src_md5 = hashlib.md5()
        bytes_copied = 0

        # Snapshot source stat before copy to ensure read-only preservation
        src_stat_before = self.source_path.stat()

        with open(self.source_path, "rb") as src_file, open(destination_path, "wb") as dst_file:
            while chunk := src_file.read(CHUNK_SIZE):
                src_sha256.update(chunk)
                src_md5.update(chunk)
                dst_file.write(chunk)
                bytes_copied += len(chunk)
                if progress_callback and total_bytes > 0:
                    pct = int((bytes_copied / total_bytes) * 100)
                    progress_callback(min(pct, 99))

        # Verify source remained untouched
        src_stat_after = self.source_path.stat()
        if src_stat_before.st_mtime != src_stat_after.st_mtime or src_stat_before.st_size != src_stat_after.st_size:
            raise RuntimeError("CRITICAL FORENSIC VIOLATION: Source file was modified during acquisition!")

        # Calculate destination file hashes independently
        dst_sha256 = hashlib.sha256()
        dst_md5 = hashlib.md5()
        with open(destination_path, "rb") as dst_file:
            while chunk := dst_file.read(CHUNK_SIZE):
                dst_sha256.update(chunk)
                dst_md5.update(chunk)

        source_sha256_hex = src_sha256.hexdigest()
        dest_sha256_hex = dst_sha256.hexdigest()
        source_md5_hex = src_md5.hexdigest()
        dest_md5_hex = dst_md5.hexdigest()

        verified = (source_sha256_hex == dest_sha256_hex)
        error_msg = None if verified else "Forensic hash mismatch between source and destination."

        if progress_callback:
            progress_callback(100)

        return AcquisitionResult(
            source_sha256=source_sha256_hex,
            destination_sha256=dest_sha256_hex,
            source_md5=source_md5_hex,
            destination_md5=dest_md5_hex,
            size_bytes=bytes_copied,
            destination_path=destination_path,
            verified=verified,
            error_message=error_msg,
            item_count=1
        )
