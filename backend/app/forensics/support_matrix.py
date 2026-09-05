"""Internal forensic vendor capabilities and support matrix."""
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class VendorCapability:
    vendor_name: str
    detection: str     # SUPPORTED | PARTIAL | NONE
    parsing: str       # SUPPORTED | PARTIAL | NONE
    decoding: str      # SUPPORTED | PARTIAL | NONE
    proxy: str         # SUPPORTED | PARTIAL | NONE
    details: str
    supported_signatures: List[str]


SUPPORT_MATRIX: Dict[str, VendorCapability] = {
    "dahua": VendorCapability(
        vendor_name="Dahua",
        detection="SUPPORTED",
        parsing="SUPPORTED",
        decoding="SUPPORTED",
        proxy="SUPPORTED",
        details="DHAV container parsing, OSD timestamp extraction, Annex B stream demuxing, and MP4 proxy transmuxing.",
        supported_signatures=["DHAV", "WFS0", "WFS"],
    ),
    "hikvision": VendorCapability(
        vendor_name="Hikvision",
        detection="SUPPORTED",
        parsing="PARTIAL",
        decoding="PARTIAL",
        proxy="PARTIAL",
        details="HIKB/HIKV/HIKT signature detection, MPEG-PS PES demuxing and transmuxing. Encrypted HIKB variants unsupported.",
        supported_signatures=["HIKB", "HIKV", "HIKT", "Hikvision MPEG-PS"],
    ),
    "cpplus": VendorCapability(
        vendor_name="CP Plus",
        detection="SUPPORTED",
        parsing="PARTIAL",
        decoding="PARTIAL",
        proxy="PARTIAL",
        details="CP Plus detection with Dahua OEM DHAV compatibility pipeline reuse.",
        supported_signatures=["CPPLUS", "DHAV", "WFS"],
    ),
    "generic": VendorCapability(
        vendor_name="Generic",
        detection="SUPPORTED",
        parsing="SUPPORTED",
        decoding="SUPPORTED",
        proxy="SUPPORTED",
        details="Standard ISO/IEC MP4, MKV/WebM, AVI, and Annex B H.264/H.265 elementary streams.",
        supported_signatures=["MP4", "MKV", "AVI", "H264", "H265"],
    ),
}


def get_vendor_capabilities(vendor_name: str) -> VendorCapability:
    key = vendor_name.lower().replace(" ", "")
    return SUPPORT_MATRIX.get(
        key,
        VendorCapability(
            vendor_name=vendor_name,
            detection="NONE",
            parsing="NONE",
            decoding="NONE",
            proxy="NONE",
            details=f"No forensic adapter registered for {vendor_name}",
            supported_signatures=[],
        ),
    )
