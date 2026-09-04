from pathlib import Path
from app.forensics.acquisition.base import AcquisitionAdapter, AcquisitionResult
from app.forensics.acquisition.file_copy import FileCopyAdapter
from app.forensics.acquisition.directory_copy import DirectoryCopyAdapter
from app.forensics.acquisition.disk_image import DiskImageAdapter
from app.models.acquisition import AcquisitionMethod

def get_acquisition_adapter(method: AcquisitionMethod | str, source_path: Path | str) -> AcquisitionAdapter:
    """
    Factory to retrieve appropriate vendor-agnostic forensic acquisition adapter.
    """
    method_str = str(method)
    if method_str in (AcquisitionMethod.FILE_COPY, AcquisitionMethod.EXPORTED_VIDEO, AcquisitionMethod.LOGICAL_ACQUISITION, AcquisitionMethod.OTHER, "FILE_COPY", "EXPORTED_VIDEO", "LOGICAL_ACQUISITION", "OTHER"):
        # Check if source is a directory or file
        p = Path(source_path)
        if p.exists() and p.is_dir():
            return DirectoryCopyAdapter(source_path)
        return FileCopyAdapter(source_path)
    elif method_str in (AcquisitionMethod.DIRECTORY_COPY, "DIRECTORY_COPY"):
        return DirectoryCopyAdapter(source_path)
    elif method_str in (AcquisitionMethod.DISK_IMAGE, "DISK_IMAGE"):
        return DiskImageAdapter(source_path)
    else:
        return FileCopyAdapter(source_path)
