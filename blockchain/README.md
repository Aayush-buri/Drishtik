# Hyperledger Fabric Blockchain Anchoring for Drishtik

## Architecture & Purpose
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

* certificates and private keys are supplied through configuration paths
* private keys must not be committed
* real credentials must not be stored in Git
* example configuration must contain only placeholders
* production secrets belong outside the repository

---

## Local Development Network Setup

A single-machine development topology is defined in `blockchain/docker-compose.fabric.yml`:
- **CA (Certificate Authority)**: ca.org1.example.com on port 7054
- **Orderer**: orderer.example.com on port 7050
- **Peer**: peer0.org1.example.com on port 7051
- **Channel**: cctvchannel
- **Chaincode**: `evidence_anchor`

### Prerequisites:
1. Docker Desktop with Compose V2.
2. Go 1.20+ (for chaincode packaging).
3. Node.js (for Gateway Adapter).

### Starting the Local Fabric Network:
```bash
cd blockchain
docker compose -f docker-compose.fabric.yml up -d
```

### Deploying the Chaincode:
```bash
# Package and install the chaincode on peer0.org1
peer lifecycle chaincode package evidence_anchor.tar.gz --path ./chaincode --lang golang --label evidence_anchor_1.0
peer lifecycle chaincode install evidence_anchor.tar.gz
```

---

## Drishtik Offline / Fail-Safe Behavior
If the Hyperledger Fabric runtime is not running or unreachable:
1. Drishtik operations continue safely without blocking evidence import, acquisition, or video analysis.
2. The UI clearly reports:
   Blockchain Service: UNAVAILABLE
   Blockchain anchoring unavailable. Local SHA-256 integrity and audit logging remain active.
3. Drishtik **never fabricates fake transactions or fake transaction IDs**.
