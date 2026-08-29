---
name: drishtik-core
description: Core development rules for Drishtik Multi-Vendor DVR/NVR Forensic Analysis Platform
globs:
  - "**/*"
---

# Drishtik Core Workspace Rules

You are working on **Drishtik**, a local desktop forensic analysis platform for authorized DVR/NVR surveillance evidence examination.

Before writing or modifying any code, you MUST read and follow these project documents:
- `docs/DEVELOPMENT_RULES.md` — Authoritative governance rules
- `docs/architecture/SYSTEM_ARCHITECTURE.md` — Layer architecture and module boundaries
- `docs/architecture/MODULE_ARCHITECTURE.md` — Module responsibilities and forbidden dependencies
- `docs/architecture/DATA_FLOW.md` — Evidence lifecycle and data separation
- `docs/architecture/API_ARCHITECTURE.md` — API groups and endpoint design

## Mandatory Rules

1. **Inspect architecture before coding.** Read the architecture documents listed above before generating or modifying code. Understand which module your change belongs to and what it must not import.

2. **Preserve original evidence.** Never modify original evidence files or their metadata. All analysis operates on forensic copies. Original timestamps must be preserved alongside any normalized versions.

3. **Never invent vendor formats.** Do not guess, fabricate, or hallucinate proprietary DVR/NVR binary layouts, filesystem structures, or video headers without verified documentation.

4. **Never fake unsupported functionality.** If a feature, vendor, codec, or format is not implemented, return explicit `UNSUPPORTED` status. Never silently fabricate forensic results.

5. **Write tests with every feature.** All new modules, parsers, API endpoints, and algorithms require unit tests. Use synthetic test data only — never real CCTV evidence.

6. **Never commit real evidence or secrets.** No surveillance footage, forensic disk images, passwords, API keys, private keys, or `.env` files in the repository.

7. **Use modular vendor adapters.** Each DVR/NVR vendor parser must implement the common `VendorAdapter` interface from `parsers/common/`. No vendor-specific logic in `backend/` or `frontend/`.

8. **Preserve original timestamps.** Store normalized (UTC) timestamps separately. Never overwrite original device timestamps.

9. **Label derived data clearly.**
   - Normalized timestamps → stored as separate fields
   - Recovered data → tagged `RECOVERED EVIDENCE`
   - AI outputs → tagged `AI-GENERATED FINDING`

10. **SHA-256 is the primary integrity hash.** MD5 is optional/reference only. Hash comparison proves binary identity — it does NOT prove two videos depict the same event.

11. **Keep blockchain records separate from video.** Hyperledger Fabric stores hash/custody records only. Actual video/media must never be stored on the ledger. Support offline fallback.

12. **Maintain strict layer separation.**
    - Frontend communicates with backend through HTTP/WebSocket only (never direct Python imports)
    - Backend delegates to engines (forensic, video, AI, parsers) — does not contain domain logic
    - Engines do not import from frontend or backend/api
    - Dependencies flow downward only

13. **Do not rewrite unrelated code.** Scope changes tightly to the assigned task. Do not refactor untouched modules.

14. **Document limitations.** Any partial implementation, approximate algorithm, or known constraint must be documented in code comments and API responses.

15. **Run tests before declaring success.** Execute the relevant test suite and verify passing results before reporting completion.
