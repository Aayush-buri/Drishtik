import pytest
from app.models.user import User
from app.models.case import Case, CaseMember, RoleEnum
from app.core.security import get_password_hash

@pytest.fixture
def test_users(db_session):
    u1 = User(username="admin_user", display_name="Admin", password_hash=get_password_hash("pass"), is_active=True)
    u2 = User(username="inv_user", display_name="Investigator", password_hash=get_password_hash("pass"), is_active=True)
    u3 = User(username="view_user", display_name="Viewer", password_hash=get_password_hash("pass"), is_active=True)
    u4 = User(username="other_user", display_name="Other", password_hash=get_password_hash("pass"), is_active=True)
    db_session.add_all([u1, u2, u3, u4])
    db_session.commit()
    return {"admin": u1, "inv": u2, "view": u3, "other": u4}

@pytest.fixture
def test_case(db_session, test_users):
    c = Case(case_identifier="CASE-TEST1", name="Test Case", created_by=test_users["admin"].id)
    db_session.add(c)
    db_session.commit()
    
    m1 = CaseMember(case_id=c.id, user_id=test_users["admin"].id, role=RoleEnum.ADMIN)
    m2 = CaseMember(case_id=c.id, user_id=test_users["inv"].id, role=RoleEnum.INVESTIGATOR)
    m3 = CaseMember(case_id=c.id, user_id=test_users["view"].id, role=RoleEnum.VIEWER)
    db_session.add_all([m1, m2, m3])
    db_session.commit()
    return c

async def get_token(async_client, username, password="pass"):
    res = await async_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return res.json()["access_token"]

@pytest.mark.asyncio
async def test_create_case(async_client):
    # This endpoint creates the first admin user too!
    payload = {
        "name": "New Case",
        "description": "Desc",
        "case_type": "Theft",
        "username": "new_creator",
        "password": "new_password",
        "display_name": "New Creator"
    }
    response = await async_client.post("/api/v1/cases", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Case"
    assert data["role"] == "ADMIN"
    assert "case_identifier" in data
    
    # Verify creator became admin
    token = await get_token(async_client, "new_creator", "new_password")
    res2 = await async_client.get(f"/api/v1/cases/{data['id']}", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 200
    assert res2.json()["role"] == "ADMIN"

@pytest.mark.asyncio
async def test_list_own_cases(async_client, test_users, test_case):
    token = await get_token(async_client, "admin_user")
    res = await async_client.get("/api/v1/cases", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == test_case.id

@pytest.mark.asyncio
async def test_cannot_list_another_users_case(async_client, test_users, test_case):
    token = await get_token(async_client, "other_user")
    res = await async_client.get("/api/v1/cases", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()) == 0

@pytest.mark.asyncio
async def test_view_authorized_case(async_client, test_users, test_case):
    token = await get_token(async_client, "view_user")
    res = await async_client.get(f"/api/v1/cases/{test_case.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["role"] == "VIEWER"

@pytest.mark.asyncio
async def test_cannot_view_unauthorized_case(async_client, test_users, test_case):
    token = await get_token(async_client, "other_user")
    res = await async_client.get(f"/api/v1/cases/{test_case.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_admin_access(async_client, test_users, test_case):
    token = await get_token(async_client, "admin_user")
    res = await async_client.get(f"/api/v1/cases/{test_case.id}/members", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()) == 3

@pytest.mark.asyncio
async def test_investigator_access(async_client, test_users, test_case):
    token = await get_token(async_client, "inv_user")
    res = await async_client.get(f"/api/v1/cases/{test_case.id}/members", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

@pytest.mark.asyncio
async def test_viewer_access(async_client, test_users, test_case):
    token = await get_token(async_client, "view_user")
    res = await async_client.get(f"/api/v1/cases/{test_case.id}/members", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_viewer_cannot_manage_collaborators(async_client, test_users, test_case):
    token = await get_token(async_client, "view_user")
    res = await async_client.post(f"/api/v1/cases/{test_case.id}/members", headers={"Authorization": f"Bearer {token}"}, json={"username": "a", "display_name": "A", "role": "VIEWER"})
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_investigator_cannot_manage_collaborators(async_client, test_users, test_case):
    token = await get_token(async_client, "inv_user")
    res = await async_client.post(f"/api/v1/cases/{test_case.id}/members", headers={"Authorization": f"Bearer {token}"}, json={"username": "a", "display_name": "A", "role": "VIEWER"})
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_admin_can_add_collaborator(async_client, test_users, test_case):
    token = await get_token(async_client, "admin_user")
    payload = {"username": "new_collab", "display_name": "New Collab", "role": "VIEWER", "password": "pass"}
    res = await async_client.post(f"/api/v1/cases/{test_case.id}/members", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert res.status_code == 200
    assert res.json()["user"]["username"] == "new_collab"

@pytest.mark.asyncio
async def test_duplicate_username_rejected(async_client, test_users):
    payload = {
        "name": "Case 2",
        "username": "admin_user", # already exists
        "password": "new_password",
        "display_name": "Admin2"
    }
    res = await async_client.post("/api/v1/cases", json=payload)
    assert res.status_code == 409

@pytest.mark.asyncio
async def test_duplicate_case_membership_rejected(async_client, test_users, test_case):
    token = await get_token(async_client, "admin_user")
    # inv_user is already in case
    payload = {"username": "inv_user", "display_name": "Inv", "role": "VIEWER"}
    res = await async_client.post(f"/api/v1/cases/{test_case.id}/members", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert res.status_code == 409

@pytest.mark.asyncio
async def test_admin_can_remove_collaborator(async_client, test_users, test_case):
    token = await get_token(async_client, "admin_user")
    res = await async_client.delete(f"/api/v1/cases/{test_case.id}/members/{test_users['inv'].id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

@pytest.mark.asyncio
async def test_admin_can_change_role(async_client, test_users, test_case):
    token = await get_token(async_client, "admin_user")
    res = await async_client.put(f"/api/v1/cases/{test_case.id}/members/{test_users['inv'].id}/role", headers={"Authorization": f"Bearer {token}"}, json={"role": "ADMIN"})
    assert res.status_code == 200
    assert res.json()["role"] == "ADMIN"
