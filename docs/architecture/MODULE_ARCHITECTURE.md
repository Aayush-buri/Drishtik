# Drishtik: Module Architecture

> Precise definition of each module's responsibility, permitted dependencies, and strict exclusions.

---

## 1. `frontend/`

**Responsibility**: Desktop user interface for forensic workstation interaction.

**Contains**:
- Electron main process and preload scripts
- React components (TypeScript)
- Tailwind CSS styling and shadcn/ui components
- Framer Motion transitions
- State management (React context or Zustand/Jotai)
- API client layer (HTTP/WebSocket to backend)
- IPC bridge via contextBridge

**Must NOT contain**:
- Python code
- Direct evidence file reading/writing
- Forensic algorithms or disk access logic
- Vendor-specific parsing
- AI model inference
- Database access (SQLAlchemy/SQLite)
- Business logic beyond UI state management

---

## 2. `backend/`

**Responsibility**: Application server exposing versioned REST and WebSocket APIs, orchestrating services, and managing background jobs.

**Planned Internal Structure**:
```
backend/
├── api/
│   └── v1/
│       ├── auth.py           # Authentication endpoints
│       ├── cases.py          # Case management
│       ├── evidence.py       # Evidence operations
│       ├── devices.py        # Device registration/identification
│       ├── acquisitions.py   # Acquisition jobs
│       ├── videos.py         # Video analysis operations
│       ├── recovery.py       # Recovery operations
│       ├── timeline.py       # Timeline queries
│       ├── ai.py             # AI analysis jobs
│       ├── hashing.py        # Hash operations
│       ├── custody.py        # Chain-of-custody records
│       ├── records.py        # Audit log and reports
│       ├── settings.py       # Application settings
│       ├── blockchain.py     # Blockchain status/queries
│       └── notifications.py  # Notification endpoints
├── services/                  # Business logic services
├── middleware/                 # Auth, RBAC, request logging
├── schemas/                   # Pydantic request/response models
├── config/                    # Application configuration
├── jobs/                      # Background job definitions
├── main.py                    # FastAPI application entry point
└── dependencies.py            # FastAPI dependency injection
```

**Contains**:
- FastAPI application and router registration
- Pydantic schemas for request/response validation
- Service orchestration layer
- Authentication and RBAC middleware
- Job orchestrator for background tasks
- WebSocket manager for real-time updates
- Configuration management

**Must NOT contain**:
- Frontend/UI code (React, HTML, CSS)
- Low-level disk I/O or forensic engine code (delegates to `forensic_engine/`)
- Vendor-specific filesystem parsing (delegates to `parsers/`)
- FFmpeg subprocess calls (delegates to `video_engine/`)
- AI model loading or inference (delegates to `ai_engine/`)
- Direct hash computation (delegates to `hashing/`)

---

## 3. `forensic_engine/`

**Responsibility**: Low-level forensic disk access, image loading, partition analysis, and sector-level I/O.

**Contains**:
- Disk image loaders (`.dd`, `.raw`, `.img`, `.E01`)
- pytsk3 filesystem examination
- libewf Expert Witness format support
- Partition table analysis
- Sector-level reader with write-block enforcement
- Physical device access abstractions

**Must NOT contain**:
- HTTP/API endpoint definitions
- UI components
- Vendor-specific DVR/NVR format parsing (delegates to `parsers/`)
- Video decoding (delegates to `video_engine/`)
- AI inference (delegates to `ai_engine/`)
- Report generation (delegates to `reports/`)

---

## 4. `parsers/`

**Responsibility**: Modular vendor-specific filesystem parsing through a pluggable adapter pattern.

**Structure**:
```
parsers/
├── common/           # Base adapter interface and shared utilities
│   ├── base.py       # Abstract VendorAdapter class
│   ├── registry.py   # Adapter registration and discovery
│   └── types.py      # Shared type definitions
├── dahua/            # Dahua DVR/NVR filesystem adapter
├── hikvision/        # Hikvision DVR/NVR filesystem adapter
├── cpplus/           # CP Plus DVR filesystem adapter
├── uniview/          # Uniview adapter (future)
├── godrej/           # Godrej adapter (future)
├── honeywell/        # Honeywell adapter (future)
└── matrix/           # Matrix adapter (future)
```

**Common Adapter Interface** (Conceptual):
```
VendorAdapter (Abstract)
├── identify(evidence) → VendorIdentification
├── inspect(evidence) → FilesystemInspection
├── extract_metadata(evidence) → MetadataResult
├── list_recordings(evidence) → list[RecordingInfo]
├── extract_video(evidence, recording_id) → ExtractionResult
├── validate_recording(recording) → ValidationResult
└── get_capabilities() → AdapterCapabilities
```

**Must NOT contain**:
- HTTP/API code
- UI code
- AI logic
- Report generation
- Database queries (receives/returns data objects only)
- Invented/fabricated proprietary formats

---

## 5. `recovery/`

**Responsibility**: Deleted file analysis, unallocated space scanning, and file carving on forensic copies.

**Contains**:
- Deleted file index scanning
- Unallocated cluster analysis
- File carving engines (signature-based recovery)
- Recovered file validation
- Recovery result labeling (`RECOVERED EVIDENCE`)

**Must NOT contain**:
- Direct access to original evidence media (operates on forensic copies only)
- UI code
- API endpoints
- AI inference
- Vendor-specific parsing logic

---

## 6. `video_engine/`

**Responsibility**: Video stream demuxing, decoding, frame extraction, and metadata reading.

**Contains**:
- FFmpeg subprocess management
- FFprobe metadata extraction
- OpenCV frame operations
- Stream demuxing
- Codec identification and validation
- Safe frame extraction to temporary storage
- Thumbnail generation

**Must NOT contain**:
- Video editing features (color grading, transitions, effects, creative tooling)
- Re-encoding of original evidence streams (unless creating explicit working copies)
- UI code or API endpoints
- AI inference
- Vendor-specific filesystem parsing

---

## 7. `ai_engine/`

**Responsibility**: Local AI/ML inference for object detection and motion analysis.

**Contains**:
- YOLO model loading and inference
- OpenCV motion detection
- Frame preprocessing
- Detection result formatting with `AI-GENERATED FINDING` labels
- Model registry (supports model version swapping)
- Confidence threshold management

**Must NOT contain**:
- UI code or API endpoints
- Direct evidence file modification
- Vendor-specific parsing
- Report generation
- Cloud API calls for inference

---

## 8. `hashing/`

**Responsibility**: Cryptographic hash computation and verification.

**Contains**:
- SHA-256 hash computation (primary)
- MD5 hash computation (optional reference)
- File hash comparison engine
- Hash record creation
- Streaming hash computation for large files

**Must NOT contain**:
- UI code or API endpoints
- Evidence file modification
- Vendor-specific logic
- Business logic beyond hash computation

---

## 9. `timeline/`

**Responsibility**: Multi-camera chronological event alignment and timestamp normalization.

**Contains**:
- Timestamp normalizer (device-local → UTC)
- Multi-camera event aligner
- Event aggregator (video metadata, AI findings, motion events, investigator markers, system events)
- Filter engine (camera, event type, time range)
- Timeline query engine

**Must NOT contain**:
- UI code or API endpoints
- Video decoding
- AI inference
- Direct evidence file access

---

## 10. `blockchain/`

**Responsibility**: Hyperledger Fabric integration for immutable custody records.

**Contains**:
- Python client for the Node.js Fabric Gateway service
- Transaction submission (submit → committed/failed)
- Transaction query
- Verification workflow (compare local SHA-256 against ledger record)
- Offline fallback logic
- Node.js/TypeScript Fabric Gateway service (future subdirectory)

**Must NOT contain**:
- Actual video/media storage on the ledger
- UI code
- Vendor-specific parsing
- General application business logic

---

## 11. `database/`

**Responsibility**: Data persistence layer, ORM models, and schema migrations.

**Contains**:
- SQLAlchemy ORM model definitions
- Alembic migration scripts
- Database session management
- Repository pattern implementations
- Database connection configuration (SQLite / PostgreSQL)

**Must NOT contain**:
- UI code
- API endpoint definitions
- Business logic (belongs in `backend/services/`)
- Direct forensic engine calls

---

## 12. `security/`

**Responsibility**: Authentication, authorization, access control, and audit trail management.

**Contains**:
- Password hashing (bcrypt or argon2)
- User authentication logic
- RBAC role enforcement
- Session/token management
- Audit log recorder
- Chain-of-custody event recorder
- Path traversal protection utilities
- Subprocess sandboxing utilities

**Must NOT contain**:
- UI code
- API endpoint definitions (endpoints are in `backend/api/`)
- Forensic algorithms
- Vendor-specific logic

---

## 13. `reports/`

**Responsibility**: Forensic report generation.

**Contains**:
- Report template engine
- PDF generation (ReportLab or WeasyPrint)
- Evidence summary composition
- Hash verification inclusion
- Timeline and AI findings inclusion (with proper labels)
- Examiner information fields

**Must NOT contain**:
- UI code
- Video decoding
- AI inference
- Direct database queries (receives data via service layer)

---

## 14. `tests/`

**Responsibility**: Automated test suites.

**Structure**:
```
tests/
├── unit/             # Isolated unit tests for individual functions/classes
├── integration/      # Cross-module integration tests
├── forensic/         # Forensic-specific test cases (hash verification, carving validation)
└── security/         # Security-focused tests (auth, RBAC, input validation)
```

**Contains**:
- pytest test files
- Synthetic/controlled test fixtures
- Mock objects for external services
- Test configuration

**Must NOT contain**:
- Real CCTV evidence or surveillance footage
- Real credentials or API keys
- Production database files

---

## 15. `sample_data/`

**Responsibility**: Minimal synthetic test data for development and automated testing.

**Contains**:
- Synthetic binary test vectors (small, fabricated test files with known structures)
- Sample metadata JSON/YAML fixtures
- Test hash values

**Must NOT contain**:
- Real CCTV recordings
- Real forensic disk images
- Real case data or PII

---

## 16. `scripts/`

**Responsibility**: Developer utility and maintenance scripts.

**Contains**:
- Environment setup scripts
- Database initialization/migration helpers
- Development server launchers
- Code quality check runners

**Must NOT contain**:
- Production application logic
- Forensic algorithms
- UI components

---

## 17. `docs/`

**Responsibility**: Technical and forensic documentation.

**Structure**:
```
docs/
├── architecture/     # System architecture, data flow, module design, API design
├── forensic/         # Forensic methodology, vendor research, verification protocols
├── vendors/          # Vendor-specific reverse-engineering notes and format documentation
├── testing/          # Test strategy, test plans, synthetic data specifications
├── DEVELOPMENT_RULES.md   # Authoritative development governance
└── README.md              # Documentation index
```

---

## 18. `.github/workflows/`

**Responsibility**: CI/CD pipeline definitions.

**Contains**:
- GitHub Actions workflow YAML files
- Automated test runners
- Linting and code quality checks
- Security scanning configurations
