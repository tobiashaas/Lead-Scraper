# API Authentication & Authorization

Die API nutzt **JWT (JSON Web Tokens)** für Authentication und **Role-Based Access Control (RBAC)** für Authorization.

## Features

- ✅ **JWT Authentication** - Sichere Token-basierte Authentifizierung
- ✅ **Role-Based Access Control** - User, Admin, Superuser Rollen
- ✅ **Protected Routes** - Alle API-Endpoints sind geschützt
- ✅ **Token Refresh** - Automatische Token-Erneuerung
- ✅ **Password Hashing** - Bcrypt für sichere Passwort-Speicherung
- ✅ **User Management** - CRUD Operations für User

## User Rollen

### 1. User (Standard)
- Zugriff auf alle Companies-Endpoints
- Zugriff auf alle Scraping-Endpoints
- Kann eigene Daten verwalten

### 2. Admin
- Alle User-Rechte
- Kann andere User verwalten (außer Superuser)
- Kann User-Passwörter ändern

### 3. Superuser
- Alle Admin-Rechte
- Kann Superuser erstellen und verwalten
- Voller System-Zugriff

## API Endpoints

### Authentication Endpoints (Public)

#### 1. Register
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "username": "newuser",
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "Max Mustermann"
}
```

**Response:**
```json
{
  "id": 1,
  "username": "newuser",
  "email": "user@example.com",
  "full_name": "Max Mustermann",
  "role": "user",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2025-01-17T20:00:00Z"
}
```

#### 2. Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "newuser",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1440
}
```

#### 3. Refresh Token
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1440
}
```

### Protected Endpoints

Alle folgenden Endpoints benötigen einen gültigen Access Token im Authorization Header:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### 4. Get Current User
```http
GET /api/v1/auth/me
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "id": 1,
  "username": "newuser",
  "email": "user@example.com",
  "full_name": "Max Mustermann",
  "role": "user",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2025-01-17T20:00:00Z"
}
```

#### 5. Change Password
```http
POST /api/v1/auth/change-password
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "current_password": "OldPass123!",
  "new_password": "NewSecurePass456!"
}
```

**Response:**
```json
{
  "message": "Password changed successfully"
}
```

#### 6. List Users (Admin only)
```http
GET /api/v1/auth/users
Authorization: Bearer {admin_access_token}
```

**Response:**
```json
{
  "total": 10,
  "skip": 0,
  "limit": 100,
  "items": [
    {
      "id": 1,
      "username": "admin",
      "email": "admin@example.com",
      "role": "admin",
      "is_active": true
    }
  ]
}
```

## Protected API Routes

### Companies API
Alle Companies-Endpoints benötigen Authentication:

```http
GET    /api/v1/companies/              # List companies
GET    /api/v1/companies/{id}          # Get company
POST   /api/v1/companies/              # Create company
PUT    /api/v1/companies/{id}          # Update company
DELETE /api/v1/companies/{id}          # Delete company
```

**Beispiel:**
```bash
curl -X GET "http://localhost:8000/api/v1/companies/" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Scraping API
Alle Scraping-Endpoints benötigen Authentication:

```http
GET    /api/v1/scraping/jobs           # List jobs
GET    /api/v1/scraping/jobs/{id}      # Get job
POST   /api/v1/scraping/jobs           # Create job
DELETE /api/v1/scraping/jobs/{id}      # Cancel job
```

**Beispiel:**
```bash
curl -X POST "http://localhost:8000/api/v1/scraping/jobs" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "source_name": "gelbe_seiten",
    "city": "Stuttgart",
    "industry": "IT",
    "max_pages": 5
  }'
```

## Client Integration

### JavaScript/TypeScript

```typescript
// Login
const loginResponse = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'user',
    password: 'password'
  })
});

const { access_token } = await loginResponse.json();

// Use token for protected requests
const companiesResponse = await fetch('http://localhost:8000/api/v1/companies/', {
  headers: {
    'Authorization': `Bearer ${access_token}`
  }
});

const companies = await companiesResponse.json();
```

### Python

```python
import requests

# Login
login_response = requests.post(
    'http://localhost:8000/api/v1/auth/login',
    json={
        'username': 'user',
        'password': 'password'
    }
)

access_token = login_response.json()['access_token']

# Use token for protected requests
headers = {'Authorization': f'Bearer {access_token}'}

companies_response = requests.get(
    'http://localhost:8000/api/v1/companies/',
    headers=headers
)

companies = companies_response.json()
```

### cURL

```bash
# Login
TOKEN=$(curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"password"}' \
  | jq -r '.access_token')

# Use token
curl -X GET "http://localhost:8000/api/v1/companies/" \
  -H "Authorization: Bearer $TOKEN"
```

## Token Lifecycle

### Access Token
- **Gültigkeit**: 24 Stunden (konfigurierbar)
- **Verwendung**: Für alle API-Requests
- **Speicherung**: Im Memory (nicht in LocalStorage!)

### Refresh Token
- **Gültigkeit**: 7 Tage (konfigurierbar)
- **Verwendung**: Zum Erneuern des Access Tokens
- **Speicherung**: HttpOnly Cookie (empfohlen)

### Token Refresh Flow

```typescript
async function makeAuthenticatedRequest(url: string) {
  let accessToken = getAccessToken();

  // Try request with current token
  let response = await fetch(url, {
    headers: { 'Authorization': `Bearer ${accessToken}` }
  });

  // If token expired, refresh and retry
  if (response.status === 401) {
    const refreshToken = getRefreshToken();

    const refreshResponse = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    });

    const { access_token } = await refreshResponse.json();
    setAccessToken(access_token);

    // Retry original request
    response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${access_token}` }
    });
  }

  return response;
}
```

## Error Handling

### 401 Unauthorized
```json
{
  "detail": "Could not validate credentials"
}
```

**Ursachen:**
- Token fehlt
- Token ist abgelaufen
- Token ist ungültig

**Lösung:** Neu einloggen oder Token refreshen

### 403 Forbidden
```json
{
  "detail": "Not enough permissions"
}
```

**Ursachen:**
- User hat nicht die erforderliche Rolle
- User ist nicht aktiv

**Lösung:** Admin kontaktieren für Rechte-Erhöhung

## Security Best Practices

### 1. Token Storage

**✅ Empfohlen:**
- Access Token: Memory (JavaScript Variable)
- Refresh Token: HttpOnly Cookie

**❌ Nicht empfohlen:**
- LocalStorage (XSS-anfällig)
- SessionStorage (XSS-anfällig)

### 2. HTTPS

**Immer HTTPS in Production verwenden:**
```python
# In config.py
class Settings(BaseSettings):
    # Force HTTPS in production
    force_https: bool = Field(default=True, env="FORCE_HTTPS")
```

### 3. Token Expiration

**Kurze Access Token Lifetime:**
```python
# In .env
ACCESS_TOKEN_EXPIRE_MINUTES=15  # 15 Minuten in Production
REFRESH_TOKEN_EXPIRE_DAYS=7     # 7 Tage
```

### 4. Password Requirements

**Starke Passwörter erzwingen:**
- Mindestens 8 Zeichen
- Groß- und Kleinbuchstaben
- Zahlen
- Sonderzeichen

### 5. Rate Limiting

**API-Requests limitieren:**
```python
# Implementierung in app/middleware/rate_limiter.py
# Max 100 Requests pro Minute pro User
```

## Admin User erstellen

```bash
# Script ausführen
python create_admin_user.py
```

Oder manuell in der Datenbank:

```python
from app.database.models import User, UserRole
from app.core.security import get_password_hash
from app.database.database import SessionLocal

db = SessionLocal()

admin = User(
    username="admin",
    email="admin@example.com",
    full_name="Admin User",
    hashed_password=get_password_hash("AdminPass123!"),
    role=UserRole.ADMIN,
    is_active=True,
    is_superuser=False
)

db.add(admin)
db.commit()
```

## Testing

### Integration Tests

Alle Tests nutzen automatisch Authentication:

```python
def test_list_companies(client, auth_headers):
    """Test with authentication"""
    response = client.get("/api/v1/companies/", headers=auth_headers)
    assert response.status_code == 200
```

### Manual Testing

```bash
# 1. Register User
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "TestPass123!",
    "full_name": "Test User"
  }'

# 2. Login
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "TestPass123!"
  }'

# 3. Use Token
curl -X GET "http://localhost:8000/api/v1/companies/" \
  -H "Authorization: Bearer {access_token}"
```

## Configuration

### Environment Variables

```env
# JWT Settings
SECRET_KEY=your-secret-key-min-32-characters-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7

# Password Requirements
MIN_PASSWORD_LENGTH=8
REQUIRE_UPPERCASE=true
REQUIRE_LOWERCASE=true
REQUIRE_DIGITS=true
REQUIRE_SPECIAL_CHARS=true
```

### Generate Secret Key

```python
import secrets
secret_key = secrets.token_urlsafe(32)
print(f"SECRET_KEY={secret_key}")
```

## Troubleshooting

### "Could not validate credentials"

**Problem:** Token wird nicht akzeptiert

**Lösung:**
1. Prüfe, ob Token im Header ist: `Authorization: Bearer {token}`
2. Prüfe Token-Format (sollte 3 Teile haben: `xxx.yyy.zzz`)
3. Prüfe Token-Ablauf (max 24h)
4. Neu einloggen

### "Not enough permissions"

**Problem:** User hat nicht die erforderliche Rolle

**Lösung:**
1. Prüfe User-Rolle: `GET /api/v1/auth/me`
2. Kontaktiere Admin für Rechte-Erhöhung

### "User is not active"

**Problem:** User-Account wurde deaktiviert

**Lösung:**
1. Kontaktiere Admin zur Reaktivierung

## Weitere Ressourcen

- [JWT.io](https://jwt.io/) - JWT Debugger
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [OAuth2 Password Flow](https://oauth.net/2/grant-types/password/)
