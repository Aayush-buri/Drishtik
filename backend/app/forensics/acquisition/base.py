from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

@dataclass
class AcquisitionResult:
    source_sha256: str
    destination_sha256: str
    source_md5: str
    destination_md5: str
    size_bytes: int
    destination_path: Path
    verified: bool
    error_message: Optional[str] = None
    item_count: int = 1

class AcquisitionAdapter(ABC):
    """Abstract base class for all forensic acquisition adapters."""

    def __init__(self, source_path: Path | str):
        self.source_path = Path(source_path)

    @abstractmethod
    def validate_source(self) -> bool:
        """Validates that the source exists, is accessible, and meets adapter constraints."""
        pass

    @abstractmethod
    def estimate_size(self) -> int:
        """Estimates total size of source in bytes."""
        pass

    @abstractmethod
    def acquire(
        self,
        destination_dir: Path,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> AcquisitionResult:
        """
        Executes read-only forensic acquisition into destination_dir.
        Must preserve the source without any modification, calculate hashes,
        and verify cryptographic integrity.
        """
        pass

    def verify(self, result: AcquisitionResult) -> bool:
        """Verifies source and destination SHA-256 match."""
        return bool(
            result.source_sha256
            and result.destination_sha256
            and (result.source_sha256.lower() == result.destination_sha256.lower())
        )

    def cleanup(self) -> None:
        """Optional post-acquisition cleanup."""
        pass
