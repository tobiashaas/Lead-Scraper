"""
Integration Tests für Authentication API Endpoints
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import create_access_token, get_password_hash
from app.database.models import User, UserRole
from app.core.config import settings


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

    def test_login_inactive_user(self, client, db_session):
        """Test: Login should fail for inactive user"""
        inactive_user = User(
            username="inactive",
            email="inactive@example.com",
            hashed_password=get_password_hash("inactive123"),
            role=UserRole.USER,
            is_active=False,
        )
        db_session.add(inactive_user)
        db_session.commit()

        response = client.post(
            "/api/v1/auth/login", json={"username": "inactive", "password": "inactive123"}
        )

        assert response.status_code == 403
        assert "Inactive" in response.json()["detail"]

    def test_login_locked_user(self, client, db_session):
        """Test: Login should fail for locked users"""
        locked_user = User(
            username="locked",
            email="locked@example.com",
            hashed_password=get_password_hash("locked123"),
            role=UserRole.USER,
            is_active=True,
            locked_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(locked_user)
        db_session.commit()

        response = client.post(
            "/api/v1/auth/login", json={"username": "locked", "password": "locked123"}
        )

        assert response.status_code == 403
        assert "Account locked" in response.json()["detail"]

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

    def test_refresh_token_invalid_token(self, client):
        """Test: Refresh should fail for malformed tokens"""
        response = client.post("/api/v1/auth/refresh", params={"refresh_token": "invalid"})

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    def test_refresh_token_inactive_user(self, client, db_session, test_user):
        """Test: Refresh should fail if user becomes inactive"""
        login_response = client.post(
            "/api/v1/auth/login", json={"username": "testuser", "password": "testpass123"}
        )
        refresh_token = login_response.json()["refresh_token"]

        # Deactivate user after issuing refresh token
        test_user.is_active = False
        db_session.commit()

        response = client.post("/api/v1/auth/refresh", params={"refresh_token": refresh_token})

        assert response.status_code == 401
        assert "inactive" in response.json()["detail"].lower()

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

    def test_change_password_missing_token(self, client):
        """Test: Change password without authentication should fail"""
        response = client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "anything", "new_password": "newpass"},
        )

        assert response.status_code == 401

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

    def test_refresh_token_expired(self, client, test_user):
        """Test: Refresh token should fail if expired"""
        # Create an expired refresh token
        expires_delta = timedelta(seconds=-1)  # Already expired
        refresh_token = create_access_token(
            data={"sub": test_user.username, "type": "refresh"},
            expires_delta=expires_delta
        )

        # Try to refresh with expired token
        response = client.post("/api/v1/auth/refresh", params={"refresh_token": refresh_token})
        
        assert response.status_code == 401
        assert "invalid refresh token" in response.json()["detail"].lower()

    def test_refresh_token_wrong_type(self, client, test_user):
        """Test: Refresh should fail if token has wrong type"""
        # Create an access token (type=access) and try to use it as refresh token
        access_token = create_access_token(
            data={"sub": test_user.username, "type": "access"}
        )
        
        response = client.post("/api/v1/auth/refresh", params={"refresh_token": access_token})
        
        assert response.status_code == 401
        assert "invalid refresh token" in response.json()["detail"].lower()

    def test_failed_login_attempts_counter(self, client, db_session, test_user):
        """Test: Failed login attempts should be tracked and account locked after 5 attempts"""
        # Initial failed attempts should be 0
        assert test_user.failed_login_attempts == 0
        assert test_user.locked_until is None
        
        # Make 4 failed login attempts (not enough to lock)
        for _ in range(4):
            response = client.post(
                "/api/v1/auth/login", 
                json={"username": "testuser", "password": "wrongpassword"}
            )
            assert response.status_code == 401
        
        # Check that counter was incremented but account not locked yet
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 4
        assert test_user.locked_until is None
        
        # 5th failed attempt should lock the account
        response = client.post(
            "/api/v1/auth/login", 
            json={"username": "testuser", "password": "wrongpassword"}
        )
        assert response.status_code == 401
        
        # Check that account is now locked
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 5
        assert test_user.locked_until is not None
        # Convert naive datetime to timezone-aware for comparison
        locked_until_aware = test_user.locked_until.replace(tzinfo=timezone.utc) if test_user.locked_until.tzinfo is None else test_user.locked_until
        assert locked_until_aware > datetime.now(timezone.utc)
        
        # Unlock account manually for next test
        test_user.locked_until = None
        test_user.failed_login_attempts = 0
        db_session.commit()
        
        # Successful login should reset counter
        response = client.post(
            "/api/v1/auth/login", 
            json={"username": "testuser", "password": "testpass123"}
        )
        assert response.status_code == 200
        
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 0

    def test_last_login_updated_on_successful_login(self, client, test_user, db_session):
        """Test: Last login timestamp should be updated on successful login"""
        initial_last_login = test_user.last_login
        
        # Login successfully
        response = client.post(
            "/api/v1/auth/login", 
            json={"username": "testuser", "password": "testpass123"}
        )
        assert response.status_code == 200
        
        # Check that last_login was updated
        db_session.refresh(test_user)
        assert test_user.last_login is not None
        assert test_user.last_login != initial_last_login

    def test_admin_list_users_pagination(self, client, db_session, admin_user):
        """Test: Admin can paginate through user list"""
        # Create additional test users
        for i in range(5):
            user = User(
                username=f"testuser_{i}",
                email=f"test_{i}@example.com",
                hashed_password=get_password_hash("password"),
                role=UserRole.USER,
                is_active=True
            )
            db_session.add(user)
        db_session.commit()
        
        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login", 
            json={"username": "admin", "password": "admin123"}
        )
        token = login_response.json()["access_token"]
        
        # Get first page (2 users)
        response = client.get(
            "/api/v1/auth/users?skip=0&limit=2",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        users_page1 = response.json()
        assert len(users_page1) == 2
        
        # Get second page
        response = client.get(
            "/api/v1/auth/users?skip=2&limit=2",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        users_page2 = response.json()
        assert len(users_page2) == 2
        
        # Verify users are different between pages
        user_ids_page1 = {user["id"] for user in users_page1}
        user_ids_page2 = {user["id"] for user in users_page2}
        assert user_ids_page1.isdisjoint(user_ids_page2)
