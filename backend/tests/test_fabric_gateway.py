import pytest
import os
import json
from datetime import datetime, timezone
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

@patch('app.forensics.blockchain.fabric_provider.FabricGatewayClient.send_request')
def test_6_no_fake_transactions(mock_send_request, clean_gateway):
    # Setup mock to simulate connected but not actually anchoring
    mock_send_request.side_effect = lambda method, args: {"result": {"status": "NOT_CONFIGURED"}} if method == "health" else {}

    settings.FABRIC_ENABLED = True
    provider = HyperledgerFabricProvider()
    res = provider.anchor_evidence("c1", "e1", "hash", "type", "actor", datetime.now(timezone.utc), "src", {})
    assert res.transaction_id is None
    assert res.block_number is None
    assert res.status == "NOT_CONFIGURED"
    assert res.success is False

@patch('app.forensics.blockchain.fabric_provider.FabricGatewayClient.send_request')
def test_mocked_real_submission_success(mock_send_request, clean_gateway):
    def side_effect(method, args):
        if method == "health":
            return {"result": {"status": "CONNECTED"}}
        elif method == "submit":
            return {
                "result": {
                    "transaction_id": "REAL_TX_ID_123",
                    "block_number": "42",
                    "successful": True,
                    "payload": {}
                }
            }
        return {}
    mock_send_request.side_effect = side_effect

    settings.FABRIC_ENABLED = True
    provider = HyperledgerFabricProvider()
    res = provider.anchor_evidence("c1", "e1", "hash", "type", "actor", datetime.now(timezone.utc), "src", {})
    assert res.success is True
    assert res.status == "ANCHORED"
    assert res.transaction_id == "REAL_TX_ID_123"
    assert res.block_number == 42

@patch('app.forensics.blockchain.fabric_provider.FabricGatewayClient.send_request')
def test_mocked_submission_commit_timeout_or_fail(mock_send_request, clean_gateway):
    def side_effect(method, args):
        if method == "health":
            return {"result": {"status": "CONNECTED"}}
        elif method == "submit":
            return {
                "result": {
                    "transaction_id": "REAL_TX_ID_456",
                    "block_number": None,
                    "successful": False,
                    "payload": {}
                }
            }
        return {}
    mock_send_request.side_effect = side_effect

    settings.FABRIC_ENABLED = True
    provider = HyperledgerFabricProvider()
    res = provider.anchor_evidence("c1", "e1", "hash", "type", "actor", datetime.now(timezone.utc), "src", {})
    assert res.success is False
    assert res.status in ("FAILED", "TIMEOUT")
    assert res.transaction_id == "REAL_TX_ID_456"
    assert res.block_number is None

@patch('app.forensics.blockchain.fabric_provider.FabricGatewayClient.send_request')
def test_mocked_real_verification(mock_send_request, clean_gateway):
    def side_effect(method, args):
        if method == "health":
            return {"result": {"status": "CONNECTED"}}
        elif method == "evaluate":
            return {
                "result": {
                    "sha256": "EXPECTED_HASH",
                    "transaction_id": "TX999"
                }
            }
        return {}
    mock_send_request.side_effect = side_effect

    settings.FABRIC_ENABLED = True
    provider = HyperledgerFabricProvider()

    # Match
    res = provider.verify_anchor("c1", "e1", "EXPECTED_HASH")
    assert res.verified is True
    assert res.status == "VERIFIED"

    # Mismatch
    res2 = provider.verify_anchor("c1", "e1", "DIFFERENT_HASH")
    assert res2.verified is False
    assert res2.status == "MISMATCH"

@pytest.mark.skipif(not os.environ.get("FABRIC_LIVE_TEST"), reason="Live Fabric network required for integration test")
def test_live_integration_real_transaction(clean_gateway):
    settings.FABRIC_ENABLED = True
    provider = HyperledgerFabricProvider()

    # 1. health
    health = provider.health_check()
    assert health["status"] == "CONNECTED"

    # 2. anchor_evidence
    dt = datetime.now(timezone.utc)
    res = provider.anchor_evidence(
        "LIVE_TEST_CASE",
        "LIVE_TEST_EVIDENCE_001",
        "a_deterministic_test_SHA-256_value",
        "test_action",
        "test_actor",
        dt,
        "src",
        {"some": "data"}
    )

    assert res.success is True
    assert res.status == "ANCHORED"

    # 3. real transaction ID
    assert res.transaction_id is not None
    assert isinstance(res.transaction_id, str)
    assert len(res.transaction_id) > 0

    # 4. real block number
    assert res.block_number is not None
    assert isinstance(res.block_number, int)

    # 5. GetEvidenceAnchor
    raw_eval = provider.evaluate_evidence_anchor("LIVE_TEST_CASE", "LIVE_TEST_EVIDENCE_001")
    assert raw_eval["status"] == "SUCCESS"
    assert raw_eval.get("transaction_id") == res.transaction_id
    assert "block_number" not in raw_eval or raw_eval.get("block_number") is None

    # 6. verify_anchor
    verify_res = provider.verify_anchor("LIVE_TEST_CASE", "LIVE_TEST_EVIDENCE_001", "a_deterministic_test_SHA-256_value")
    assert verify_res.verified is True
    assert verify_res.status == "VERIFIED"
    assert verify_res.transaction_id == res.transaction_id

    # 7. mismatch verification
    mismatch_res = provider.verify_anchor("LIVE_TEST_CASE", "LIVE_TEST_EVIDENCE_001", "WRONG_SHA256")
    assert mismatch_res.verified is False
    assert mismatch_res.status == "MISMATCH"
    assert mismatch_res.transaction_id == res.transaction_id
