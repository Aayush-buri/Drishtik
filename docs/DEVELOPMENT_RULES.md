# Drishtik Development Rules & Guidelines

This document defines the core forensic integrity laws, architectural invariants, code governance rules, and future UI concepts that all developers, contributors, and AI coding agents MUST strictly follow when working on the **Drishtik** codebase.

---

## Core Forensic & Development Rules

1. **Never unnecessarily modify original evidence.**  
   All raw evidence drives, partitions, and files must be treated as immutable. Analysis must be conducted via write-blocking or read-only modes.
2. **Work on forensic copies/images where appropriate.**  
   Examiners and automated pipelines should perform deep carving, parsing, and analysis on verified bit-stream forensic images (`.dd`, `.raw`, `.E01`) or verified working copies rather than direct evidence source drives.
3. **Preserve original timestamps.**  
   Never overwrite or alter original embedded device timestamps, partition headers, or file system creation/modification times during ingestion or conversion.
4. **Store normalized timestamps separately.**  
   UTC-normalized, standardized timeline timestamps must be stored as separate metadata attributes alongside original timestamps without replacing them.
5. **SHA-256 is the primary integrity hash.**  
   All evidence files, disk images, carved video streams, and audit logs must use SHA-256 for cryptographic integrity validation.
6. **MD5 is optional and secondary/reference only.**  
   MD5 hashing is provided strictly as an optional legacy reference value and must never replace SHA-256 for primary integrity verification.
7. **Never invent undocumented vendor formats.**  
   Do not guess, hallucinate, or fabricate proprietary binary layouts or video headers without verified documentation, specification, or reverse-engineered validation.
8. **Never claim unsupported functionality works.**  
   If a feature, vendor model, codec, or partition scheme is not implemented, the system must clearly report it as unsupported.
9. **Recovered evidence must be clearly labeled as recovered.**  
   Any video clip, frame, or metadata carved from unallocated clusters or reconstructed from damaged headers must be explicitly tagged as `Recovered Evidence`.
10. **AI results must be marked as AI-generated findings.**  
    Detections, classifications, bounding boxes, and motion heatmaps produced by AI/ML models must be distinctly identified as `AI-Generated Findings`.
11. **AI results must never overwrite original evidence metadata.**  
    AI annotations exist as auxiliary analytical layers and must never replace or modify inherent video stream properties.
12. **Never commit real CCTV evidence.**  
    No live surveillance media, drive dumps, or operational case videos may be committed to the repository.
13. **Never commit secrets.**  
    API keys, certificates, private keys, passwords, and `.env` credentials must never be committed.
14. **Every major feature requires tests.**  
    All parser modules, carving algorithms, integrity checkers, and API endpoints must be accompanied by unit, integration, or forensic test suites.
15. **Long forensic operations must not block the UI.**  
    Heavy operations (disk acquisition, carving, hashing, AI inference, video transcoding) must run asynchronously in background workers with real-time status reporting.
16. **Vendor support must use modular adapters.**  
    Each DVR/NVR vendor filesystem must be implemented as an isolated, pluggable parser module inheriting from standard parser interfaces.
17. **Evidence operations must be auditable.**  
    Every ingestion, extraction, hash verification, export, and user action must generate a tamper-evident audit log record.
18. **Security must be considered before implementation.**  
    Threat modeling, input sanitization, buffer boundary checks, and least-privilege principles must guide all feature designs.
19. **Actual CCTV video must never be stored on blockchain.**  
    Raw video streams and heavy binary media must never be stored on the blockchain ledger.
20. **Blockchain stores appropriate hash/custody records only.**  
    The Hyperledger Fabric ledger stores cryptographic evidence hashes, custody transfer timestamps, examiner IDs, and audit verification proofs only.
21. **All future AI coding agents must inspect project instructions before modifying code.**  
    AI assistants must review `DEVELOPMENT_RULES.md`, `ARCHITECTURE_NOTES.md`, and project constraints before generating code.
22. **AI agents must not rewrite unrelated modules.**  
    Refactoring and code generation must be tightly scoped to the assigned task without modifying untouched subsystems.
23. **Unsupported operations must return explicit unsupported status.**  
    All functions encountering unrecognized vendor signatures, codecs, or unreadable sectors must raise explicit, structured unsupported errors rather than failing silently or fabricating output.
24. **Do not silently fabricate forensic results.**  
    Zero-speculation forensics: never extrapolate missing timestamps, fabricate non-existent frames, or report false verification passes.

---

## Future UI Architecture Concept

> [!NOTE]
> This represents the planned design direction for the future desktop interface. **Do not implement this UI yet.**

```
APPLICATION LEVEL
└── Case Manager
    ├── Create / Open Case
    └── Select Case
        └── Case Authentication (User Credentials & Role Check)

CASE LEVEL (Workstation Navigation)
├── Dashboard (High-level Case Overview & Summary Statistics)
├── Evidence (Evidence Grid/Cards, Hash Verification & Comparison)
├── Devices (Connected DVR/NVR Drives & Storage Devices)
├── Acquisition (Forensic Imaging & Physical Sector Extraction)
├── Video Analysis (Playback, Metadata, AI Findings, Synchronized Streams)
├── Recovery (Unallocated Space Carving & Deleted Video Restoration)
├── Timeline (Multi-Camera Chronological Event Alignment)
├── AI Analysis (Object Detection, Person/Vehicle Tracking, Motion Maps)
├── Records (Audit Log & Forensic Reports with Resizable Divider)
└── Settings (Case & System Configuration)

GLOBAL / BOTTOM CONTROLS
├── Home / Case Manager (Quick Navigation to Case Manager)
├── Notifications (Async Job Status, Integrity Alerts, System Prompts)
└── Settings (Global Preferences, Security, Collaborators)
```

### UI Design Principles
- **Clean, Light, Professional Workspace**: Evidence-first aesthetic without distracting dark-cyber neon accents or exaggerated glows.
- **Inspired by Professional Workstations**: Clean panel organization (conceptually inspired by professional media suites like DaVinci Resolve, without direct visual imitation).
- **Smooth & Subtle Micro-Transitions**: High responsiveness with clear visual indicators for long-running asynchronous tasks.
