import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Callable
from app.forensics.acquisition.base import AcquisitionAdapter, AcquisitionResult

CHUNK_SIZE = 65536

class DirectoryCopyAdapter(AcquisitionAdapter):
    """
    Forensic directory acquisition adapter.
    Recursively scans and acquires files in deterministic lexical order,
    computes individual file hashes, creates a forensic manifest, and computes
    overall source and destination manifest hashes.
    """

    def validate_source(self) -> bool:
        return self.source_path.exists() and self.source_path.is_dir()

    def estimate_size(self) -> int:
        if not self.validate_source():
            raise FileNotFoundError(f"Source directory not found: {self.source_path}")
        total = 0
        for entry in self.source_path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
        return total

    def acquire(
        self,
        destination_dir: Path,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> AcquisitionResult:
        if not self.validate_source():
            raise FileNotFoundError(f"Source directory not found: {self.source_path}")

        total_bytes = self.estimate_size()
        destination_dir = Path(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)

        files = sorted([p for p in self.source_path.rglob("*") if p.is_file()])
        bytes_copied = 0
        file_manifest = []

        # Snapshot source file stats to verify immutability
        src_stats_before = {p: (p.stat().st_mtime, p.stat().st_size) for p in files}

        overall_src_sha256 = hashlib.sha256()
        overall_src_md5 = hashlib.md5()

        for file_path in files:
            rel_path = file_path.relative_to(self.source_path)
            target_path = destination_dir / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)

            f_sha256 = hashlib.sha256()
            f_md5 = hashlib.md5()
            with open(file_path, "rb") as s_in, open(target_path, "wb") as d_out:
                while chunk := s_in.read(CHUNK_SIZE):
                    f_sha256.update(chunk)
                    f_md5.update(chunk)
                    overall_src_sha256.update(chunk)
                    overall_src_md5.update(chunk)
                    d_out.write(chunk)
                    bytes_copied += len(chunk)
                    if progress_callback and total_bytes > 0:
                        pct = int((bytes_copied / total_bytes) * 100)
                        progress_callback(min(pct, 99))

            file_manifest.append({
                "path": str(rel_path).replace("\\", "/"),
                "size_bytes": file_path.stat().st_size,
                "sha256": f_sha256.hexdigest(),
                "md5": f_md5.hexdigest()
            })

        # Verify source files remained untouched
        for p, (before_mtime, before_size) in src_stats_before.items():
            after_stat = p.stat()
            if after_stat.st_mtime != before_mtime or after_stat.st_size != before_size:
                raise RuntimeError("CRITICAL FORENSIC VIOLATION: Source directory content was modified during acquisition!")

        # Independent destination hash verification
        overall_dst_sha256 = hashlib.sha256()
        overall_dst_md5 = hashlib.md5()

        for item in file_manifest:
            dst_file = destination_dir / item["path"]
            with open(dst_file, "rb") as d_in:
                while chunk := d_in.read(CHUNK_SIZE):
                    overall_dst_sha256.update(chunk)
                    overall_dst_md5.update(chunk)

        # Write manifest file to destination
        manifest_path = destination_dir / "acquisition_manifest.json"
        manifest_data = {
            "source_directory": str(self.source_path),
            "file_count": len(files),
            "total_bytes": bytes_copied,
            "overall_sha256": overall_src_sha256.hexdigest(),
            "files": file_manifest
        }
        with open(manifest_path, "w", encoding="utf-8") as m_out:
            json.dump(manifest_data, m_out, indent=2)

        source_sha256_hex = overall_src_sha256.hexdigest()
        dest_sha256_hex = overall_dst_sha256.hexdigest()
        source_md5_hex = overall_src_md5.hexdigest()
        dest_md5_hex = overall_dst_md5.hexdigest()

        verified = (source_sha256_hex == dest_sha256_hex)
        error_msg = None if verified else "Forensic directory hash mismatch."

        if progress_callback:
            progress_callback(100)

        return AcquisitionResult(
            source_sha256=source_sha256_hex,
            destination_sha256=dest_sha256_hex,
            source_md5=source_md5_hex,
            destination_md5=dest_md5_hex,
            size_bytes=bytes_copied,
            destination_path=destination_dir,
            verified=verified,
            error_message=error_msg,
            item_count=len(files)
        )
