"""Tests for Network Stream Acquisition & Fabric Provider Safety.

Verifies:
1. Network live pull adapter resolution and method support
2. ONVIF port closed -> fallback to RTSP probe without aborting
3. Unsupported vendor fallback returns explicit unsupported error
4. Credential safety: passwords masked in URIs, URL-encoded, XML-escaped
5. Fabric provider safety: real provider never fabricates Tx IDs or block numbers
"""
import pytest
from unittest.mock import patch, MagicMock
from app.forensics.acquisition import (
    get_network_acquisition_adapter,
    NetworkStreamAdapter,
    NetworkDeviceTarget,
    probe_network_device,
)
from app.forensics.acquisition.network_stream import (
    sanitize_rtsp_uri,
    _xml_escape,
    _build_rtsp_uri,
)
from datetime import datetime, timezone
from app.forensics.blockchain.fabric_provider import HyperledgerFabricProvider
from app.models.acquisition import AcquisitionMethod


def test_network_acquisition_adapter_resolution():
    """Verify that NETWORK_LIVE_PULL resolves to NetworkStreamAdapter."""
    target = NetworkDeviceTarget(
        device_label="IP-CAM-01",
        ip_address="192.168.1.100",
        username="admin",
        password="secretpassword",
        vendor_hint="Dahua",
        channel=1,
    )
    adapter = get_network_acquisition_adapter(target, duration_seconds=60)
    assert isinstance(adapter, NetworkStreamAdapter)
    assert adapter.method == AcquisitionMethod.NETWORK_LIVE_PULL
    assert adapter.duration_seconds == 60


def test_sanitize_rtsp_uri():
    """Verify that credentials in RTSP URIs are securely masked."""
    uri = "rtsp://admin:SecretPassword123!@192.168.1.100:554/cam/realmonitor?channel=1"
    sanitized = sanitize_rtsp_uri(uri)
    assert "SecretPassword123!" not in sanitized
    assert "rtsp://admin:***@192.168.1.100:554/cam/realmonitor?channel=1" == sanitized


def test_sanitize_rtsp_uri_no_credentials():
    """Verify that URIs without credentials remain unchanged."""
    uri = "rtsp://192.168.1.100:554/live/ch1"
    assert sanitize_rtsp_uri(uri) == uri


def test_xml_escape_credentials():
    """Verify XML special characters in SOAP credentials are properly escaped."""
    assert _xml_escape("admin<>&\"'") == "admin&lt;&gt;&amp;&quot;&apos;"
    assert _xml_escape("regular_user") == "regular_user"


def test_build_rtsp_uri_url_encodes_credentials():
    """Verify special characters in passwords and usernames are URL-encoded in RTSP URI."""
    uri = _build_rtsp_uri(
        host="192.168.1.50",
        port=554,
        path="/cam/realmonitor?channel=1",
        username="admin user",
        password="p@ss/word#123",
    )
    assert "admin%20user" in uri
    assert "p%40ss%2Fword%23123" in uri
    assert uri.startswith("rtsp://")


def test_documented_fallback_rtsp_paths():
    """Verify Dahua and Hikvision fallback path templates."""
    from app.forensics.acquisition.network_stream import _DOCUMENTED_FALLBACK_RTSP_PATHS
    assert "dahua" in _DOCUMENTED_FALLBACK_RTSP_PATHS
    assert "hikvision" in _DOCUMENTED_FALLBACK_RTSP_PATHS
    assert _DOCUMENTED_FALLBACK_RTSP_PATHS["dahua"].format(channel=2) == "/cam/realmonitor?channel=2&subtype=0"
    assert _DOCUMENTED_FALLBACK_RTSP_PATHS["hikvision"].format(channel=1) == "/Streaming/Channels/101"
    assert _DOCUMENTED_FALLBACK_RTSP_PATHS["hikvision"].format(channel=3) == "/Streaming/Channels/301"


def test_unsupported_vendor_fallback_honest_refusal():
    """Verify that unsupported vendors without known templates honestly refuse to invent paths."""
    target = NetworkDeviceTarget(
        device_label="Test Device",
        ip_address="192.168.1.50",
        username="admin",
        password="password",
        onvif_port=80,
        rtsp_port=554,
        vendor_hint="Honeywell",
        channel=1,
    )

    with patch("app.forensics.acquisition.network_stream.socket.create_connection") as mock_conn:
        # Mock port 80 closed, port 554 open
        def mock_connect(addr, timeout=None):
            ip, port = addr
            if port == 80:
                raise OSError("Connection refused")
            return MagicMock()
        mock_conn.side_effect = mock_connect

        info = probe_network_device(target)
        assert info.reachable is True
        assert info.onvif_supported is False
        assert info.rtsp_uri is None
        assert "no documented fallback RTSP path" in info.error_message
        assert "Explicit rtsp_path_override required" in info.error_message


def test_onvif_closed_falls_back_to_rtsp_probe():
    """Verify that when ONVIF port 80 is closed, probe_network_device does not abort

    but tests RTSP port 554 and tests known vendor fallback.
    """
    target = NetworkDeviceTarget(
        device_label="IP-CAM-02",
        ip_address="192.168.1.200",
        username="admin",
        password="secretpassword",
        onvif_port=80,
        rtsp_port=554,
        vendor_hint="Dahua",
        channel=1,
    )

    # Mock socket.create_connection so port 80 fails (closed) and port 554 succeeds (open)
    def mock_socket_conn(addr, timeout=None):
        host, port = addr
        if port == 80:
            raise OSError("Connection refused")
        return MagicMock()

    with patch("app.forensics.acquisition.network_stream.socket.create_connection", side_effect=mock_socket_conn):
        info = probe_network_device(target)
        assert info.reachable is True
        assert info.onvif_supported is False
        assert info.rtsp_uri is not None
        assert "192.168.1.200:554" in info.rtsp_uri
        assert "/cam/realmonitor" in info.rtsp_uri


def test_fabric_provider_safety_no_fake_transactions():
    """Verify that real Fabric provider NEVER generates fake transaction IDs or blocks."""
    # When peer socket is unavailable or unconfigured, provider MUST report UNAVAILABLE / NOT_CONFIGURED
    # and MUST NOT invent local synthetic hashes, UUIDs, or fake block numbers.
    provider = HyperledgerFabricProvider()
    
    health = provider.health_check()
    assert health["available"] is False
    assert health["status"] in ("UNAVAILABLE", "NOT_CONFIGURED")

    result = provider.anchor_evidence(
        case_identifier="CASE-2026-TEST",
        evidence_identifier="EV-TEST-001",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        event_type="EVIDENCE_ACQUIRED",
        actor="Investigator",
        timestamp=datetime.now(timezone.utc),
        source="LOCAL_TEST",
        metadata={"case_id": 1}
    )
    
    assert result.success is False
    assert result.transaction_id is None
    assert result.block_number is None
    assert result.status in ("UNAVAILABLE", "NOT_CONFIGURED")

    # Verification must report verified=False, not hallucinate a verification
    v_res = provider.verify_anchor(
        case_identifier="CASE-2026-TEST",
        evidence_identifier="EV-TEST-001",
        expected_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert v_res.verified is False
    assert v_res.transaction_id is None
    assert v_res.block_number is None
    assert v_res.status in ("UNAVAILABLE", "NOT_CONFIGURED")
