# Hyperledger Fabric Anchoring Integration

Drishtik utilizes Hyperledger Fabric as an enterprise permissioned ledger for **cryptographic integrity anchoring** and **chain-of-custody verification**.

## Current verified capability after Sprint 7A

The system implements a true Node.js-based Fabric Gateway architecture:

* real Node.js Fabric Gateway client foundation
* configurable Fabric identity
* configurable certificate/private-key paths
* configurable MSP/channel/chaincode/endpoint
* real Gateway connectivity/health when correctly configured
* real read-only GetEvidenceAnchor evaluation when configured
* deterministic NOT_CONFIGURED / UNAVAILABLE / ERROR behavior
* offline forensic operations continue
* no fabricated transaction IDs
* no fabricated block numbers
* no fabricated ANCHORED or VERIFIED ledger states

### Architecture

`	ext
FastAPI Python backend
        |
        | subprocess + JSON-RPC over stdin/stdout
        v
Node.js Fabric Gateway Worker
        |
        | @hyperledger/fabric-gateway
        v
Hyperledger Fabric peer/gateway
        |
        v
Fabric channel + chaincode
`

## What is NOT complete yet

Sprint 7A does **not** yet provide:

* end-to-end real transaction submission from the forensic custody workflow
* real commit-event confirmation integrated into custody processing
* application-level block-number confirmation for submitted evidence
* complete live ledger verification in every production workflow
* multi-organization Fabric governance

These belong to Sprint 7B and later bounded work. The system is not fully blockchain-integrated yet.

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
