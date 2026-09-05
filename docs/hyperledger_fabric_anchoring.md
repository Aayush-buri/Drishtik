# Hyperledger Fabric Integrity Anchoring & Chain of Custody

## 1. Executive Summary & Forensic Purpose
Digital CCTV evidence is vulnerable to allegations of post-seizure tampering, deletion, trimming, or metadata manipulation. In criminal and civil proceedings, establishing an unforgeable, verifiable chain of custody is essential for court admissibility.

Drishtik integrates **Hyperledger Fabric** as an enterprise-grade, permissioned blockchain integrity anchoring layer. By anchoring evidence cryptographic digests (SHA-256) and procedural custody transitions into an append-only distributed ledger, Drishtik guarantees that any retrospective alteration of evidence files or case audit logs is immediately detected.

---

## 2. Forensic Claim Boundaries (What Blockchain Proves vs Does Not Prove)

> [!IMPORTANT]
> **Strict Forensic Admissibility Boundaries**:
> - **Integrity & Immutability**: Anchoring proves that a specific file with a specific SHA-256 digest existed at a specific point in time and has not been altered since that record was committed.
> - **Procedural Provenance**: It proves the chronological sequence of custody events (e.g. who imported, derived, carved, or exported the frame).
> - **What it DOES NOT Prove**:
>   1. **Real-world Authenticity / Truth**: Blockchain anchoring does **not** prove that the video footage represents true historical events (e.g., deepfakes or pre-acquisition manipulated footage will produce valid hashes).
>   2. **Hardware Genuineness**: It does **not** authenticate the physical CCTV camera sensor or guarantee lack of physical tampering prior to acquisition.
>   3. **Human Identification**: It does **not** prove the identity of persons or vehicles detected in the video frames.

---

## 3. Off-Chain vs On-Chain Architecture

To ensure high performance, privacy, and compliance with data minimization requirements:

| Component | Storage Location | Rationale |
| :--- | :--- | :--- |
| **CCTV Video & Storage Images** (`.dav`, `.mp4`, `.raw`, `.dd`) | **Off-Chain** (Drishtik Storage) | Large binary media exceeds block size limits; video files never touch the blockchain. |
| **Exported Frame Images** (`.jpg`, `.png`) | **Off-Chain** (Drishtik Storage) | Stored as derived artifacts with unique SHA-256 hashes. |
| **Evidence SHA-256 & MD5 Digests** | **On-Chain** (Hyperledger Fabric) | Cryptographic proof of integrity; 64-character hexadecimal string. |
| **Case & Evidence Identifiers** (`CASE-XXXX`, `EVD-XXXX`) | **On-Chain** (Hyperledger Fabric) | Verifiable relational linkage to Drishtik case files. |
| **Custody Transitions & Operator ID** | **On-Chain** (Hyperledger Fabric) | Non-repudiation of investigator actions. |
| **Previous Event Reference Hash** | **On-Chain** (Hyperledger Fabric) | Unbroken hash chain preventing retroactive event insertion or reordering. |
| **Provenance Metadata Hash** | **On-Chain** (Hyperledger Fabric) | Canonical JSON hash of camera model, channel, and acquisition params. |

---

## 4. Hyperledger Fabric Network Topology

A dedicated local permissioned network is configured via `blockchain/docker-compose.fabric.yml`:
- **Network Name**: `drishtik-fabric-net`
- **Channel**: `cctvchannel`
- **Chaincode**: `evidence_anchor` (Go Contract API)
- **Organization**: `Org1MSP`
- **Peer**: `peer0.org1.example.com` (Port `7051`, Gossip `7051`, Chaincode `7052`)
- **Orderer**: `orderer.example.com` (Raft Consensus, Port `7050`)
- **Certificate Authority**: `ca.org1.example.com` (Port `7054`)

---

## 5. Smart Contract Data Model (`EvidenceAnchor`)

```go
type EvidenceAnchor struct {
    AnchorID      string `json:"anchor_id"`       // ANCH-XXXXXX
    CaseID        string `json:"case_id"`         // Case identifier
    EvidenceID    string `json:"evidence_id"`     // Evidence identifier
    SHA256        string `json:"sha256"`          // 64-char hex digest
    EventType     string `json:"event_type"`      // EVIDENCE_IMPORTED, EVIDENCE_DERIVED, etc.
    Actor         string `json:"actor"`           // Username / Operator ID
    Timestamp     string `json:"timestamp"`       // RFC3339 UTC timestamp
    Source        string `json:"source"`          // "Drishtik Forensic Engine"
    MetadataHash  string `json:"metadata_hash"`   // SHA-256 of canonical JSON metadata
    TransactionID string `json:"transaction_id"`  // Fabric cryptographic TxID
    BlockNumber   uint64 `json:"block_number"`    // Immutable ledger block index
}
```

---

## 6. Procedural Workflows

### A. Automatic Anchoring on Forensic Lifecycle Events
When any of the following lifecycle operations occurs, Drishtik automatically records a `CustodyEvent` and packages an `EvidenceAnchor`:
1. `EVIDENCE_IMPORTED`: Initial evidence upload.
2. `EVIDENCE_ACQUIRED`: Controlled bitstream acquisition from hardware device.
3. `EVIDENCE_DERIVED`: Forensic trim, crop, or proprietary proxy generation.
4. `RECOVERED_EVIDENCE_CREATED`: Carved video candidate from raw disk image.
5. `AI_FRAME_EXPORTED`: Extracted frame from YOLO/OpenCV AI detection finding.

Each event includes the hash of the preceding custody event (`previous_event_reference`), forming a contiguous cryptographic chain.

### B. 3-Point Blockchain Integrity Verification Workflow
When an investigator clicks `[ Verify Blockchain Integrity ]`:
```text
1. Storage Check: Recalculate fresh SHA-256 directly from file on disk.
2. Database Check: Compare with recorded SHA-256 in Drishtik database.
3. Ledger Query: Query Hyperledger Fabric peer for anchored record.
4. Triangulation:
   If Disk == Database == Blockchain:
       → Status: VERIFIED
       → Audit Event: BLOCKCHAIN_INTEGRITY_VERIFIED
   If Disk != Database OR Database != Blockchain:
       → Status: MISMATCH (Diagnostic reason detailing exact hash variance)
       → Audit Event: BLOCKCHAIN_INTEGRITY_FAILED
```

---

## 7. Non-Blocking Fault Tolerance & Offline Behavior

If the Hyperledger Fabric runtime is stopped, unconfigured, or unreachable:
1. **Zero Operational Blockage**: Evidence import, video analysis, frame export, and recovery carving proceed without failure.
2. **Explicit Transparency**: The UI displays:
   ```text
   Blockchain Service: UNAVAILABLE
   Blockchain anchoring unavailable. Local SHA-256 integrity and audit logging remain active.
   ```
3. **No Fabricated Data**: Drishtik **never fabricates fake transactions or fake transaction IDs**. Missing ledger transactions are flagged as `UNAVAILABLE` or `NOT_ANCHORED`.
