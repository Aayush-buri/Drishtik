from pathlib import Path
from typing import Optional, Callable
from app.forensics.acquisition.base import AcquisitionResult
from app.forensics.acquisition.file_copy import FileCopyAdapter

DISK_IMAGE_EXTENSIONS = {".raw", ".dd", ".img", ".bin", ".e01", ".iso", ".vmdk"}

class DiskImageAdapter(FileCopyAdapter):
    """
    Forensic disk image acquisition adapter.
    Handles physical and logical bitstream forensic images (.raw, .dd, .img, .bin, .e01),
    performing read-only verification, hashing, and storage into managed case vaults.
    """

    def validate_source(self) -> bool:
        if not super().validate_source():
            return False
        # Ensure it has a valid disk image or file extension, or permit raw bitstream
        ext = self.source_path.suffix.lower()
        return ext in DISK_IMAGE_EXTENSIONS or self.source_path.is_file()
