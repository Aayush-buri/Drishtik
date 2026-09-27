# Hyperledger Fabric Anchoring Integration

Drishtik utilizes Hyperledger Fabric as an enterprise permissioned ledger for **cryptographic integrity anchoring** and **chain-of-custody verification**.

## Current verified capability after Sprint 7B

The system implements a true Node.js-based Fabric Gateway architecture:

* real Fabric Gateway connection
* real `submitAsync()` transaction submission
* real transaction ID
* real commit-status confirmation
* real block number when supplied by commit status
* real ledger verification through `GetEvidenceAnchor`
* no fabricated transaction/block metadata
* offline fallback
* `get_transaction()` remains unsupported unless a genuine ledger transaction query mechanism is added
* multi-organization Fabric governance remains future work

### Architecture

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
