# Hyperledger Fabric Blockchain Anchoring for Drishtik

## Architecture & Purpose
Drishtik utilizes Hyperledger Fabric as an enterprise permissioned ledger for **cryptographic integrity anchoring** and **chain-of-custody verification**.

## Current Architecture (Sprint 7A)

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

### Current verified capability after Sprint 7A

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

### What is NOT complete yet

Sprint 7A does **not** yet provide:

* end-to-end real transaction submission from the forensic custody workflow
* real commit-event confirmation integrated into custody processing
* application-level block-number confirmation for submitted evidence
* complete live ledger verification in every production workflow
* multi-organization Fabric governance

## Identity and Security Handling

* certificates and private keys are supplied through configuration paths
* private keys must not be committed
* real credentials must not be stored in Git
* example configuration must contain only placeholders
* production secrets belong outside the repository

---

## Local Development Network Setup

A single-machine development topology is defined in lockchain/docker-compose.fabric.yml:
- **CA (Certificate Authority)**: ca.org1.example.com on port 7054
- **Orderer**: orderer.example.com on port 7050
- **Peer**: peer0.org1.example.com on port 7051
- **Channel**: cctvchannel
- **Chaincode**: vidence_anchor

### Prerequisites:
1. Docker Desktop with Compose V2.
2. Go 1.20+ (for chaincode packaging).
3. Node.js (for Gateway Adapter).

### Starting the Local Fabric Network:
`ash
cd blockchain
docker compose -f docker-compose.fabric.yml up -d
`

### Deploying the Chaincode:
`ash
# Package and install the chaincode on peer0.org1
peer lifecycle chaincode package evidence_anchor.tar.gz --path ./chaincode --lang golang --label evidence_anchor_1.0
peer lifecycle chaincode install evidence_anchor.tar.gz
`

---

## Drishtik Offline / Fail-Safe Behavior
If the Hyperledger Fabric runtime is not running or unreachable:
1. Drishtik operations continue safely without blocking evidence import, acquisition, or video analysis.
2. The UI clearly reports:
   Blockchain Service: UNAVAILABLE
   Blockchain anchoring unavailable. Local SHA-256 integrity and audit logging remain active.
3. Drishtik **never fabricates fake transactions or fake transaction IDs**.
