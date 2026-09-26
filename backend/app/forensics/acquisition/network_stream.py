"""Network-based live acquisition adapter for IP-connected DVR/NVR devices.

TARGET FILE IN REPO: backend/app/forensics/acquisition/network_stream.py

Connects to IP-connected DVR/NVR devices over the network using:
  - ONVIF (standards-based device info, stream-URI resolution, and clock-offset
    detection) as the PRIMARY method.
  - RTSP (stream pull via FFmpeg stream-copy) as the data-pull mechanism,
    preserving the compressed media payload without re-encoding (-c copy).
  - A table of vendors' published default RTSP paths as a fallback ONLY when
    a device does not answer ONVIF and the vendor path is documented.

Forensic soundness principles:
  1. All ONVIF calls are strictly READ-ONLY: GetDeviceInformation, GetProfiles,
     GetStreamUri, GetSystemDateAndTime (ONVIF Core Specification v2.6, Sec. 8).
     No PTZ, recording-control, or configuration write operations.
  2. RTSP capture uses FFmpeg "-c copy" (stream copy), never re-encoding.
     The output container is remuxed (e.g. MPEG-TS), so output bytes are NOT
     byte-for-byte identical to internal DVR storage or raw RTSP packetization.
  3. Captured stream SHA-256 and MD5 are computed on the captured artifact file
     and verified post-write, labeled honestly as logical network stream capture.
  4. Logical acquisition (AcquisitionMethod.NETWORK_LIVE_PULL): captures current
     live streaming media, NOT historical recordings or deleted footage.
     Disk-image carving remains the physical acquisition method for recovery.
  5. Credential safety: Passwords are accepted only at runtime and are NEVER
     written to persistent storage, application logs, or audit details.
"""
import base64
import hashlib
import os
import re
import socket
import subprocess
import time
import urllib.parse
import xml.sax.saxutils as saxutils
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional
from xml.etree import ElementTree as ET

from app.forensics.acquisition.base import AcquisitionAdapter, AcquisitionResult
from app.forensics.vendor_adapter import get_ffmpeg_executable
from app.models.acquisition import AcquisitionMethod

CHUNK_SIZE = 65536  # 64 KB chunk size for streaming and verification
DEFAULT_ONVIF_PORT = 80
DEFAULT_RTSP_PORT = 554
DEFAULT_TIMEOUT_S = 8

ONVIF_NS = {
    "soap": "http://www.w3.org/2003/05/soap-envelope",
    "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
    "wsu": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
    "tds": "http://www.onvif.org/ver10/device/wsdl",
    "trt": "http://www.onvif.org/ver10/media/wsdl",
    "tt": "http://www.onvif.org/ver10/schema",
}

# Fallback RTSP path templates -- used ONLY when a device does not answer ONVIF
# and the path is backed by authoritative vendor documentation.
# Do NOT invent unverified fallback URLs for other vendors.
_DOCUMENTED_FALLBACK_RTSP_PATHS = {
    "dahua": "/cam/realmonitor?channel={channel}&subtype=0",
    "hikvision": "/Streaming/Channels/{channel}01",
    "uniview": "/media/video{channel}",
    "cpplus": "/cam/realmonitor?channel={channel}&subtype=0",
}


def sanitize_rtsp_uri(uri: str) -> str:
    """Masks credentials in RTSP URIs for safe logging and display."""
    if not uri:
        return ""
    return re.sub(r"://([^:@]+):([^@]+)@", r"://\1:***@", uri)


@dataclass
class NetworkDeviceTarget:
    """Connection parameters for one network-attached DVR/NVR."""
    device_label: str
    ip_address: str
    username: str
    password: str
    onvif_port: int = DEFAULT_ONVIF_PORT
    rtsp_port: int = DEFAULT_RTSP_PORT
    channel: int = 1
    vendor_hint: Optional[str] = None
    rtsp_path_override: Optional[str] = None
    onvif_profile_token: Optional[str] = None


@dataclass
class NetworkConnectionInfo:
    reachable: bool
    onvif_supported: bool
    rtsp_uri: Optional[str] = None
    device_manufacturer: Optional[str] = None
    device_model: Optional[str] = None
    device_clock_offset: Optional[timedelta] = None
    error_message: Optional[str] = None


def _xml_escape(text: str) -> str:
    """Safely escapes XML special characters (&, <, >, ", ')."""
    return saxutils.escape(text, entities={'"': "&quot;", "'": "&apos;"})


def _build_ws_security_header(username: str, password: str) -> str:
    """Builds a WS-Security UsernameToken (PasswordDigest) SOAP header with XML-escaping."""
    nonce_bytes = os.urandom(16)
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    digest = base64.b64encode(
        hashlib.sha1(nonce_bytes + created.encode("utf-8") + password.encode("utf-8")).digest()
    ).decode("utf-8")
    nonce_b64 = base64.b64encode(nonce_bytes).decode("utf-8")
    escaped_user = _xml_escape(username)

    return (
        "<soap:Header>"
        '<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" '
        'xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">'
        "<wsse:UsernameToken>"
        f"<wsse:Username>{escaped_user}</wsse:Username>"
        '<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">'
        f"{digest}</wsse:Password>"
        '<wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">'
        f"{nonce_b64}</wsse:Nonce>"
        f"<wsu:Created>{created}</wsu:Created>"
        "</wsse:UsernameToken>"
        "</wsse:Security>"
        "</soap:Header>"
    )


def _soap_request(url: str, username: str, password: str, body: str, timeout: int = DEFAULT_TIMEOUT_S) -> ET.Element:
    """Issues one ONVIF SOAP 1.2 request with WS-Security auth and returns the parsed XML root."""
    import urllib.request

    header = _build_ws_security_header(username, password)
    envelope = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">'
        f"{header}"
        f"<soap:Body>{body}</soap:Body></soap:Envelope>"
    )
    req = urllib.request.Request(
        url,
        data=envelope.encode("utf-8"),
        headers={"Content-Type": "application/soap+xml; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return ET.fromstring(resp.read())


def _onvif_get_device_info(target: NetworkDeviceTarget, timeout: int = DEFAULT_TIMEOUT_S) -> Dict[str, Optional[str]]:
    url = f"http://{target.ip_address}:{target.onvif_port}/onvif/device_service"
    body = '<tds:GetDeviceInformation xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>'
    root = _soap_request(url, target.username, target.password, body, timeout=timeout)

    def _text(tag: str) -> Optional[str]:
        el = root.find(f".//tds:{tag}", ONVIF_NS)
        return el.text if el is not None else None

    return {
        "manufacturer": _text("Manufacturer"),
        "model": _text("Model"),
        "firmware_version": _text("FirmwareVersion"),
        "serial_number": _text("SerialNumber"),
    }


def _onvif_get_stream_uri(target: NetworkDeviceTarget, timeout: int = DEFAULT_TIMEOUT_S) -> Optional[str]:
    """Resolves stream URI via ONVIF media service.

    Does not assume profile index equals channel number. If profile mapping is
    ambiguous, requires explicit profile token or falls back to documented vendor path.
    """
    media_url = f"http://{target.ip_address}:{target.onvif_port}/onvif/media_service"
    profiles_body = '<trt:GetProfiles xmlns:trt="http://www.onvif.org/ver10/media/wsdl"/>'
    root = _soap_request(media_url, target.username, target.password, profiles_body, timeout=timeout)

    profile_elements = root.findall(".//trt:Profiles", ONVIF_NS)
    if not profile_elements:
        return None

    chosen_token: Optional[str] = None

    if target.onvif_profile_token:
        chosen_token = target.onvif_profile_token
    elif len(profile_elements) == 1:
        # Single profile device (e.g. single-channel IP camera)
        chosen_token = profile_elements[0].attrib.get("token")
    else:
        # Check if profile tokens or names match requested channel explicitly
        ch_str = str(target.channel)
        for p in profile_elements:
            token = p.attrib.get("token", "")
            name_el = p.find("tt:Name", ONVIF_NS)
            name = name_el.text if name_el is not None else ""
            if (
                f"ch{ch_str}" in token.lower()
                or f"channel{ch_str}" in token.lower()
                or f"ch{ch_str}" in name.lower()
                or f"channel{ch_str}" in name.lower()
                or token == f"Profile_{ch_str}"
            ):
                chosen_token = token
                break

    if not chosen_token:
        # Channel to profile mapping is unresolved; do not silently guess
        return None

    stream_body = (
        '<trt:GetStreamUri xmlns:trt="http://www.onvif.org/ver10/media/wsdl">'
        "<trt:StreamSetup>"
        '<tt:Stream xmlns:tt="http://www.onvif.org/ver10/schema">RTP-Unicast</tt:Stream>'
        '<tt:Transport xmlns:tt="http://www.onvif.org/ver10/schema"><tt:Protocol>RTSP</tt:Protocol></tt:Transport>'
        "</trt:StreamSetup>"
        f"<trt:ProfileToken>{chosen_token}</trt:ProfileToken>"
        "</trt:GetStreamUri>"
    )
    root2 = _soap_request(media_url, target.username, target.password, stream_body, timeout=timeout)
    uri_el = root2.find(".//tt:Uri", ONVIF_NS)
    if uri_el is None or not uri_el.text:
        return None

    resolved_uri = uri_el.text.strip()
    # Ensure credentials are incorporated if the device returned an unauthenticated URI
    if "@" not in resolved_uri and target.username:
        safe_user = urllib.parse.quote(target.username, safe="")
        safe_pass = urllib.parse.quote(target.password, safe="")
        resolved_uri = re.sub(r"^rtsp://", f"rtsp://{safe_user}:{safe_pass}@", resolved_uri)

    return resolved_uri


def _onvif_get_clock_offset(target: NetworkDeviceTarget, timeout: int = DEFAULT_TIMEOUT_S) -> Optional[timedelta]:
    """Read-only device clock offset check: returns (device_time - our_utc_now)."""
    url = f"http://{target.ip_address}:{target.onvif_port}/onvif/device_service"
    body = '<tds:GetSystemDateAndTime xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>'
    try:
        root = _soap_request(url, target.username, target.password, body, timeout=timeout)
        utc = root.find(".//tt:UTCDateTime", ONVIF_NS)
        if utc is None:
            return None
        date_el = utc.find("tt:Date", ONVIF_NS)
        time_el = utc.find("tt:Time", ONVIF_NS)
        y = int(date_el.find("tt:Year", ONVIF_NS).text)
        mo = int(date_el.find("tt:Month", ONVIF_NS).text)
        d = int(date_el.find("tt:Day", ONVIF_NS).text)
        h = int(time_el.find("tt:Hour", ONVIF_NS).text)
        mi = int(time_el.find("tt:Minute", ONVIF_NS).text)
        s = int(time_el.find("tt:Second", ONVIF_NS).text)
        device_time = datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)
        return device_time - datetime.now(timezone.utc)
    except Exception:
        return None


def _build_rtsp_uri(host: str, port: int, path: str, username: str = "", password: str = "") -> str:
    """Constructs an RTSP URI with safely URL-encoded credentials."""
    if not path.startswith("/"):
        path = "/" + path
    if username:
        safe_user = urllib.parse.quote(username, safe="")
        safe_pass = urllib.parse.quote(password, safe="")
        return f"rtsp://{safe_user}:{safe_pass}@{host}:{port}{path}"
    return f"rtsp://{host}:{port}{path}"


def probe_network_device(target: NetworkDeviceTarget, timeout: int = DEFAULT_TIMEOUT_S) -> NetworkConnectionInfo:
    """Read-only reachability and capability probe.

    Does not abort immediately if ONVIF port is unreachable; proceeds to check
    RTSP reachability for documented fallback paths.
    """
    onvif_reachable = False
    try:
        with socket.create_connection((target.ip_address, target.onvif_port), timeout=min(timeout, 3)):
            onvif_reachable = True
    except (OSError, socket.timeout):
        onvif_reachable = False

    device_info: Dict[str, Optional[str]] = {}
    clock_offset: Optional[timedelta] = None

    if onvif_reachable:
        try:
            device_info = _onvif_get_device_info(target, timeout=timeout)
            clock_offset = _onvif_get_clock_offset(target, timeout=timeout)
            uri = _onvif_get_stream_uri(target, timeout=timeout)
            if uri:
                return NetworkConnectionInfo(
                    reachable=True,
                    onvif_supported=True,
                    rtsp_uri=uri,
                    device_manufacturer=device_info.get("manufacturer"),
                    device_model=device_info.get("model"),
                    device_clock_offset=clock_offset,
                )
        except Exception:
            # Fall through to documented fallback
            pass

    # Check RTSP port reachability
    rtsp_reachable = False
    try:
        with socket.create_connection((target.ip_address, target.rtsp_port), timeout=min(timeout, 3)):
            rtsp_reachable = True
    except (OSError, socket.timeout):
        rtsp_reachable = False

    if not onvif_reachable and not rtsp_reachable:
        return NetworkConnectionInfo(
            reachable=False,
            onvif_supported=False,
            error_message=f"Network target {target.ip_address} unreachable on ONVIF port {target.onvif_port} and RTSP port {target.rtsp_port}."
        )

    # Resolve documented fallback RTSP path
    path: Optional[str] = None
    if target.rtsp_path_override:
        path = target.rtsp_path_override
    elif target.vendor_hint and target.vendor_hint.lower() in _DOCUMENTED_FALLBACK_RTSP_PATHS:
        path = _DOCUMENTED_FALLBACK_RTSP_PATHS[target.vendor_hint.lower()].format(channel=target.channel)
    else:
        hint_str = target.vendor_hint or "unspecified"
        return NetworkConnectionInfo(
            reachable=True,
            onvif_supported=False,
            error_message=(
                f"ONVIF service unavailable and vendor hint '{hint_str}' has no documented fallback RTSP path. "
                "Explicit rtsp_path_override required."
            )
        )

    rtsp_uri = _build_rtsp_uri(target.ip_address, target.rtsp_port, path, target.username, target.password)

    return NetworkConnectionInfo(
        reachable=True,
        onvif_supported=False,
        rtsp_uri=rtsp_uri,
        device_manufacturer=device_info.get("manufacturer") or target.vendor_hint,
        device_model=device_info.get("model"),
        device_clock_offset=clock_offset,
    )


class NetworkStreamAdapter(AcquisitionAdapter):
    """Forensic acquisition adapter for live network-connected DVR/NVR streams."""

    def __init__(self, target: NetworkDeviceTarget, duration_seconds: int = 300):
        self.target = target
        self.duration_seconds = duration_seconds
        self.method = AcquisitionMethod.NETWORK_LIVE_PULL
        self._connection_info: Optional[NetworkConnectionInfo] = None
        super().__init__(source_path=f"network://{target.ip_address}:{target.rtsp_port}/ch{target.channel}")

    def validate_source(self) -> bool:
        self._connection_info = probe_network_device(self.target)
        return bool(self._connection_info.reachable and self._connection_info.rtsp_uri)

    def estimate_size(self) -> int:
        return 0

    def acquire(
        self,
        destination_dir: Path,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> AcquisitionResult:
        if self._connection_info is None and not self.validate_source():
            pass

        if not self._connection_info or not self._connection_info.rtsp_uri:
            err = self._connection_info.error_message if self._connection_info else "stream URI could not be resolved"
            raise ConnectionError(
                f"Cannot acquire stream for device '{self.target.device_label}' at {self.target.ip_address}: {err}"
            )

        ffmpeg_bin = get_ffmpeg_executable()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg executable not found.")

        destination_dir = Path(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.target.device_label)
        destination_path = destination_dir / f"{safe_label}_live_capture.ts"

        cmd = [
            ffmpeg_bin,
            "-y",
            "-rtsp_transport", "tcp",
            "-timeout", str(DEFAULT_TIMEOUT_S * 1_000_000),
            "-i", self._connection_info.rtsp_uri,
            "-t", str(self.duration_seconds),
            "-c", "copy",
            "-f", "mpegts",
            "pipe:1",
        ]

        sha256 = hashlib.sha256()
        md5 = hashlib.md5()
        bytes_written = 0
        start_time = time.monotonic()

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            with open(destination_path, "wb") as out_f:
                while True:
                    chunk = proc.stdout.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    sha256.update(chunk)
                    md5.update(chunk)
                    out_f.write(chunk)
                    bytes_written += len(chunk)
                    if progress_callback and self.duration_seconds > 0:
                        elapsed = time.monotonic() - start_time
                        pct = int(min(99, (elapsed / self.duration_seconds) * 100))
                        progress_callback(pct)
            proc.wait(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()

        stderr_tail = proc.stderr.read().decode(errors="ignore")[-500:] if proc.stderr else ""
        if bytes_written == 0:
            sanitized_tail = re.sub(r"://([^:@]+):([^@]+)@", r"://\1:***@", stderr_tail)
            raise RuntimeError(
                f"No data received from device '{self.target.device_label}'. FFmpeg output: {sanitized_tail}"
            )

        verify_sha256 = hashlib.sha256()
        verify_md5 = hashlib.md5()
        with open(destination_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                verify_sha256.update(chunk)
                verify_md5.update(chunk)

        source_sha256_hex = sha256.hexdigest()
        source_md5_hex = md5.hexdigest()
        dest_sha256_hex = verify_sha256.hexdigest()
        dest_md5_hex = verify_md5.hexdigest()
        verified = (source_sha256_hex == dest_sha256_hex) and (source_md5_hex == dest_md5_hex)

        if progress_callback:
            progress_callback(100)

        return AcquisitionResult(
            source_sha256=source_sha256_hex,
            destination_sha256=dest_sha256_hex,
            source_md5=source_md5_hex,
            destination_md5=dest_md5_hex,
            size_bytes=bytes_written,
            destination_path=destination_path,
            verified=verified,
            error_message=None if verified else "Hash mismatch between received stream and written file.",
            item_count=1,
        )

    def get_device_clock_offset(self) -> Optional[timedelta]:
        if self._connection_info is None:
            self.validate_source()
        return self._connection_info.device_clock_offset if self._connection_info else None


def connect_multiple(
    targets: List[NetworkDeviceTarget],
    destination_root: Path,
    duration_seconds: int = 300,
    max_workers: int = 4,
) -> Dict[str, AcquisitionResult]:
    """Acquires live streams from several DVR/NVR devices concurrently with bounded concurrency."""
    destination_root = Path(destination_root)
    results: Dict[str, AcquisitionResult] = {}

    def _run_one(t: NetworkDeviceTarget) -> AcquisitionResult:
        adapter = NetworkStreamAdapter(t, duration_seconds=duration_seconds)
        return adapter.acquire(destination_root / t.device_label)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_label = {pool.submit(_run_one, t): t.device_label for t in targets}
        for future in as_completed(future_to_label):
            label = future_to_label[future]
            try:
                results[label] = future.result()
            except Exception as exc:
                results[label] = AcquisitionResult(
                    source_sha256="",
                    destination_sha256="",
                    source_md5="",
                    destination_md5="",
                    size_bytes=0,
                    destination_path=destination_root / label,
                    verified=False,
                    error_message=str(exc),
                    item_count=0,
                )
    return results
