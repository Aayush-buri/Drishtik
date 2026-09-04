import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import io
import os
import uuid
from unittest.mock import patch, MagicMock
from app.main import app
from app.models.case import Case, CaseMember, RoleEnum
from app.models.user import User
from app.models.evidence import Evidence, IntegrityStatus
from app.core.security import get_password_hash

# Mock authentication
@pytest.fixture
def test_user(db_session: Session):
    user = User(username=f"evidence_tester_{uuid.uuid4().hex[:6]}", password_hash=get_password_hash("pass"), display_name="Test")
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def test_case(db_session: Session, test_user: User):
    case = Case(case_identifier=f"CASE-{uuid.uuid4().hex[:6]}", name="Test Case", created_by=test_user.id)
    db_session.add(case)
    db_session.commit()
    member = CaseMember(case_id=case.id, user_id=test_user.id, role=RoleEnum.ADMIN)
    db_session.add(member)
    db_session.commit()
    return case

def test_import_evidence(test_case: Case, test_user: User, db_session: Session):
    client = TestClient(app)
    from app.dependencies.auth import get_current_user, require_case_investigator_or_admin
    
    app.dependency_overrides[require_case_investigator_or_admin] = lambda: db_session.query(CaseMember).first()
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    file_content = f"fake video content {uuid.uuid4()}".encode()
    response = client.post(
        f"/api/v1/cases/{test_case.case_identifier}/evidence",
        files={"file": ("test_vid.mp4", io.BytesIO(file_content), "video/mp4")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["original_filename"] == "test_vid.mp4"
    assert data["size_bytes"] == len(file_content)
    assert data["integrity_status"] == "VERIFIED"
    assert "sha256" in data
    assert "md5_reference" in data

    # Verify duplicates throw 409
    response_duplicate = client.post(
        f"/api/v1/cases/{test_case.case_identifier}/evidence",
        files={"file": ("test_vid.mp4", io.BytesIO(file_content), "video/mp4")}
    )
    app.dependency_overrides = {}
    assert response_duplicate.status_code == 409

def test_compare_evidence(test_case: Case, test_user: User, db_session: Session):
    client = TestClient(app)
    from app.dependencies.auth import require_case_investigator_or_admin
    app.dependency_overrides[require_case_investigator_or_admin] = lambda: db_session.query(CaseMember).first()
    
    # Import first
    resp1 = client.post(f"/api/v1/cases/{test_case.case_identifier}/evidence", files={"file": ("v1.mp4", io.BytesIO(f"content1_{uuid.uuid4()}".encode()), "video/mp4")})
    # Import second (different content)
    resp2 = client.post(f"/api/v1/cases/{test_case.case_identifier}/evidence", files={"file": ("v2.mp4", io.BytesIO(f"content2_{uuid.uuid4()}".encode()), "video/mp4")})
    
    id1 = resp1.json()["id"]
    id2 = resp2.json()["id"]
    
    compare_resp = client.post(
        f"/api/v1/cases/{test_case.case_identifier}/evidence/compare",
        json={"evidence_ids": [id1, id2]}
    )
    app.dependency_overrides = {}
    
    assert compare_resp.status_code == 200
    assert compare_resp.json()["result"] == "FILE_CONTENT_DIFFERS"


def test_invalid_case_identifier(test_case: Case, test_user: User, db_session: Session):
    client = TestClient(app)
    from app.dependencies.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    # Try to GET evidence for a case identifier that doesn't exist
    response = client.get("/api/v1/cases/INVALID-CASE-123/evidence")
    assert response.status_code == 404
    assert response.json()["detail"] == "Case not found"
    
    # Try to POST evidence for a case identifier that doesn't exist
    file_content = b"fake video content"
    response = client.post(
        "/api/v1/cases/INVALID-CASE-123/evidence",
        files={"file": ("test_vid.mp4", io.BytesIO(file_content), "video/mp4")}
    )
    assert response.status_code == 404
    
    app.dependency_overrides = {}

def test_get_evidence_list(test_case: Case, test_user: User, db_session: Session):
    client = TestClient(app)
    from app.dependencies.auth import get_current_user, require_case_member
    
    app.dependency_overrides[require_case_member] = lambda: db_session.query(CaseMember).first()
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    response = client.get(f"/api/v1/cases/{test_case.case_identifier}/evidence")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    
    app.dependency_overrides = {}
