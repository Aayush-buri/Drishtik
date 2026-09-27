from pathlib import Path
import enum
from dataclasses import dataclass
from typing import Optional, Callable

from app.forensics.acquisition.base import AcquisitionResult
from app.forensics.acquisition.file_copy import FileCopyAdapter
from app.forensics.recovery.engine import DiskImageInfo

DISK_IMAGE_EXTENSIONS = {".raw", ".dd", ".img", ".bin", ".e01", ".iso", ".vmdk"}

class DiskImageInspectionStatus(str, enum.Enum):
    SUPPORTED = "SUPPORTED"
    DETECTED_BUT_UNAVAILABLE = "DETECTED_BUT_UNAVAILABLE"
    INVALID_OR_UNREADABLE = "INVALID_OR_UNREADABLE"
    UNSUPPORTED = "UNSUPPORTED"

@dataclass
class DiskImageInspectionResult:
    status: DiskImageInspectionStatus
    info: Optional[DiskImageInfo] = None
    message: str = ""

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

    def inspect_image(self) -> DiskImageInspectionResult:
        """
        Inspects the source image in a strictly read-only manner.
        Returns basic forensic container metadata and validation status.
        """
        if not self.source_path.is_file():
            return DiskImageInspectionResult(
                status=DiskImageInspectionStatus.UNSUPPORTED,
                message="Source is not a valid file"
            )

        suffix = self.source_path.suffix.lower()

        # Read-only verification variables
        stat_before = self.source_path.stat()

        try:
            with open(self.source_path, "rb") as f:
                header = f.read(512)
        except Exception as e:
            return DiskImageInspectionResult(
                status=DiskImageInspectionStatus.INVALID_OR_UNREADABLE,
                message=f"Failed to read image header: {e}"
            )

        is_e01 = header.startswith(b"EVF") or suffix == ".e01"

        if is_e01:
            if not header.startswith(b"EVF"):
                return DiskImageInspectionResult(
                    status=DiskImageInspectionStatus.INVALID_OR_UNREADABLE,
                    message="E01 extension detected but missing EVF signature"
                )

            try:
                import pyewf
                handle = pyewf.handle()
                handle.open([str(self.source_path)])

                info = DiskImageInfo(
                    image_format="E01 (Expert Witness Format)",
                    size_bytes=handle.get_media_size(),
                    sector_size=handle.get_bytes_per_sector(),
                    is_supported=True,
                    details="E01 metadata successfully inspected via pyewf"
                )
                handle.close()

                # Verify read-only safety
                stat_after = self.source_path.stat()
                if stat_before.st_size != stat_after.st_size or stat_before.st_mtime != stat_after.st_mtime:
                    return DiskImageInspectionResult(
                        status=DiskImageInspectionStatus.INVALID_OR_UNREADABLE,
                        message="Safety violation: E01 inspection altered source file size or timestamp"
                    )

                return DiskImageInspectionResult(
                    status=DiskImageInspectionStatus.SUPPORTED,
                    info=info,
                    message="E01 metadata successfully inspected."
                )
            except ImportError:
                info = DiskImageInfo(
                    image_format="E01 (Expert Witness Format)",
                    size_bytes=stat_before.st_size,
                    sector_size=None,
                    is_supported=True,
                    details="E01 detected; detailed EWF metadata inspection unavailable because libewf support is not installed."
                )
                return DiskImageInspectionResult(
                    status=DiskImageInspectionStatus.DETECTED_BUT_UNAVAILABLE,
                    info=info,
                    message="E01 detected; detailed EWF metadata inspection unavailable because libewf support is not installed."
                )
            except Exception as e:
                return DiskImageInspectionResult(
                    status=DiskImageInspectionStatus.INVALID_OR_UNREADABLE,
                    message=f"Failed to parse E01 with pyewf: {e}"
                )

        if suffix in (".raw", ".dd", ".img", ".bin"):
            info = DiskImageInfo(
                image_format="Raw / DD Bitstream Image",
                size_bytes=stat_before.st_size,
                sector_size=None,
                is_supported=True,
                details="Raw uncompressed block device bitstream image"
            )
            return DiskImageInspectionResult(
                status=DiskImageInspectionStatus.SUPPORTED,
                info=info,
                message="Raw image detected."
            )

        return DiskImageInspectionResult(
            status=DiskImageInspectionStatus.UNSUPPORTED,
            message="Input is neither a supported disk image nor an E01 candidate."
        )

    def acquire(
        self,
        destination_dir: Path,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> AcquisitionResult:
        result = super().acquire(destination_dir, progress_callback)
        inspection = self.inspect_image()
        
        is_e01 = self.source_path.suffix.lower() == ".e01"
        result.method = "E01_IMAGE" if is_e01 else "RAW_IMAGE"
        result.source_type = "IMAGE"
        
        if inspection.info:
            result.sector_size = inspection.info.sector_size
            
        if inspection.status == DiskImageInspectionStatus.DETECTED_BUT_UNAVAILABLE:
            result.error_message = inspection.message
            
        return result
