import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

class SourceDeviceProvider(ABC):
    """
    Abstract Base Class for hardware source device discovery and access control.
    Prepares Drishtik for native Electron/desktop privileged device access while
    providing controlled workstation boundary validation in browser/development environments.
    """

    @abstractmethod
    def list_devices(self) -> List[Dict[str, Any]]:
        """Enumerates available physical or mounted source devices."""
        pass

    @abstractmethod
    def get_device(self, device_identifier: str) -> Optional[Dict[str, Any]]:
        """Retrieves details for a specific device."""
        pass

    @abstractmethod
    def is_connected(self, source_root: Optional[str]) -> bool:
        """Determines if the physical source device root is currently connected and accessible."""
        pass

    @abstractmethod
    def get_source_root(self, source_root: Optional[str]) -> Optional[Path]:
        """Resolves the canonical root path for the device."""
        pass

    @abstractmethod
    def validate_access(self, source_root: Optional[str], target_path: str) -> Path:
        """
        Resolves canonical path and validates that target_path belongs strictly to source_root.
        Rejects directory traversal, symlink escapes, UNC escapes, and arbitrary paths outside root.
        """
        pass

    @abstractmethod
    def list_source_contents(self, source_root: Optional[str], subpath: str = "") -> List[Dict[str, Any]]:
        """Returns constrained file/folder listing inside the verified source root."""
        pass


class LocalWorkstationSourceProvider(SourceDeviceProvider):
    """
    Workstation implementation of SourceDeviceProvider.
    Enforces strict forensic source-boundary containment on the local workstation/server,
    allowing controlled pen drive testing (e.g. E:\\ or designated test mount)
    while rejecting arbitrary access to unauthorized system paths.
    """

    def list_devices(self) -> List[Dict[str, Any]]:
        # In browser/web server mode, we report available drive roots if on Windows
        devices = []
        if os.name == "nt":
            import string
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    devices.append({
                        "device_id": f"DRIVE_{letter}",
                        "name": f"Local Drive ({drive})",
                        "source_root": drive,
                        "is_connected": True
                    })
        return devices

    def get_device(self, device_identifier: str) -> Optional[Dict[str, Any]]:
        for dev in self.list_devices():
            if dev.get("device_id") == device_identifier:
                return dev
        return None

    def is_connected(self, source_root: Optional[str]) -> bool:
        if not source_root or not source_root.strip():
            return False
        
        try:
            p = Path(os.path.realpath(source_root.strip()))
            if not p.exists():
                return False
            # Ensure it is accessible for reading
            if p.is_dir():
                os.listdir(str(p))
                return True
            elif p.is_file():
                with open(p, "rb") as f:
                    f.read(1)
                return True
            return False
        except (OSError, PermissionError, FileNotFoundError):
            return False

    def get_source_root(self, source_root: Optional[str]) -> Optional[Path]:
        if not source_root or not source_root.strip():
            return None
        return Path(os.path.realpath(source_root.strip()))

    def validate_access(self, source_root: Optional[str], target_path: str) -> Path:
        if not source_root or not source_root.strip():
            raise ValueError("Device has no registered source root.")

        canonical_root = Path(os.path.realpath(source_root.strip()))
        if not canonical_root.exists():
            raise ValueError("Source device is not connected or accessible.")

        if not target_path or not target_path.strip():
            # If target_path is empty, return canonical_root itself
            return canonical_root

        raw_p = Path(target_path.strip())

        # Disallow explicit traversal sequences in string representation
        normalized_str = target_path.replace("\\", "/")
        parts = [p for p in normalized_str.split("/") if p]
        if any(part == ".." for part in parts):
            raise ValueError("Selected source is outside the registered device.")

        if raw_p.is_absolute():
            resolved_target = Path(os.path.realpath(str(raw_p)))
        else:
            resolved_target = Path(os.path.realpath(str(canonical_root / raw_p)))

        # Boundary containment check
        try:
            if not resolved_target.is_relative_to(canonical_root):
                raise ValueError("Selected source is outside the registered device.")
        except (ValueError, AttributeError):
            try:
                common = os.path.commonpath([str(canonical_root), str(resolved_target)])
                if os.path.realpath(common) != str(canonical_root):
                    raise ValueError("Selected source is outside the registered device.")
            except Exception:
                raise ValueError("Selected source is outside the registered device.")

        if not resolved_target.exists():
            raise FileNotFoundError(f"Target path does not exist inside source device: {target_path}")

        return resolved_target

    def list_source_contents(self, source_root: Optional[str], subpath: str = "") -> List[Dict[str, Any]]:
        if not source_root or not source_root.strip():
            return []

        target_dir = self.validate_access(source_root, subpath)
        canonical_root = Path(os.path.realpath(source_root.strip()))

        if target_dir.is_file():
            stat = target_dir.stat()
            rel_path = str(target_dir.relative_to(canonical_root)).replace("\\", "/")
            return [{
                "name": target_dir.name,
                "path": rel_path,
                "is_dir": False,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            }]

        items = []
        try:
            with os.scandir(str(target_dir)) as entries:
                for entry in entries:
                    try:
                        stat = entry.stat()
                        entry_path = Path(entry.path)
                        rel_path = str(entry_path.relative_to(canonical_root)).replace("\\", "/")
                        items.append({
                            "name": entry.name,
                            "path": rel_path,
                            "is_dir": entry.is_dir(),
                            "size_bytes": stat.st_size if not entry.is_dir() else None,
                            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                        })
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            return []

        # Sort: directories first, then alphabetical
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return items


_default_provider = LocalWorkstationSourceProvider()

def get_device_provider() -> SourceDeviceProvider:
    """Factory to retrieve the active SourceDeviceProvider."""
    return _default_provider
