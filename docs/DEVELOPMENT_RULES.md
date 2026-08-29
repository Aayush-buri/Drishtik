# Drishtik: Development Rules & Governance Policy

> **Authoritative reference.** All developers, contributors, and AI coding agents
> MUST follow these rules when working on the Drishtik codebase.

---

## Part I — Forensic Integrity Laws

These rules are non-negotiable. Violations compromise evidence admissibility.

1. **Never unnecessarily modify original evidence.**
   All raw evidence drives, partitions, and files must be treated as immutable. Analysis must be conducted via write-blocking or read-only modes.

2. **Work on forensic copies/images where appropriate.**
   Examiners and automated pipelines must perform carving, parsing, and analysis on verified bit-stream forensic images (`.dd`, `.raw`, `.E01`) or verified working copies — never on original source drives.

3. **Preserve original timestamps.**
   Never overwrite or alter original embedded device timestamps, partition headers, or file system creation/modification times during ingestion or conversion.

4. **Store normalized timestamps separately.**
   UTC-normalized timestamps must be stored as separate metadata attributes alongside original timestamps. Normalization must never overwrite originals.

5. **SHA-256 is the primary integrity hash.**
   All evidence files, disk images, carved video streams, and audit records must use SHA-256 for cryptographic integrity validation.

6. **MD5 is optional and secondary/reference only.**
   MD5 hashing is provided strictly as an optional legacy reference value. MD5 must never replace SHA-256 for primary integrity verification.

7. **Never invent undocumented vendor formats.**
   Do not guess, hallucinate, or fabricate proprietary binary layouts or video headers without verified documentation, specification, or validated reverse engineering.

8. **Never claim unsupported functionality works.**
   If a feature, vendor model, codec, or partition scheme is not implemented, the system must clearly report it as unsupported. Return an explicit `UNSUPPORTED` status.

9. **Recovered evidence must be clearly labeled.**
   Any data carved from unallocated clusters or reconstructed from damaged headers must be explicitly tagged: `RECOVERED EVIDENCE`. Never claim full recovery when only fragments are found.

10. **AI results must be marked as AI-generated findings.**
    All detections, classifications, bounding boxes, and motion analysis produced by AI/ML models must be labeled: `AI-GENERATED FINDING`.

11. **AI results must never overwrite original evidence metadata.**
    AI annotations exist as auxiliary analytical layers stored separately. They must never replace or modify inherent video stream properties or original evidence data.

12. **Do not silently fabricate forensic results.**
    Never extrapolate missing timestamps, fabricate non-existent frames, invent hash values, or report false verification passes. Zero-speculation forensics.

---

## Part II — Security & Repository Rules

13. **Never commit real CCTV evidence.**
    No live surveillance media, drive dumps, or operational case videos may be committed to the repository.

14. **Never commit secrets.**
    API keys, certificates (`.key`, `.pem`, `.crt`), private keys, passwords, and `.env` credential files must never be committed.

15. **Never commit real case data or PII.**
    No witness names, case numbers, officer credentials, or location metadata from live investigations.

16. **Imported evidence is untrusted input.**
    All ingested files, containers, vendor stream data, and external metadata must be treated as hostile input. Implement defensive boundary checks, integer overflow protections, and subprocess isolation.

17. **Security must be considered before implementation.**
    Threat modeling, input sanitization, buffer boundary checks, and least-privilege principles must guide all feature designs before code is written.

18. **Individual authentication only.**
    Every user must authenticate with a unique username and unique password. Shared or generic team accounts are prohibited. Roles: ADMIN, INVESTIGATOR, VIEWER.

---

## Part III — Architectural Rules

19. **Layer separation is mandatory.**
    Frontend, backend API, application services, forensic engine, vendor parsers, AI engine, video engine, hashing, and database are distinct layers. Each layer has a single responsibility. See `docs/architecture/SYSTEM_ARCHITECTURE.md` for boundary definitions.

20. **Frontend must not directly manipulate evidence files.**
    All file access is routed through the backend API. The frontend renderer never touches the filesystem directly.

21. **Vendor support must use modular adapters.**
    Each DVR/NVR vendor filesystem must be implemented as an isolated, pluggable parser module inheriting from the common `VendorAdapter` interface in `parsers/common/`.

22. **Long forensic operations must not block the UI.**
    Acquisition, hashing, carving, AI inference, video conversion, report generation, and blockchain transactions must run as background jobs with progress reporting via WebSocket.

23. **Every major feature requires tests.**
    All parser modules, carving algorithms, integrity checkers, API endpoints, and security controls must be accompanied by unit tests, and where appropriate integration and forensic test suites.

24. **Evidence operations must be auditable.**
    Every ingestion, extraction, hash verification, export, analysis action, and user operation must generate an append-only audit log record.

25. **Device and Evidence are distinct concepts.**
    A Device is the origin/container of evidence (DVR, NVR, disk, image). Evidence is the acquired/imported forensic data derived from a device through an acquisition.

26. **Original data and derived data must be stored separately.**
    Original timestamps, file metadata, and hash baselines are immutable records. Normalized timestamps, AI findings, parsed vendor metadata, and recovered fragments are derived data stored in separate tables/fields.

27. **Unsupported operations must return explicit unsupported status.**
    All functions encountering unrecognized vendor signatures, codecs, or unreadable sectors must raise explicit, structured unsupported errors rather than failing silently or fabricating output.

---

## Part IV — Blockchain Rules

28. **Actual CCTV video must never be stored on blockchain.**
    Raw video streams and heavy binary media must never be stored on the blockchain ledger.

29. **Blockchain stores appropriate hash/custody records only.**
    The Hyperledger Fabric ledger stores: case ID, evidence ID, SHA-256 hash, action, user identity, timestamp, and transaction ID.

30. **Blockchain must support offline fallback.**
    If the Fabric network is unavailable, forensic workflow must continue using local database only. The UI must clearly indicate blockchain status. Never falsely indicate a successful blockchain commit.

---

## Part V — AI Agent Rules

31. **All AI coding agents must inspect project instructions before modifying code.**
    AI assistants must read `DEVELOPMENT_RULES.md`, `SYSTEM_ARCHITECTURE.md`, `MODULE_ARCHITECTURE.md`, and relevant architecture documents before generating code.

32. **AI agents must not rewrite unrelated modules.**
    Refactoring and code generation must be tightly scoped to the assigned task. Do not modify untouched subsystems.

33. **Document limitations.**
    Any code that operates with known limitations (partial vendor support, approximate timestamp normalization, limited carving coverage) must clearly document those limitations in code comments and API responses.

---

## Part VI — Hash Comparison Integrity

34. **Hash comparison proves binary identity, not event identity.**
    SHA-256 comparison can confirm that two files contain identical bytes. It does NOT prove that two videos depict the same physical event, scene, or timeframe.

---

## Part VII — Future UI Architecture Concept

> [!NOTE]
> This represents the planned design direction for the future desktop interface. **Do not implement this UI yet.**

### Application Level
```
Case Manager (entry point)
├── New Case → Create Admin Account → Open Case
├── Open Case → Case Authentication → Case Dashboard
└── Search Cases
```

### Case Level Navigation
```
Dashboard
Evidence
Devices
Acquisition
Video Analysis
Recovery
Timeline
AI Analysis
Records
Settings
```

### Global / Bottom Controls
```
Home / Case Manager    (returns to Case Manager)
Notifications          (async job status, integrity alerts)
Settings               (global preferences)
```

### Architectural Constraints on UI Navigation
- **No duplicate "Cases" section inside the case workspace.** Case switching happens via Case Manager only.
- **No "Recent Activity" section.** Dashboard shows only useful case statistics and optional Recent Evidence preview.
- **No separate "Integrity" navigation item.** Integrity verification belongs inside the Evidence section.
- **No separate "Videos" and "Video Analysis" sections.** There is ONE section: Video Analysis.
- **Records combines Audit Log and Reports** in one section with a resizable divider between the two panels.
- **Settings contains Collaborator management.**
- **Notifications are global** — not per-section.

### Dashboard Concept
- Minimal summary cards: Evidence count, Devices, Videos, Recovered items, AI events.
- Optional: Recent Evidence preview, Timeline overview, Quick Actions.
- No excessive cards. No "Recent Activity" feed.

### Evidence Workspace Concept
- Card/grid-first presentation.
- Evidence card fields: Evidence ID, File name, Source, Type, Size, Format, Hash status, Processing status, Evidence status, Preview (where safe).
- Actions: Open, Details, Compare, Verify, Analyze, Export (where authorized).
- Integrity verification is inside the Evidence section.
- Evidence comparison supports two or more files.

### Video Analysis Workspace Concept
- One unified section (not separate Videos + Video Analysis).
- Workspace: Video player, playback controls, next/previous video, metadata panel, AI findings, event markers, timeline, camera information, investigator notes.
- **No video editing features** (no color grading, transitions, effects, editing timeline tracks, creative tools).

### Recovery Workspace Concept
- Operates on forensic copies/images/test datasets only.
- Supports: deleted file analysis, unallocated space analysis, file carving, recovered file validation.
- All recovered items labeled: `RECOVERED EVIDENCE`.

### Records Workspace Concept
- Combines Audit Log and Reports in one section: **Records**.
- Two panels with a resizable divider/sidebar control.

### Settings Concept
Categories: General, Security, Collaborators, Evidence, Video, AI, Blockchain, Reports, Advanced.
