# Authentication & Authorization Guide

## Overview

The TTC Chatbot backend implements a comprehensive authentication and authorization system with:

- **JWT Token-based Authentication**: Stateless request authentication
- **bcrypt Password Hashing**: Secure password storage
- **Role-Based Access Control (RBAC)**: Four roles with granular permissions
- **Optional Authentication**: API routes work with or without authentication
- **Default Admin Credentials**: Quick startup with demo users

## Quick Start

### 1. Initialize Admin User

After starting the application, default users are created automatically on first run:

```bash
# Option A: Automatic setup on app startup
python main.py
# Creates: admin (password: changeme), demo (password: demo123), moderator (password: mod123)

# Option B: Manual setup script
python backend/admin_setup.py

# Option C: Reset specific user password
python backend/admin_setup.py reset admin MyNewPassword123!
```

### 2. Login and Get Token

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "changeme"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "admin",
  "role": "admin"
}
```

### 3. Use Token to Access Protected Routes

```bash
curl -X GET http://localhost:8000/api/sessions \
  -H "Authorization: Bearer eyJhbGc..."
```

## API Endpoints

### Authentication Routes (`/api/auth`)

#### Register New User
```
POST /api/auth/register
Content-Type: application/json

{
  "username": "alice",
  "email": "alice@example.com",
  "password": "SecurePass123!",
  "full_name": "Alice Smith"
}

Response: 201 Created
{
  "id": "...",
  "username": "alice",
  "email": "alice@example.com",
  "full_name": "Alice Smith",
  "role": "user",
  "is_active": true,
  "is_verified": false,
  "created_at": "2025-03-16T10:00:00"
}
```

#### Login
```
POST /api/auth/login
Content-Type: application/json

{
  "username": "alice",
  "password": "SecurePass123!"
}

Response: 200 OK
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user_id": "550e8400-...",
  "username": "alice",
  "role": "user"
}
```

#### Refresh Token
```
POST /api/auth/refresh
Authorization: Bearer {current_token}

Response: 200 OK
{
  "access_token": "eyJhbGc_new...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user_id": "550e8400-...",
  "username": "alice",
  "role": "user"
}
```

#### Get Current User Profile
```
GET /api/auth/me
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "550e8400-...",
  "username": "alice",
  "email": "alice@example.com",
  "full_name": "Alice Smith",
  "role": "user",
  "is_active": true,
  "is_verified": false,
  "created_at": "2025-03-16T10:00:00",
  "last_login": "2025-03-16T12:00:00"
}
```

#### Update User Profile
```
PUT /api/auth/me?full_name=Alice%20Johnson
Authorization: Bearer {token}

Response: 200 OK
```

#### Reset Password
```
POST /api/auth/reset-password?old_password=OldPass123!&new_password=NewPass456!
Authorization: Bearer {token}

Response: 204 No Content
```

#### Setup Admin (First Run Only)
```
POST /api/auth/setup-admin?security_key=change-me-in-production
Content-Type: application/json

{
  "username": "admin",
  "email": "admin@ttc-chatbot.local",
  "password": "AdminPassword123!",
  "full_name": "System Administrator"
}

Response: 201 Created
```

## Roles & Permissions

### 1. **ADMIN** Role
Full system access. Can manage all sessions, users, and see all data.

**Permissions:**
- `users:create` - Create new users
- `users:read` - Read user info
- `users:update` - Update users
- `users:delete` - Delete users
- `sessions:read:all` - Read any session
- `sessions:delete:all` - Delete any session
- `chat:access` - Use chat
- `messages:read:all` - Read any messages
- `admin:access` - Access admin panel

### 2. **MODERATOR** Role
Can view and delete all sessions/messages, but cannot modify users.

**Permissions:**
- `users:read` - Read user info
- `sessions:read:all` - Read any session
- `sessions:delete:all` - Delete any session
- `chat:access` - Use chat
- `messages:read:all` - Read any messages

### 3. **USER** Role (Default)
Can only access own sessions and provide feedback.

**Permissions:**
- `sessions:read:own` - Read own sessions
- `sessions:update:own` - Update own sessions
- `chat:access` - Use chat
- `messages:read:own` - Read own messages
- `feedback:create` - Submit feedback

### 4. **GUEST** Role
Limited to creating new sessions and accessing chat.

**Permissions:**
- `chat:access` - Use chat
- `sessions:create` - Create new sessions

## Session Management with Authentication

### Create Session (Authenticated)
When you're logged in, sessions are automatically linked to your user:

```bash
POST /api/sessions
Authorization: Bearer {token}
Content-Type: application/json

{
  "topic": "Line 1 Delays"
}

# Session is now linked to your user_id
```

### Create Session (Unauthenticated)
Sessions can still be created without authentication:

```bash
POST /api/sessions
Content-Type: application/json

{
  "topic": "General Question"
}

# Session has user_id = null
```

### Access Control

**Own Sessions (USER):**
- Can view own sessions
- Can update own sessions
- Can delete own sessions
- Can submit feedback
- Cannot access others' sessions

**All Sessions (ADMIN/MODERATOR):**
- Can view ALL sessions
- Can delete ANY session
- Can see all messages
- No restrictions

## Password Requirements

Passwords must meet these requirements:
- **Minimum 8 characters**
- **At least 1 uppercase letter** (A-Z)
- **At least 1 lowercase letter** (a-z)
- **At least 1 digit** (0-9)
- **At least 1 special character** (!@#$%^&*(),.?":{}|<>)

### Valid Examples:
- `SecurePass123!`
- `MyP@ssw0rd`
- `TCC_Chat#2024`

### Invalid Examples:
- `password` (no uppercase, digits, special)
- `Pass123` (no special characters)
- `P@ss` (too short)

## Environment Variables

Configure auth system with environment variables:

```bash
# JWT Configuration
export SECRET_KEY="your-super-secret-key-change-in-production"
export ADMIN_SETUP_KEY="change-me-in-production"

# Admin Setup (optional, defaults to: admin/changeme/admin@ttc-chatbot.local)
export ADMIN_USERNAME="admin"
export ADMIN_EMAIL="admin@ttc-chatbot.local"
export ADMIN_PASSWORD="YourSecurePassword123!"
```

## Security Best Practices

### Production Checklist:

1. **Change SECRET_KEY**
   ```bash
   # Generate a strong secret key
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   # Use in production:
   export SECRET_KEY="your-generated-key"
   ```

2. **Change Default Credentials**
   ```bash
   python backend/admin_setup.py reset admin NewAdminPassword123!
   python backend/admin_setup.py reset demo NewDemoPassword123!
   python backend/admin_setup.py reset moderator NewModPassword123!
   ```

3. **Use HTTPS** - Always use HTTPS in production

4. **Restrict CORS Origins**
   - Update CORS middleware in `main.py`
   - Change from `allow_origins=["*"]` to specific domains

5. **Set TOKEN_EXPIRE_MINUTES Appropriately**
   - Default: 30 minutes
   - Shorter for sensitive apps
   - Longer for internal tools

6. **Database Security**
   - Use PostgreSQL in production (not SQLite)
   - Use strong database credentials
   - Enable SSL connections

## Code Integration Examples

### FastAPI Route with Required Authentication

```python
from fastapi import APIRouter, Depends
from backend.auth import get_current_user, require_role, TokenData
from backend.models import UserRole

router = APIRouter()

@router.get("/protected")
async def protected_route(current_user: TokenData = Depends(get_current_user)):
    """This endpoint requires a valid JWT token."""
    return {"message": f"Hello, {current_user.username}!"}

@router.delete("/admin-only")
@require_role(UserRole.ADMIN)
async def admin_only(current_user: TokenData = Depends(get_current_user)):
    """Only admins can access this."""
    return {"message": "Admin access granted"}
```

### Optional Authentication Route

```python
from typing import Optional

@router.get("/optional-auth")
async def optional_auth_route(
    current_user: Optional[TokenData] = None,
    db: Session = Depends(get_db)
):
    """Authentication is optional. If provided, use it. Otherwise, proceed."""
    if current_user:
        return {"message": f"Hello, {current_user.username}"}
    else:
        return {"message": "Hello, Guest!"}
```

## Testing Authentication

### Using curl:

```bash
# 1. Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"TestPass123!"}'

# 2. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"TestPass123!"}' | jq -r '.access_token')

# 3. Access protected endpoint
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"

# 4. Create authenticated session
curl -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"topic":"My Session"}'
```

### Using Python requests:

```python
import requests

# Configure
BASE_URL = "http://localhost:8000"
credentials = {"username": "admin", "password": "changeme"}

# Login
resp = requests.post(f"{BASE_URL}/api/auth/login", json=credentials)
token = resp.json()["access_token"]

# Use token
headers = {"Authorization": f"Bearer {token}"}
sessions = requests.get(f"{BASE_URL}/api/sessions", headers=headers)
print(sessions.json())
```

## Troubleshooting

### "Invalid or expired token"
- Token has expired (expires after 30 minutes by default)
- Token is malformed or tampered with
- Secret key mismatch (different key used to encode/decode)

**Solution:** Request a new token via `/auth/login` or `/auth/refresh`

### "Invalid username or password"
- Username doesn't exist
- Password is incorrect (case-sensitive)

**Solution:** Check credentials. Register new user if needed.

### "Access denied. Required roles: [admin]"
- Your user role doesn't have permission for this action
- Admin only endpoints require admin role

**Solution:** Use an admin account or ask admin to change your role

### "Session already exists"
- Username or email already registered

**Solution:** Use different username/email or login with existing account

## File Structure

```
backend/
├── auth.py                 # Core auth logic (passwords, JWT, RBAC)
├── auth_routes.py          # Authentication API endpoints
├── schemas.py              # Pydantic validation models
├── admin_setup.py          # Admin setup and user management script
├── models.py               # Database models (User, Session, Permission)
├── database.py             # Database configuration
├── services.py             # Business logic (SessionService, etc.)
├── routes.py               # API endpoints (protected with optional auth)
└── __init__.py
```

## Next Steps

1. **Customize Permissions** - Add custom permissions in `backend/auth.py` → `ROLE_PERMISSIONS`
2. **Email Verification** - Implement email verification in `auth_routes.py` → `register()`
3. **Audit Logging** - Log auth events (login, token refresh, permission checks)
4. **Two-Factor Auth** - Add 2FA totp-based authentication
5. **API Key Auth** - Support API key authentication for machine-to-machine

---

For more information, see the main [Backend README](./readme.md) and [API Documentation](../docs/api.md).
