import pytest
from app.models.user import User
from app.core.security import get_password_hash

@pytest.fixture
def setup_user(db_session):
    user = User(
        username="testuser",
        display_name="Test User",
        password_hash=get_password_hash("password123"),
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def setup_inactive_user(db_session):
    user = User(
        username="inactive",
        display_name="Inactive User",
        password_hash=get_password_hash("password123"),
        is_active=False
    )
    db_session.add(user)
    db_session.commit()
    return user

@pytest.mark.asyncio
async def test_login_success(async_client, setup_user):
    response = await async_client.post("/api/v1/auth/login", json={"username": "testuser", "password": "password123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_password(async_client, setup_user):
    response = await async_client.post("/api/v1/auth/login", json={"username": "testuser", "password": "wrong"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_login_unknown_username(async_client):
    response = await async_client.post("/api/v1/auth/login", json={"username": "unknown", "password": "password123"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_login_inactive_user(async_client, setup_inactive_user):
    response = await async_client.post("/api/v1/auth/login", json={"username": "inactive", "password": "password123"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_me(async_client, setup_user):
    login_res = await async_client.post("/api/v1/auth/login", json={"username": "testuser", "password": "password123"})
    token = login_res.json()["access_token"]
    
    response = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert "password_hash" not in data
    assert "password" not in data

@pytest.mark.asyncio
async def test_missing_authentication(async_client):
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_invalid_token(async_client):
    response = await async_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid_token_xyz"})
    assert response.status_code == 401
