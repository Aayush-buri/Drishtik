# Hyperledger Fabric Blockchain Anchoring for Drishtik

## Architecture & Purpose
Drishtik utilizes Hyperledger Fabric as an enterprise permissioned ledger for **cryptographic integrity anchoring** and **chain-of-custody verification**.

### What is stored on-chain:
- Evidence SHA-256 digests
- Case identifiers and Evidence identifiers
- Procedural event types (`EVIDENCE_IMPORTED`, `EVIDENCE_ACQUIRED`, `EVIDENCE_DERIVED`, `RECOVERED_EVIDENCE_CREATED`, `AI_FRAME_EXPORTED`)
- Acting operator identity (`actor`)
- UTC ISO-8601 timestamps
- Previous event cryptographic references (creating an unbroken hash chain)
- Provenance metadata hashes

### What is strictly off-chain:
- All original video files (`.dav`, `.mp4`, `.mkv`, `.avi`)
- Raw disk images (`.raw`, `.dd`, `.img`, `.e01`)
- Derived video segments and exported JPEG frames
- Case notes, investigator credentials, and private keys

---

## Local Development Network Setup

A single-machine development topology is defined in `blockchain/docker-compose.fabric.yml`:
- **CA (Certificate Authority)**: `ca.org1.example.com` on port `7054`
- **Orderer**: `orderer.example.com` on port `7050`
- **Peer**: `peer0.org1.example.com` on port `7051`
- **Channel**: `cctvchannel`
- **Chaincode**: `evidence_anchor`

### Prerequisites:
1. Docker Desktop with Compose V2.
2. Go 1.20+ (for chaincode packaging).

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
   ```text
   Blockchain Service: UNAVAILABLE
   Blockchain anchoring unavailable. Local SHA-256 integrity and audit logging remain active.
   ```
3. Drishtik **never fabricates fake transactions or fake transaction IDs**.
