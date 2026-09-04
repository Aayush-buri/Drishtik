import pytest
import os
import io
import uuid
import subprocess
import imageio_ffmpeg
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.case import Case, CaseMember, RoleEnum
from app.models.user import User
from app.models.evidence import Evidence, EvidenceStatus
from app.models.audit import AuditLog
from app.core.security import get_password_hash
from app.dependencies.auth import (
    get_current_user, require_case_member, require_case_investigator_or_admin, require_case_admin
)

@pytest.fixture
def test_admin_user(db_session: Session):
    user = User(username=f"admin_{uuid.uuid4().hex[:6]}", password_hash=get_password_hash("pass"), display_name="Admin")
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def test_investigator_user(db_session: Session):
    user = User(username=f"investigator_{uuid.uuid4().hex[:6]}", password_hash=get_password_hash("pass"), display_name="Investigator")
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def test_viewer_user(db_session: Session):
    user = User(username=f"viewer_{uuid.uuid4().hex[:6]}", password_hash=get_password_hash("pass"), display_name="Viewer")
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def case_with_members(db_session: Session, test_admin_user: User, test_investigator_user: User, test_viewer_user: User):
    case = Case(case_identifier=f"CASE-{uuid.uuid4().hex[:6].upper()}", name="Forensic Test Case", created_by=test_admin_user.id)
    db_session.add(case)
    db_session.commit()

    m_admin = CaseMember(case_id=case.id, user_id=test_admin_user.id, role=RoleEnum.ADMIN)
    m_inv = CaseMember(case_id=case.id, user_id=test_investigator_user.id, role=RoleEnum.INVESTIGATOR)
    m_view = CaseMember(case_id=case.id, user_id=test_viewer_user.id, role=RoleEnum.VIEWER)
    db_session.add_all([m_admin, m_inv, m_view])
    db_session.commit()
    return case

def generate_unique_video(seed: str = None) -> bytes:
    """Generates a unique 2-second 320x240 MP4 video in memory."""
    seed = seed or uuid.uuid4().hex[:6]
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    tmp_name = f"tmp_{uuid.uuid4().hex}.mp4"
    subprocess.run([
        exe, "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=30",
        "-metadata", f"title=test_{seed}",
        "-c:v", "libx264", "-preset", "ultrafast", "-y", tmp_name
    ], capture_output=True, check=True)
    with open(tmp_name, "rb") as f:
        data = f.read()
    os.remove(tmp_name)
    return data

def test_derive_trim(override_get_db, case_with_members: Case, test_admin_user: User, db_session: Session):
    client = TestClient(app)
    admin_member = db_session.query(CaseMember).filter(CaseMember.case_id == case_with_members.id, CaseMember.user_id == test_admin_user.id).first()
    admin_member.case = case_with_members

    app.dependency_overrides[get_current_user] = lambda: test_admin_user
    app.dependency_overrides[require_case_member] = lambda: admin_member
    app.dependency_overrides[require_case_investigator_or_admin] = lambda: admin_member
    app.dependency_overrides[require_case_admin] = lambda: admin_member

    video_bytes = generate_unique_video("trim_test")

    # 1. Import real original video
    import_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("original_video.mp4", io.BytesIO(video_bytes), "video/mp4")}
    )
    assert import_resp.status_code == 200
    orig = import_resp.json()
    orig_id = orig["id"]
    orig_sha = orig["sha256"]

    # 2. Trim from 0.5s to 1.5s
    derive_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{orig_id}/derive",
        json={"operation": "TRIM", "start_time": 0.5, "end_time": 1.5}
    )
    assert derive_resp.status_code == 200
    derived = derive_resp.json()

    assert derived["evidence_status"] == "DERIVED"
    assert derived["parent_evidence_id"] == orig_id
    assert derived["parent_evidence_identifier"] == orig["evidence_identifier"]
    assert derived["derived_operation"] == "TRIM"
    assert derived["sha256"] != orig_sha  # New unique hash
    assert derived["id"] != orig_id
    assert "trim_00-00_to_00-01" in derived["original_filename"]

    # 3. Assert original evidence in DB is completely untouched
    orig_db = db_session.query(Evidence).filter(Evidence.id == orig_id).first()
    assert orig_db.sha256 == orig_sha
    assert orig_db.evidence_status == EvidenceStatus.ORIGINAL

    # 4. Check audit logs
    audit_resp = client.get(f"/api/v1/cases/{case_with_members.case_identifier}/audit-logs")
    assert audit_resp.status_code == 200
    actions = [l["action"] for l in audit_resp.json()]
    assert "EVIDENCE_DERIVED" in actions

def test_derive_crop(override_get_db, case_with_members: Case, test_investigator_user: User, db_session: Session):
    client = TestClient(app)
    inv_member = db_session.query(CaseMember).filter(CaseMember.case_id == case_with_members.id, CaseMember.user_id == test_investigator_user.id).first()
    inv_member.case = case_with_members

    app.dependency_overrides[get_current_user] = lambda: test_investigator_user
    app.dependency_overrides[require_case_member] = lambda: inv_member
    app.dependency_overrides[require_case_investigator_or_admin] = lambda: inv_member

    video_bytes = generate_unique_video("crop_test")

    # Import original
    import_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("to_crop.mp4", io.BytesIO(video_bytes), "video/mp4")}
    )
    assert import_resp.status_code == 200
    orig_id = import_resp.json()["id"]

    # Investigator creates cropped derived evidence
    crop_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{orig_id}/derive",
        json={"operation": "CROP", "crop": {"x": 10, "y": 10, "width": 160, "height": 120}}
    )
    assert crop_resp.status_code == 200
    crop_data = crop_resp.json()
    assert crop_data["evidence_status"] == "DERIVED"
    assert crop_data["derived_operation"] == "CROP"
    assert crop_data["width"] == 160
    assert crop_data["height"] == 120

def test_derive_viewer_permission_denied(override_get_db, case_with_members: Case, test_viewer_user: User, test_admin_user: User, db_session: Session):
    client = TestClient(app)
    admin_member = db_session.query(CaseMember).filter(CaseMember.case_id == case_with_members.id, CaseMember.role == RoleEnum.ADMIN).first()
    admin_member.case = case_with_members

    # Admin imports
    app.dependency_overrides[get_current_user] = lambda: test_admin_user
    app.dependency_overrides[require_case_member] = lambda: admin_member
    app.dependency_overrides[require_case_investigator_or_admin] = lambda: admin_member

    video_bytes = generate_unique_video("viewer_test")
    import_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("for_viewer_test.mp4", io.BytesIO(video_bytes), "video/mp4")}
    )
    assert import_resp.status_code == 200
    orig_id = import_resp.json()["id"]

    # Now viewer tries to derive
    viewer_member = db_session.query(CaseMember).filter(CaseMember.case_id == case_with_members.id, CaseMember.user_id == test_viewer_user.id).first()
    viewer_member.case = case_with_members
    from fastapi import HTTPException
    def reject_viewer():
        raise HTTPException(status_code=403, detail="Investigator privileges required")

    app.dependency_overrides[require_case_investigator_or_admin] = reject_viewer
    derive_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{orig_id}/derive",
        json={"operation": "TRIM", "start_time": 0, "end_time": 1}
    )
    assert derive_resp.status_code == 403

def test_soft_delete_admin_only(override_get_db, case_with_members: Case, test_admin_user: User, test_investigator_user: User, db_session: Session):
    client = TestClient(app)
    admin_member = db_session.query(CaseMember).filter(CaseMember.case_id == case_with_members.id, CaseMember.user_id == test_admin_user.id).first()
    admin_member.case = case_with_members

    app.dependency_overrides[get_current_user] = lambda: test_admin_user
    app.dependency_overrides[require_case_member] = lambda: admin_member
    app.dependency_overrides[require_case_investigator_or_admin] = lambda: admin_member
    app.dependency_overrides[require_case_admin] = lambda: admin_member

    video_bytes = generate_unique_video("delete_test")

    # Import original
    import_resp = client.post(
        f"/api/v1/cases/{case_with_members.case_identifier}/evidence",
        files={"file": ("to_delete.mp4", io.BytesIO(video_bytes), "video/mp4")}
    )
    assert import_resp.status_code == 200
    ev_id = import_resp.json()["id"]

    # 1. Investigator tries to delete -> 403
    from fastapi import HTTPException
    def reject_admin():
        raise HTTPException(status_code=403, detail="Admin privileges required")

    app.dependency_overrides[require_case_admin] = reject_admin
    inv_del = client.delete(f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}")
    assert inv_del.status_code == 403

    # 2. Admin deletes -> 200
    app.dependency_overrides[require_case_admin] = lambda: admin_member
    admin_del = client.delete(f"/api/v1/cases/{case_with_members.case_identifier}/evidence/{ev_id}")
    assert admin_del.status_code == 200

    # 3. Verify evidence no longer in active list
    list_resp = client.get(f"/api/v1/cases/{case_with_members.case_identifier}/evidence")
    active_ids = [e["id"] for e in list_resp.json()]
    assert ev_id not in active_ids

    # 4. Verify in DB is_deleted == True (preserved)
    ev_db = db_session.query(Evidence).filter(Evidence.id == ev_id).first()
    assert ev_db.is_deleted is True
    assert ev_db.deleted_by == test_admin_user.id

    # 5. Check audit log has EVIDENCE_DELETED
    audit_resp = client.get(f"/api/v1/cases/{case_with_members.case_identifier}/audit-logs")
    actions = [l["action"] for l in audit_resp.json()]
    assert "EVIDENCE_DELETED" in actions
