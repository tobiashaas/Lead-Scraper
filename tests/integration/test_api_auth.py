"""
Integration Tests für Authentication API Endpoints
"""

import pytest

from app.core.security import get_password_hash
from app.database.models import User, UserRole


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    """Create an admin user"""
    admin = User(
        username="admin",
        email="admin@example.com",
        full_name="Admin User",
        hashed_password=get_password_hash("admin123"),
        role=UserRole.ADMIN,
        is_superuser=True,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


class TestAuthenticationEndpoints:
    """Test Suite für Authentication API Endpoints"""

    def test_register_new_user(self, client):
        """Test: Register a new user"""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpass123",
            "full_name": "New User",
        }

        response = client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 201
        data = response.json()

        assert data["username"] == user_data["username"]
        assert data["email"] == user_data["email"]
        assert data["full_name"] == user_data["full_name"]
        assert "id" in data
        assert "hashed_password" not in data  # Password should not be returned

    def test_register_duplicate_username(self, client, test_user):
        """Test: Register with existing username should fail"""
        user_data = {
            "username": test_user.username,
            "email": "different@example.com",
            "password": "password123",
        }

        response = client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_duplicate_email(self, client, test_user):
        """Test: Register with existing email should fail"""
        user_data = {
            "username": "differentuser",
            "email": test_user.email,
            "password": "password123",
        }

        response = client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_login_success(self, client, test_user):
        """Test: Login with correct credentials"""
        login_data = {"username": "testuser", "password": "testpass123"}

        response = client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, test_user):
        """Test: Login with wrong password should fail"""
        login_data = {"username": "testuser", "password": "wrongpassword"}

        response = client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """Test: Login with non-existent user should fail"""
        login_data = {"username": "nonexistent", "password": "password123"}

        response = client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 401

    def test_get_current_user(self, client, test_user):
        """Test: Get current user info"""
        # Login first
        login_response = client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "testpass123"}
        )
        token = login_response.json()["access_token"]

        # Get current user
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()

        assert data["username"] == test_user.username
        assert data["email"] == test_user.email
        assert data["id"] == test_user.id

    def test_get_current_user_without_token(self, client):
        """Test: Access /me without token should fail"""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401  # No credentials provided (Unauthorized)

    def test_get_current_user_invalid_token(self, client):
        """Test: Access /me with invalid token should fail"""
        response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid_token"})

        assert response.status_code == 401

    def test_refresh_token(self, client, test_user):
        """Test: Refresh access token"""
        # Login first
        login_response = client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "testpass123"}
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh token
        response = client.post("/api/v1/auth/refresh", params={"refresh_token": refresh_token})

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert "refresh_token" in data

    def test_change_password(self, client, test_user):
        """Test: Change user password"""
        # Login first
        login_response = client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "testpass123"}
        )
        token = login_response.json()["access_token"]

        # Change password
        password_data = {"old_password": "testpass123", "new_password": "newpass456"}

        response = client.post(
            "/api/v1/auth/change-password",
            json=password_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

        # Try login with new password
        login_response = client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "newpass456"}
        )

        assert login_response.status_code == 200

    def test_change_password_wrong_old_password(self, client, test_user):
        """Test: Change password with wrong old password should fail"""
        # Login first
        login_response = client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "testpass123"}
        )
        token = login_response.json()["access_token"]

        # Try to change password with wrong old password
        password_data = {"old_password": "wrongpassword", "new_password": "newpass456"}

        response = client.post(
            "/api/v1/auth/change-password",
            json=password_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_list_users_as_admin(self, client, admin_user):
        """Test: Admin can list all users"""
        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
        )
        token = login_response.json()["access_token"]

        # List users
        response = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        users = response.json()

        assert isinstance(users, list)
        assert len(users) >= 1

    def test_list_users_as_regular_user(self, client, test_user):
        """Test: Regular user cannot list users"""
        # Login as regular user
        login_response = client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "testpass123"}
        )
        token = login_response.json()["access_token"]

        # Try to list users
        response = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 403  # Forbidden
