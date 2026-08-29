# Drishtik Documentation Directory

Technical and forensic documentation for **Drishtik: Multi-Vendor DVR/NVR Forensic Analysis Platform**.

---

## Governance

| Document | Purpose |
| :--- | :--- |
| [DEVELOPMENT_RULES.md](file:///c:/Users/HP/Desktop/Project/Drishtik/docs/DEVELOPMENT_RULES.md) | Authoritative development governance: 34 forensic integrity, security, architecture, blockchain, AI agent, and UI rules. |

---

## Architecture Documents

| Document | Purpose |
| :--- | :--- |
| [SYSTEM_ARCHITECTURE.md](file:///c:/Users/HP/Desktop/Project/Drishtik/docs/architecture/SYSTEM_ARCHITECTURE.md) | 14-layer system architecture, component diagram, technology mapping, module boundaries, dependency direction, job architecture, Electron security, and runtime modes. |
| [DATA_FLOW.md](file:///c:/Users/HP/Desktop/Project/Drishtik/docs/architecture/DATA_FLOW.md) | 17-stage evidence lifecycle (Case → Device → Acquisition → Evidence → … → Report), data separation model, evidence hierarchy, and API request flow. |
| [MODULE_ARCHITECTURE.md](file:///c:/Users/HP/Desktop/Project/Drishtik/docs/architecture/MODULE_ARCHITECTURE.md) | Each module's responsibility, permitted dependencies, planned internal structure, and strict exclusions. |
| [API_ARCHITECTURE.md](file:///c:/Users/HP/Desktop/Project/Drishtik/docs/architecture/API_ARCHITECTURE.md) | 16 API endpoint groups with methods, roles, versioning strategy, WebSocket channels, and dependency injection plan. |
| [ARCHITECTURE_NOTES.md](file:///c:/Users/HP/Desktop/Project/Drishtik/docs/architecture/ARCHITECTURE_NOTES.md) | Preliminary technology stack and UI/UX workspace concepts (Phase 1 reference — superseded by detailed architecture documents above). |

---

## Documentation Subdirectories

| Directory | Purpose |
| :--- | :--- |
| `architecture/` | System architecture, data flow, module design, API design, and component diagrams. |
| `forensic/` | Forensic methodologies, write-blocking protocols, filesystem specifications, and verification algorithms. |
| `vendors/` | Vendor-specific research, reverse-engineering notes, partition layouts, and frame header specifications. |
| `testing/` | Test strategy, test plans, synthetic test data specifications, and CI/CD procedures. |
