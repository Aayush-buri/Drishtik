# Drishtik: API Architecture

> Planned API group design, endpoint conventions, and versioning strategy for the FastAPI backend.
> This document defines the API surface — do NOT implement these endpoints yet.

---

## 1. API Conventions

### Versioning
All API endpoints are served under a versioned prefix:
```
/api/v1/...
```

### Router Organization
FastAPI uses modular routers. Each API group is a separate router file under `backend/api/v1/`. Routers are registered in the main application via `app.include_router()`.

### Request / Response Format
- All request and response bodies use JSON.
- Request validation uses Pydantic models (`backend/schemas/`).
- Responses follow a consistent envelope where appropriate:
```json
{
  "status": "success" | "error",
  "data": { ... },
  "message": "Human-readable message",
  "errors": [ ... ]
}
```

### Authentication
- All endpoints (except login) require a valid authentication token.
- Token is passed via `Authorization: Bearer <token>` header.
- RBAC permissions are enforced per-endpoint via middleware/dependency injection.

### Pagination
- List endpoints support pagination: `?page=1&page_size=20`
- Response includes: `total`, `page`, `page_size`, `items`.

### Error Codes
- Standard HTTP status codes: 200, 201, 400, 401, 403, 404, 409, 422, 500.
- Forensic-specific status extensions are returned in the response body (e.g., `UNSUPPORTED_VENDOR`, `HASH_MISMATCH`, `BLOCKCHAIN_UNAVAILABLE`).

---

## 2. API Groups & Planned Endpoints

### 2.1 Authentication (`/api/v1/auth/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| POST | `/auth/login` | Authenticate user, return session token | Public |
| POST | `/auth/logout` | Invalidate session | All |
| GET | `/auth/me` | Get current user profile | All |
| PUT | `/auth/password` | Change own password | All |

---

### 2.2 Cases (`/api/v1/cases/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/cases/` | List cases accessible to current user | All |
| POST | `/cases/` | Create new case (+ create admin account if first case) | Admin |
| GET | `/cases/{case_id}` | Get case details | Case members |
| PUT | `/cases/{case_id}` | Update case metadata | Admin |
| DELETE | `/cases/{case_id}` | Archive/delete case | Admin |
| GET | `/cases/{case_id}/members` | List case collaborators | Admin |
| POST | `/cases/{case_id}/members` | Add collaborator to case | Admin |
| PUT | `/cases/{case_id}/members/{user_id}` | Update collaborator role | Admin |
| DELETE | `/cases/{case_id}/members/{user_id}` | Remove collaborator | Admin |
| GET | `/cases/{case_id}/summary` | Dashboard summary statistics | Case members |

---

### 2.3 Evidence (`/api/v1/cases/{case_id}/evidence/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/evidence/` | List all evidence in case | Investigator, Viewer |
| GET | `/evidence/{evidence_id}` | Get evidence details | Investigator, Viewer |
| POST | `/evidence/` | Register new evidence | Investigator |
| PUT | `/evidence/{evidence_id}` | Update evidence metadata | Investigator |
| DELETE | `/evidence/{evidence_id}` | Remove evidence reference | Admin |
| POST | `/evidence/{evidence_id}/verify` | Trigger integrity re-verification | Investigator |
| POST | `/evidence/compare` | Compare hashes of multiple evidence items | Investigator, Viewer |
| GET | `/evidence/{evidence_id}/hash-records` | Get hash history for evidence | Investigator, Viewer |

---

### 2.4 Devices (`/api/v1/cases/{case_id}/devices/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/devices/` | List registered devices | Investigator, Viewer |
| POST | `/devices/` | Register new device | Investigator |
| GET | `/devices/{device_id}` | Get device details | Investigator, Viewer |
| PUT | `/devices/{device_id}` | Update device metadata | Investigator |
| POST | `/devices/{device_id}/identify` | Trigger vendor identification | Investigator |

---

### 2.5 Acquisitions (`/api/v1/cases/{case_id}/acquisitions/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/acquisitions/` | List acquisitions | Investigator, Viewer |
| POST | `/acquisitions/` | Start new acquisition (long-running job) | Investigator |
| GET | `/acquisitions/{acq_id}` | Get acquisition details and status | Investigator, Viewer |
| POST | `/acquisitions/{acq_id}/cancel` | Cancel running acquisition | Investigator |

---

### 2.6 Videos (`/api/v1/cases/{case_id}/videos/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/videos/` | List video files | Investigator, Viewer |
| GET | `/videos/{video_id}` | Get video details and metadata | Investigator, Viewer |
| GET | `/videos/{video_id}/stream` | Stream video for playback | Investigator, Viewer |
| GET | `/videos/{video_id}/metadata` | Get detailed stream metadata | Investigator, Viewer |
| POST | `/videos/{video_id}/extract-frames` | Extract frames (long-running job) | Investigator |
| GET | `/videos/{video_id}/frames` | List extracted frames | Investigator, Viewer |
| GET | `/videos/{video_id}/ai-findings` | Get AI findings for video | Investigator, Viewer |
| POST | `/videos/{video_id}/notes` | Add investigator note | Investigator |
| GET | `/videos/{video_id}/notes` | Get investigator notes | Investigator, Viewer |

---

### 2.7 Recovery (`/api/v1/cases/{case_id}/recovery/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/recovery/` | List recovery results | Investigator, Viewer |
| POST | `/recovery/` | Start recovery scan (long-running job) | Investigator |
| GET | `/recovery/{recovery_id}` | Get recovery result details | Investigator, Viewer |
| POST | `/recovery/{recovery_id}/validate` | Validate recovered file | Investigator |

---

### 2.8 Timeline (`/api/v1/cases/{case_id}/timeline/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/timeline/events` | Query timeline events with filters | Investigator, Viewer |
| POST | `/timeline/events` | Create investigator marker event | Investigator |
| GET | `/timeline/cameras` | List cameras for filtering | Investigator, Viewer |
| GET | `/timeline/event-types` | List available event types | Investigator, Viewer |

---

### 2.9 AI Analysis (`/api/v1/cases/{case_id}/ai/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| POST | `/ai/analyze` | Start AI analysis on evidence (long-running job) | Investigator |
| GET | `/ai/findings` | List AI findings | Investigator, Viewer |
| GET | `/ai/findings/{finding_id}` | Get AI finding details | Investigator, Viewer |
| GET | `/ai/models` | List available AI models | Investigator |

---

### 2.10 Hashing (`/api/v1/cases/{case_id}/hashing/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| POST | `/hashing/compute` | Compute hash for evidence (long-running job) | Investigator |
| POST | `/hashing/verify` | Verify evidence against baseline hash | Investigator |
| GET | `/hashing/records` | List hash records | Investigator, Viewer |

---

### 2.11 Chain of Custody (`/api/v1/cases/{case_id}/custody/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/custody/` | List custody events | Investigator, Viewer |
| GET | `/custody/{event_id}` | Get custody event details | Investigator, Viewer |
| POST | `/custody/export` | Export custody chain for legal use | Admin, Investigator |

---

### 2.12 Records (`/api/v1/cases/{case_id}/records/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/records/audit-log` | Query audit log entries | Admin, Investigator, Viewer |
| GET | `/records/reports` | List generated reports | Investigator, Viewer |
| POST | `/records/reports` | Generate new forensic report (long-running job) | Investigator |
| GET | `/records/reports/{report_id}` | Get report details | Investigator, Viewer |
| GET | `/records/reports/{report_id}/download` | Download report PDF | Investigator, Viewer |

---

### 2.13 Settings (`/api/v1/settings/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/settings/` | Get application settings | Admin |
| PUT | `/settings/` | Update application settings | Admin |
| GET | `/settings/categories` | List settings categories | Admin |

Settings categories: General, Security, Collaborators, Evidence, Video, AI, Blockchain, Reports, Advanced.

---

### 2.14 Blockchain (`/api/v1/blockchain/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/blockchain/status` | Get blockchain connection status | Admin, Investigator |
| POST | `/blockchain/verify/{evidence_id}` | Verify evidence hash against ledger | Investigator |
| GET | `/blockchain/transactions` | List recorded blockchain transactions | Admin, Investigator |

---

### 2.15 Notifications (`/api/v1/notifications/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/notifications/` | List notifications for current user | All |
| PUT | `/notifications/{notif_id}/read` | Mark notification as read | All |
| WS | `/notifications/ws` | WebSocket for real-time notifications & job progress | All |

---

### 2.16 Jobs (`/api/v1/cases/{case_id}/jobs/`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| GET | `/jobs/` | List jobs for case | Investigator, Viewer |
| GET | `/jobs/{job_id}` | Get job status and progress | Investigator, Viewer |
| POST | `/jobs/{job_id}/cancel` | Cancel running job | Investigator |

---

## 3. WebSocket Channels

### `/api/v1/notifications/ws`

Real-time push channel for:
- Job progress updates (job_id, progress percentage, status changes)
- Integrity alerts (hash mismatch detected)
- Blockchain transaction status (submitted → committed / failed)
- System notifications (acquisition complete, AI analysis ready)

Message format:
```json
{
  "type": "job_progress" | "integrity_alert" | "blockchain_status" | "notification",
  "payload": { ... },
  "timestamp": "ISO-8601"
}
```

---

## 4. Dependency Injection Strategy

FastAPI dependencies are used for cross-cutting concerns:

```python
# Conceptual — do NOT implement yet

def get_db_session() -> Session:
    """Provides database session per request."""

def get_current_user(token: str) -> User:
    """Validates auth token and returns authenticated user."""

def require_role(role: Role) -> Callable:
    """RBAC dependency that verifies user role."""

def get_case_access(case_id: UUID, user: User) -> CaseMember:
    """Verifies user has access to the specified case."""
```
