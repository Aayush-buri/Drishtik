# Hyperledger Fabric Anchoring Integration

Drishtik utilizes Hyperledger Fabric as an enterprise permissioned ledger for **cryptographic integrity anchoring** and **chain-of-custody verification**.

## Current Architecture (Sprint 7B)

```text
FastAPI Python backend
        |
        | subprocess + JSON-RPC over stdin/stdout
        v
Node.js Fabric Gateway Worker
        |
        | @hyperledger/fabric-gateway
        v
submitAsync(...)
        |
        v
Fabric endorsement/orderer/commit
        |
        v
real transaction ID
        |
        v
commit confirmation
        |
        v
ledger verification
```

### Verified through live local Fabric

* real transaction submission
* real transaction ID
* real commit confirmation
* real block number
* ledger retrieval
* SHA-256 verification

### Still future work

* multi-organization Fabric governance
* production CA/identity management
* production deployment
* direct arbitrary transaction lookup via `get_transaction()`

## Reproducible local validation procedure

1. Start the local Fabric network using Docker Compose in the `blockchain` directory.
2. Deploy the `evidence_anchor` chaincode to the local channel.
3. Generate or export local client certificates and private keys.
4. Set the necessary environment variables (`FABRIC_PEER_ENDPOINT`, `FABRIC_CLIENT_CERT_PATH`, etc.) pointing to the local network.
5. Run the live integration test:
   ```bash
   $env:FABRIC_LIVE_TEST="1"
   pytest backend/tests/test_fabric_gateway.py -q
   ```

## Identity and Security Handling

* certificates and private keys are supplied through configuration paths (e.g. FABRIC_CLIENT_CERT_PATH, FABRIC_CLIENT_KEY_PATH)
* private keys must not be committed
* real credentials must not be stored in Git
* example configuration must contain only placeholders
* production secrets belong outside the repository

## Offline / Fail-Safe Behavior

If the Hyperledger Fabric runtime is stopped, unconfigured, or unreachable:
1. **Zero Operational Blockage**: Evidence import, video analysis, frame export, and recovery carving proceed without failure.
2. **Explicit Transparency**: The system falls back to DISABLED, NOT_CONFIGURED, or UNAVAILABLE gracefully. Local SHA-256 integrity and audit logging remain active.
3. **No Fabricated Data**: Drishtik **never fabricates fake transactions or fake transaction IDs**. Missing ledger transactions are never synthesized.
