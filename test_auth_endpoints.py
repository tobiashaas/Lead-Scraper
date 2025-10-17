"""
Test Authentication Endpoints
"""

import httpx
import asyncio

BASE_URL = "http://localhost:8000"


async def test_auth():
    """Test authentication flow"""
    async with httpx.AsyncClient() as client:
        print("=" * 60)
        print("Testing Authentication Endpoints")
        print("=" * 60)
        print()

        # Test 1: Register new user
        print("1. Testing user registration...")
        register_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123",
            "full_name": "Test User",
        }

        try:
            response = await client.post(f"{BASE_URL}/api/v1/auth/register", json=register_data)
            if response.status_code == 201:
                print("   ✅ User registered successfully")
                user_data = response.json()
                print(f"   User ID: {user_data['id']}")
                print(f"   Username: {user_data['username']}")
            elif response.status_code == 400:
                print("   ⚠️  User already exists")
            else:
                print(f"   ❌ Registration failed: {response.status_code}")
                print(f"   {response.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        print()

        # Test 2: Login
        print("2. Testing login...")
        login_data = {"username": "admin", "password": "admin123"}

        try:
            response = await client.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
            if response.status_code == 200:
                print("   ✅ Login successful")
                tokens = response.json()
                access_token = tokens["access_token"]
                print(f"   Access Token: {access_token[:50]}...")
            else:
                print(f"   ❌ Login failed: {response.status_code}")
                print(f"   {response.json()}")
                return
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return

        print()

        # Test 3: Get current user
        print("3. Testing /me endpoint...")
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = await client.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
            if response.status_code == 200:
                print("   ✅ User info retrieved")
                user = response.json()
                print(f"   Username: {user['username']}")
                print(f"   Email: {user['email']}")
                print(f"   Role: {user['role']}")
            else:
                print(f"   ❌ Failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        print()

        # Test 4: Access protected endpoint (list users - admin only)
        print("4. Testing protected endpoint (list users)...")

        try:
            response = await client.get(f"{BASE_URL}/api/v1/auth/users", headers=headers)
            if response.status_code == 200:
                print("   ✅ Users list retrieved")
                users = response.json()
                print(f"   Total users: {len(users)}")
            else:
                print(f"   ❌ Failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        print()
        print("=" * 60)
        print("✅ Authentication tests completed!")
        print("=" * 60)


if __name__ == "__main__":
    print("\n⚠️  Make sure the API is running on http://localhost:8000")
    print("   Start with: uvicorn app.main:app --reload\n")

    try:
        asyncio.run(test_auth())
    except KeyboardInterrupt:
        print("\n\n❌ Tests interrupted")
