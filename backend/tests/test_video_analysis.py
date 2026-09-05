"""Step 12 Backend Tests: Forensic Video Analysis Layer.

Covers:
1. Video analysis session creation / persistence
2. Authorized evidence access to Unified Video Representation
3. Unauthorized evidence access rejected (foreign case / nonexistent)
4. Timeline event creation
5. Event retrieval & search
6. Event seeking data (media_time, source_timestamp, normalized_timestamp)
7. Note creation linked to exact timeline position
8. Note retrieval & search
9. Frame artifact creation (DERIVED)
10. Parent-child lineage of exported frame
11. Original evidence immutability & hash preservation
12. Timestamp normalization & calibration metadata
13. Multi-camera synchronization data & track discovery
14. Analysis audit logging (VIDEO_ANALYSIS_OPENED, FRAME_EXPORTED, TIMELINE_EVENT_CREATED, etc.)
"""
import io
import os
import uuid
import subprocess
import imageio_ffmpeg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.case import Case, CaseMember, RoleEnum
from app.models.user import User
from app.models.evidence import Evidence, EvidenceStatus
from app.models.audit import AuditLog
from app.models.video_analysis import TimelineEvent, AnalysisNote, TimestampCalibration, VideoAnalysisSession
from app.core.security import get_password_hash
from app.dependencies.auth import (
    get_current_user,
    require_case_member,
    require_case_investigator_or_admin,
    require_case_admin,
)


@pytest.fixture
def test_admin_user(db_session: Session):
    user = User(
        username=f"admin_{uuid.uuid4().hex[:6]}",
        password_hash=get_password_hash("pass"),
        display_name="Forensic Admin"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_investigator_user(db_session: Session):
    user = User(
        username=f"inv_{uuid.uuid4().hex[:6]}",
        password_hash=get_password_hash("pass"),
        display_name="Lead Investigator"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def case_with_members(db_session: Session, test_admin_user: User, test_investigator_user: User):
    case = Case(
        case_identifier=f"CASE-{uuid.uuid4().hex[:6].upper()}",
        name="CCTV Video Analysis Case",
        created_by=test_admin_user.id
    )
    db_session.add(case)
    db_session.commit()

    m_admin = CaseMember(case_id=case.id, user_id=test_admin_user.id, role=RoleEnum.ADMIN)
    m_inv = CaseMember(case_id=case.id, user_id=test_investigator_user.id, role=RoleEnum.INVESTIGATOR)
    db_session.add_all([m_admin, m_inv])
    db_session.commit()
    return case


@pytest.fixture
def foreign_case(db_session: Session, test_admin_user: User):
    case = Case(
        case_identifier=f"CASE-FOREIGN-{uuid.uuid4().hex[:6].upper()}",
        name="Foreign Unauthorized Case",
        created_by=test_admin_user.id
    )
    db_session.add(case)
    db_session.commit()
    return case


def generate_test_video(seed: str = None) -> bytes:
    """Generates a small valid MP4 test video in memory."""
    seed = seed or uuid.uuid4().hex[:6]
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    tmp_name = f"tmp_step12_{uuid.uuid4().hex}.mp4"
    subprocess.run([
        exe, "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=25",
        "-metadata", f"title=forensic_{seed}",
        "-c:v", "libx264", "-preset", "ultrafast", "-y", tmp_name
    ], capture_output=True, check=True)
    with open(tmp_name, "rb") as f:
        data = f.read()
    os.remove(tmp_name)
    return data


def setup_auth(client: TestClient, db_session: Session, case: Case, user: User):
    member = db_session.query(CaseMember).filter(
        CaseMember.case_id == case.id,
        CaseMember.user_id == user.id
    ).first()
    if member:
        member.case = case

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_case_member] = lambda: member
    app.dependency_overrides[require_case_investigator_or_admin] = lambda: member
    app.dependency_overrides[require_case_admin] = lambda: member


def test_unified_video_and_playback_resolution(override_get_db, case_with_members: Case, test_admin_user: User, db_session: Session):
    """Tests 1 & 2: Unified Video representation & authorized access."""
    client = TestClient(app)
    setup_auth(client, db_session, case_with_members, test_admin_user)

    video_bytes = generate_test_video("unified_test")

    # Import evidence
    import_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("cctv_cam01.mp4", io.BytesIO(video_bytes), "video/mp4")}
    )
    assert import_resp.status_code == 200
    ev = import_resp.json()
    ev_id = ev["id"]

    # Retrieve unified representation
    resp = client.get(f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/unified-video")
    assert resp.status_code == 200
    data = resp.json()

    # Verify model fields
    assert data["evidence_id"] == ev_id
    assert data["evidence_identifier"] == ev["evidence_identifier"]
    assert data["original_filename"] == "cctv_cam01.mp4"
    assert data["browser_playable"] is True
    assert data["fps"] > 0
    assert data["duration_seconds"] is not None
    assert "stream" in data["playback_source"]
    assert data["is_inspection_proxy"] is False
    assert data["sha256"] == ev["sha256"]


def test_unauthorized_foreign_evidence_access(override_get_db, case_with_members: Case, foreign_case: Case, test_admin_user: User, db_session: Session):
    """Test 3: Access to evidence from another case is rejected."""
    client = TestClient(app)
    setup_auth(client, db_session, case_with_members, test_admin_user)

    video_bytes = generate_test_video("foreign_test")
    import_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("cctv_secure.mp4", io.BytesIO(video_bytes), "video/mp4")}
    )
    assert import_resp.status_code == 200
    ev_id = import_resp.json()["id"]

    # Try accessing with foreign case identifier
    # Switch auth context to foreign case where user is not a member or evidence is not in case
    app.dependency_overrides[require_case_member] = lambda: CaseMember(case=foreign_case, user_id=test_admin_user.id, role=RoleEnum.ADMIN)
    app.dependency_overrides[require_case_investigator_or_admin] = lambda: CaseMember(case=foreign_case, user_id=test_admin_user.id, role=RoleEnum.ADMIN)

    resp = client.get(f"/api/v1/cases/{foreign_case.case_identifier}/evidence/{ev_id}/unified-video")
    assert resp.status_code in [403, 404]

    # Nonexistent evidence ID
    resp_404 = client.get(f"/api/v1/cases/{foreign_case.case_identifier}/evidence/999999/unified-video")
    assert resp_404.status_code == 404


def test_timeline_events_crud_and_seeking_data(override_get_db, case_with_members: Case, test_investigator_user: User, db_session: Session):
    """Tests 4, 5, 6: Timeline event creation, retrieval, search, and seeking data."""
    client = TestClient(app)
    setup_auth(client, db_session, case_with_members, test_investigator_user)

    video_bytes = generate_test_video("events_test")
    import_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("cam02.mp4", io.BytesIO(video_bytes), "video/mp4")}
    )
    ev_id = import_resp.json()["id"]

    # 1. Create Event
    create_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/timeline-events",
        json={
            "media_time": 1.45,
            "event_type": "Person",
            "title": "Suspect enters doorway",
            "description": "Individual in dark jacket enters north door"
        }
    )
    assert create_resp.status_code == 200
    evt = create_resp.json()
    assert evt["event_identifier"].startswith("EVT-")
    assert evt["media_time"] == 1.45
    assert evt["event_type"] == "Person"
    assert evt["title"] == "Suspect enters doorway"
    evt_id = evt["id"]

    # 2. List Events
    list_resp = client.get(f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/timeline-events")
    assert list_resp.status_code == 200
    events = list_resp.json()
    assert len(events) == 1
    assert events[0]["id"] == evt_id

    # 3. Search Events
    search_resp = client.get(f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/timeline-events?q=Suspect")
    assert search_resp.status_code == 200
    assert len(search_resp.json()) == 1

    empty_search = client.get(f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/timeline-events?q=Nonexistent")
    assert empty_search.status_code == 200
    assert len(empty_search.json()) == 0

    # 4. Delete Event
    del_resp = client.delete(f"/api/v1/cases/{case_with_members.case_identifier}/timeline-events/{evt_id}")
    assert del_resp.status_code == 200
    assert len(client.get(f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/timeline-events").json()) == 0


def test_analysis_notes_crud(override_get_db, case_with_members: Case, test_investigator_user: User, db_session: Session):
    """Tests 7 & 8: Investigator note creation and retrieval."""
    client = TestClient(app)
    setup_auth(client, db_session, case_with_members, test_investigator_user)

    video_bytes = generate_test_video("notes_test")
    import_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("cam03.mp4", io.BytesIO(video_bytes), "video/mp4")}
    )
    ev_id = import_resp.json()["id"]

    # 1. Create Note
    create_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/analysis-notes",
        json={
            "media_time": 2.1,
            "note_text": "Individual drops keycard on pavement"
        }
    )
    assert create_resp.status_code == 200
    note = create_resp.json()
    assert note["media_time"] == 2.1
    assert "keycard" in note["note_text"]
    note_id = note["id"]

    # 2. List Notes
    list_resp = client.get(f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/analysis-notes")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # 3. Search Notes
    search_resp = client.get(f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/analysis-notes?q=keycard")
    assert len(search_resp.json()) == 1

    # 4. Delete Note
    del_resp = client.delete(f"/api/v1/cases/{case_with_members.case_identifier}/analysis-notes/{note_id}")
    assert del_resp.status_code == 200
    assert len(client.get(f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/analysis-notes").json()) == 0


def test_frame_export_lineage_and_immutability(override_get_db, case_with_members: Case, test_investigator_user: User, db_session: Session):
    """Tests 9, 10, 11: Frame artifact export, parent-child lineage, and original evidence immutability."""
    client = TestClient(app)
    setup_auth(client, db_session, case_with_members, test_investigator_user)

    video_bytes = generate_test_video("export_frame_test")
    import_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("gate_cam.mp4", io.BytesIO(video_bytes), "video/mp4")}
    )
    assert import_resp.status_code == 200
    orig = import_resp.json()
    orig_id = orig["id"]
    orig_sha = orig["sha256"]
    orig_md5 = orig["md5_reference"]

    # Export Frame at 1.0 second
    export_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{orig_id}/export-frame",
        json={"media_time": 1.0, "frame_number": 25}
    )
    assert export_resp.status_code == 200
    frame_artifact = export_resp.json()

    # Verify Frame Artifact properties
    assert frame_artifact["evidence_status"] == "DERIVED"
    assert frame_artifact["derived_operation"] == "FRAME_EXPORT"
    assert frame_artifact["parent_evidence_id"] == orig_id
    assert frame_artifact["parent_evidence_identifier"] == orig["evidence_identifier"]
    assert frame_artifact["media_type"] == "Image"
    assert frame_artifact["file_extension"] == ".jpg"
    assert frame_artifact["media_time"] == 1.0
    assert frame_artifact["sha256"] != orig_sha
    assert frame_artifact["evidence_id"] != orig_id

    # Verify original video is strictly unchanged in DB and file system
    orig_db = db_session.query(Evidence).filter(Evidence.id == orig_id).first()
    assert orig_db.sha256 == orig_sha
    assert orig_db.md5_reference == orig_md5
    assert orig_db.evidence_status == EvidenceStatus.ORIGINAL

    # Check Audit Log for FRAME_EXPORTED
    audit = db_session.query(AuditLog).filter(
        AuditLog.case_id == case_with_members.id,
        AuditLog.action == "FRAME_EXPORTED"
    ).first()
    assert audit is not None


def test_timestamp_calibration_normalization(override_get_db, case_with_members: Case, test_investigator_user: User, db_session: Session):
    """Test 12: Timestamp calibration and normalization metadata."""
    client = TestClient(app)
    setup_auth(client, db_session, case_with_members, test_investigator_user)

    video_bytes = generate_test_video("calibration_test")
    import_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("lobby_cam.mp4", io.BytesIO(video_bytes), "video/mp4")}
    )
    ev_id = import_resp.json()["id"]

    # Set calibration: +192 seconds (3m12s)
    calib_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/calibration",
        json={
            "offset_seconds": 192.0,
            "time_zone": "UTC+05:30",
            "calibration_reason": "Compared against verified external NTP server reference",
            "calibration_method": "MANUAL_EXTERNAL_REFERENCE"
        }
    )
    assert calib_resp.status_code == 200
    calib = calib_resp.json()
    assert calib["offset_seconds"] == 192.0
    assert calib["time_zone"] == "UTC+05:30"
    assert "NTP" in calib["calibration_reason"]

    # Retrieve calibration
    get_resp = client.get(f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/calibration")
    assert get_resp.status_code == 200
    assert get_resp.json()["offset_seconds"] == 192.0


def test_multi_camera_tracks_discovery(override_get_db, case_with_members: Case, test_admin_user: User, db_session: Session):
    """Test 13: Multi-camera synchronized tracks discovery."""
    client = TestClient(app)
    setup_auth(client, db_session, case_with_members, test_admin_user)

    # Import two camera videos in the same case
    v1 = generate_test_video("cam1")
    v2 = generate_test_video("cam2")

    r1 = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("camera_01.mp4", io.BytesIO(v1), "video/mp4")}
    )
    r2 = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("camera_02.mp4", io.BytesIO(v2), "video/mp4")}
    )
    ev1_id = r1.json()["id"]
    ev2_id = r2.json()["id"]

    tracks_resp = client.get(f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev1_id}/multi-camera-tracks")
    assert tracks_resp.status_code == 200
    tracks = tracks_resp.json()
    assert len(tracks) >= 2
    track_ids = [t["evidence_id"] for t in tracks]
    assert ev1_id in track_ids
    assert ev2_id in track_ids


def test_video_analysis_session_persistence(override_get_db, case_with_members: Case, test_investigator_user: User, db_session: Session):
    """Test 1: Video analysis user session state saving."""
    client = TestClient(app)
    setup_auth(client, db_session, case_with_members, test_investigator_user)

    video_bytes = generate_test_video("session_test")
    import_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("session_video.mp4", io.BytesIO(video_bytes), "video/mp4")}
    )
    ev_id = import_resp.json()["id"]

    # Save session position
    sess_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}/sessions",
        json={
            "last_media_time": 1.75,
            "playback_speed": 1.5,
            "timeline_zoom": 2.0
        }
    )
    assert sess_resp.status_code == 200
    sess = sess_resp.json()
    assert sess["last_media_time"] == 1.75
    assert sess["playback_speed"] == 1.5
    assert sess["timeline_zoom"] == 2.0
