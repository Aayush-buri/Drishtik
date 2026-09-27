import pytest
import os
import json
from unittest.mock import patch, MagicMock
from app.forensics.blockchain.fabric_provider import HyperledgerFabricProvider, FabricGatewayClient
from app.core.config import settings

@pytest.fixture
def clean_gateway():
    client = FabricGatewayClient.get_instance()
    with client.lock:
        if client.process:
            client.process.kill()
            client.process = None
    yield
    with client.lock:
        if client.process:
            client.process.kill()
            client.process = None

def test_1_missing_configuration_not_configured(clean_gateway):
    with patch.dict(os.environ, {"FABRIC_CLIENT_CERT_PATH": "", "FABRIC_CLIENT_KEY_PATH": ""}):
        settings.FABRIC_ENABLED = True
        settings.FABRIC_CLIENT_CERT_PATH = ""
        settings.FABRIC_CLIENT_KEY_PATH = ""
        provider = HyperledgerFabricProvider()
        health = provider.health_check()
        assert health["status"] == "NOT_CONFIGURED"

def test_2_fabric_disabled_offline_fallback(clean_gateway):
    settings.FABRIC_ENABLED = False
    provider = HyperledgerFabricProvider()
    health = provider.health_check()
    assert health["status"] == "DISABLED"
    assert health["available"] is False

def test_3_invalid_endpoint_unavailable_error(clean_gateway):
    with patch.dict(os.environ, {"FABRIC_PEER_ENDPOINT": "invalid:7051"}):
        settings.FABRIC_ENABLED = True
        settings.FABRIC_CLIENT_CERT_PATH = "dummy.pem"
        settings.FABRIC_CLIENT_KEY_PATH = "dummy.key"
        provider = HyperledgerFabricProvider(peer_endpoint="invalid:7051")
        # Wait, if dummy.pem doesn't exist, newIdentity will throw in node
        health = provider.health_check()
        assert health["status"] == "ERROR" or health["status"] == "UNAVAILABLE"

def test_4_no_cert_deterministic_failure(clean_gateway):
    with patch.dict(os.environ, {"FABRIC_CLIENT_CERT_PATH": "", "FABRIC_CLIENT_KEY_PATH": ""}):
        settings.FABRIC_ENABLED = True
        settings.FABRIC_CLIENT_CERT_PATH = ""
        settings.FABRIC_CLIENT_KEY_PATH = ""
        provider = HyperledgerFabricProvider()
        health = provider.health_check()
        assert health["status"] == "NOT_CONFIGURED"

def test_5_evaluate_evidence_no_config(clean_gateway):
    settings.FABRIC_ENABLED = True
    settings.FABRIC_CLIENT_CERT_PATH = ""
    settings.FABRIC_CLIENT_KEY_PATH = ""
    provider = HyperledgerFabricProvider()
    resp = provider.evaluate_evidence_anchor("case_1", "ev_1")
    assert resp["status"] in ("NOT_CONFIGURED", "ERROR")

def test_6_no_fake_transactions(clean_gateway):
    provider = HyperledgerFabricProvider()
    res = provider.anchor_evidence("c1", "e1", "hash", "type", "actor", None, "src", {})
    assert res.transaction_id is None
    assert res.block_number is None

@pytest.mark.skipif(not os.environ.get("FABRIC_LIVE_TEST"), reason="Live Fabric network required for integration test")
def test_7_integration_real_evaluate():
    settings.FABRIC_ENABLED = True
    provider = HyperledgerFabricProvider()
    health = provider.health_check()
    assert health["status"] == "CONNECTED"
    resp = provider.evaluate_evidence_anchor("TEST_CASE", "TEST_EVIDENCE")
    # if it doesn't exist, it should return NOT_FOUND instead of crashing
    assert resp["status"] in ("SUCCESS", "NOT_FOUND")

