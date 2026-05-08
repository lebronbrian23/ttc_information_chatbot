# 🔐 Authentication Implementation - Setup Guide

## Overview

Your TTC Chatbot backend now has complete authentication and authorization! This document guides you through setup and verification.

## What You Got

### ✨ New Components

1. **`backend/auth.py`** (250+ lines)
   - Password hashing with bcrypt
   - JWT token management
   - Role-based access control
   - Admin setup helpers

2. **`backend/auth_routes.py`** (330+ lines)
   - 7 new API endpoints for authentication
   - User registration with password validation
   - Login with JWT token generation
   - Token refresh mechanism
   - Profile management

3. **`backend/schemas.py`** (370+ lines)
   - 20+ Pydantic validation models
   - Input validation with constraints
   - Email validation
   - Password complexity checking
   - Request/response serialization

4. **`backend/admin_setup.py`** (200+ lines)
   - CLI tool for user management
   - Admin initialization
   - Password reset utility

5. **`backend/AUTHENTICATION.md`** (500+ lines)
   - Complete authentication guide
   - API documentation
   - Role definitions
   - Security best practices

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
# Update pip
pip install --upgrade pip

# Install required packages
pip install -r requirements.txt

# Verify auth packages are installed
python -c "import jose; import passlib; print('✅ Dependencies installed')"
```

### Step 2: Initialize Database & Users

```bash
# Option A: Run the app (auto-initializes on startup)
python main.py
# Look for output: "✅ Default users configured (admin/demo/moderator)"

# Option B: Manual setup
python backend/admin_setup.py
```

### Step 3: Test Authentication

```bash
# In another terminal, login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme"}'

# Response will include JWT token:
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user_id": "550e8400-...",
  "username": "admin",
  "role": "admin"
}

# Use token to access protected routes
curl -X GET http://localhost:8000/api/sessions \
  -H "Authorization: Bearer eyJhbGc..."
```

### Step 4: Interactive API Documentation

Visit `http://localhost:8000/docs` and test endpoints with the Swagger UI!

## 📋 Available Default Users

| Username | Password | Role | Permissions |
|----------|----------|------|------------|
| `admin` | `changeme` | ADMIN | All permissions, full system access |
| `demo` | `demo123` | USER | Can only access own sessions |
| `moderator` | `mod123` | MODERATOR | Can moderate all sessions |

## 📝 New API Endpoints

### Authentication (`/api/auth`)

#### Register
```bash
POST /api/auth/register
Content-Type: application/json

{
  "username": "alice",
  "email": "alice@example.com",
  "password": "SecurePass123!",
  "full_name": "Alice Smith"
}
```

**Password Requirements:**
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit
- At least 1 special character (!@#$%^&*(),.?":{}|<>)

**Valid Examples:**
- `MyPassword123!`
- `TTC_Chat#2024`
- `Secure@Pass99`

#### Login
```bash
POST /api/auth/login
Content-Type: application/json

{
  "username": "alice",
  "password": "SecurePass123!"
}
```

Returns JWT token valid for 30 minutes.

#### Refresh Token
```bash
POST /api/auth/refresh
Authorization: Bearer {current_token}
```

Get new token before current one expires.

#### Get Profile
```bash
GET /api/auth/me
Authorization: Bearer {token}
```

#### Update Profile
```bash
PUT /api/auth/me?full_name=New%20Name
Authorization: Bearer {token}
```

#### Reset Password
```bash
POST /api/auth/reset-password?old_password=Old123!&new_password=New456!
Authorization: Bearer {token}
```

#### Setup Admin (First Run Only)
```bash
POST /api/auth/setup-admin?security_key=change-me-in-production
Content-Type: application/json

{
  "username": "admin",
  "email": "admin@example.com",
  "password": "AdminPassword123!",
  "full_name": "System Admin"
}
```

## 🔄 Updated Session Routes

All session routes now have **optional authentication**:

- `POST /api/sessions` - Auto-link session to authenticated user
- `GET /api/sessions` - See own sessions (or all if admin)
- `GET /api/sessions/{id}` - Verify ownership before returning
- `PATCH /api/sessions/{id}` - Verify ownership before update
- `DELETE /api/sessions/{id}` - Verify ownership before delete
- `POST /api/sessions/{id}/feedback` - Verify ownership
- `POST /api/sessions/{id}/export` - Verify ownership
- `GET /api/sessions/{id}/messages` - Verify ownership
- `GET /api/messages/{id}` - Verify ownership via session

### Example: Authenticated Session

```bash
# Create session linked to your user
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme"}' | jq -r '.access_token')

curl -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"topic":"Line 1 Delays"}'

# Session is now linked to admin user
# Only admin and moderators can see other users' sessions
```

## 🔐 Security Configuration

### Environment Variables

```bash
# JWT Configuration
export SECRET_KEY="your-secret-key-here"           # Change in production!
export ADMIN_SETUP_KEY="different-secret-key"      # Change in production!

# Admin Initialization (optional - uses defaults if not set)
export ADMIN_USERNAME="admin"
export ADMIN_EMAIL="admin@ttc-chatbot.local"
export ADMIN_PASSWORD="changeme"
```

### Production Checklist

Before deploying to production:

1. **Change SECRET_KEY**
   ```bash
   # Generate strong key
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   # Use in production
   export SECRET_KEY="your-generated-key"
   ```

2. **Change Default Passwords**
   ```bash
   python backend/admin_setup.py reset admin YourNewPassword123!
   python backend/admin_setup.py reset demo YourDemoPassword456!
   python backend/admin_setup.py reset moderator YourModPassword789!
   ```

3. **Use PostgreSQL Instead of SQLite**
   ```bash
   export DATABASE_URL="postgresql://user:pass@localhost/ttc_chatbot"
   ```

4. **Enable HTTPS**
   - Use SSL certificates
   - Redirect HTTP to HTTPS

5. **Restrict CORS Origins**
   - Update `main.py` CORS configuration
   - Change from `allow_origins=["*"]` to specific domains

## 📚 Authentication Flow

```
User visits app
    ↓
Needs to login
    ↓
POST /api/auth/login with credentials
    ↓
Backend validates password
    ↓
JWT token generated
    ↓
Token returned to frontend
    ↓
Frontend stores token
    ↓
All requests include: Authorization: Bearer {token}
    ↓
Backend validates token on each request
    ↓
User can access own sessions
    ↓
Admin can access all sessions
```

## 👥 Role Definitions

### ADMIN
- Full system access
- Can see all sessions
- Can delete any session
- Can manage users
- Can access admin endpoints

**Permissions:** users:*, sessions:read:all, sessions:delete:all, admin:*

### MODERATOR
- Can see all sessions
- Can delete any session
- Cannot create/manage users
- Cannot access admin endpoints

**Permissions:** sessions:read:all, sessions:delete:all, messages:read:all

### USER (Default)
- Can only see own sessions
- Can only delete own sessions
- Can submit feedback
- Can use chat

**Permissions:** sessions:read:own, sessions:update:own, chat:access

### GUEST
- Can use chat
- Can create new sessions
- Cannot view previous sessions

**Permissions:** chat:access, sessions:create

## 🧪 Testing

### Manual Testing with curl

```bash
#!/bin/bash

# 1. Register new user
echo "1️⃣ Registering user..."
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username":"testuser",
    "email":"test@example.com",
    "password":"TestPass123!",
    "full_name":"Test User"
  }'

# 2. Login
echo -e "\n2️⃣ Logging in..."
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"TestPass123!"}' | jq -r '.access_token')
echo "Token: $TOKEN"

# 3. Get profile
echo -e "\n3️⃣ Getting profile..."
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq

# 4. Create authenticated session
echo -e "\n4️⃣ Creating session..."
curl -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"topic":"Test Session"}' | jq

# 5. List sessions
echo -e "\n5️⃣ Listing sessions..."
curl -X GET http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Python Testing

```python
import requests

BASE_URL = "http://localhost:8000"

# Login
resp = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"username": "admin", "password": "changeme"}
)
token = resp.json()["access_token"]

# Create authenticated session
headers = {"Authorization": f"Bearer {token}"}
resp = requests.post(
    f"{BASE_URL}/api/sessions",
    json={"topic": "Line 1 Delays"},
    headers=headers
)
session_id = resp.json()["id"]

# List authenticated sessions
resp = requests.get(
    f"{BASE_URL}/api/sessions",
    headers=headers
)
print(f"Sessions: {resp.json()}")
```

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'jose'"
**Solution:** Install dependencies
```bash
pip install -r requirements.txt
```

### "Invalid or expired token"
**Cause:** Token has expired (30 min lifetime)
**Solution:** Call `/api/auth/refresh` to get new token or `/api/auth/login` to re-login

### "Invalid username or password"
**Cause:** Wrong credentials
**Solution:** Check username/password are correct. Use `/api/auth/login` to verify.

### "Access denied. Required roles: [admin]"
**Cause:** Your account doesn't have admin role
**Solution:** Login as admin user or ask admin to change your role

### "Cannot access other users' sessions"
**Cause:** Trying to access another user's session as regular user
**Solution:** Use admin account or access only your own sessions

## 📖 Documentation

- **Quick Start:** This file (you are reading it!)
- **Full Auth Guide:** `backend/AUTHENTICATION.md`
- **Backend Overview:** `backend/readme.md`
- **Implementation Details:** `AUTHENTICATION_IMPLEMENTATION.md`
- **API Docs:** `http://localhost:8000/docs` (interactive Swagger UI)

## ✅ Verification Steps

Run these to verify everything is working:

```bash
# 1. Check files exist
ls -la backend/auth.py backend/auth_routes.py backend/schemas.py backend/admin_setup.py

# 2. Check compilation
python -m py_compile backend/auth.py backend/auth_routes.py backend/schemas.py

# 3. Test imports (after pip install)
python -c "from backend.auth import hash_password; print('✅ Imports working')"

# 4. Start app
python main.py
# Should see: "✅ Default users configured (admin/demo/moderator)"

# 5. Test login (in another terminal)
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme"}'
# Should return access_token

# 6. Check Swagger UI
# Visit: http://localhost:8000/docs
# Should see /api/auth/* endpoints
```

## 🎯 Next Steps

1. **Change Default Passwords**
   ```bash
   python backend/admin_setup.py reset admin NewPassword123!
   ```

2. **Create Custom Users**
   ```bash
   # Use the /api/auth/register endpoint
   # Or manually with admin: python backend/admin_setup.py
   ```

3. **Test with Frontend**
   - Login to get token
   - Include token in session API calls
   - Sessions will be linked to your user

4. **Review Security**
   - Read `backend/AUTHENTICATION.md` security section
   - Implement additional measures as needed

5. **Extend Features**
   - Add email verification
   - Add two-factor authentication
   - Add audit logging
   - Add rate limiting

## 📞 Help

For detailed information:
- **API Endpoints:** See `backend/AUTHENTICATION.md` → API Endpoints section
- **Role/Permissions:** See `backend/AUTHENTICATION.md` → Roles & Permissions section  
- **Code Integration:** See `backend/AUTHENTICATION.md` → Code Integration Examples
- **Admin Setup:** Run `python backend/admin_setup.py --help`

---

**Everything is ready to go! Start with Step 1 above.** 🚀
