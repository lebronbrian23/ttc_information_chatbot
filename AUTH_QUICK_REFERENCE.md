# 🔐 TTC Chatbot Authentication - Quick Reference Card

## 🚀 Quick Start (3 Steps)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app (creates default users)
python main.py

# 3. In another terminal, login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme"}'
```

---

## 🎫 Default Users

| User | Pass | Role |
|------|------|------|
| admin | changeme | ADMIN |
| demo | demo123 | USER |
| moderator | mod123 | MODERATOR |

---

## 📡 API Endpoints

### Authentication (`/api/auth`)
- `POST /register` - Create account
- `POST /login` - Get token
- `POST /refresh` - Refresh token
- `GET /me` - Get profile
- `PUT /me` - Update profile
- `POST /reset-password` - Change password

### Sessions (`/api/sessions`)
- All 9 endpoints now have optional authentication
- Users see only their own sessions (unless admin)
- Admins see all sessions

---

## 🔑 Getting a Token

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme"}'

# Response:
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user_id": "550e8400-...",
  "username": "admin",
  "role": "admin"
}
```

---

## 🛡️ Using a Token

```bash
# Include in Authorization header
curl -X GET http://localhost:8000/api/sessions \
  -H "Authorization: Bearer eyJhbGc..."

# Or use with Python
import requests
headers = {"Authorization": f"Bearer {token}"}
resp = requests.get("http://localhost:8000/api/sessions", headers=headers)
```

---

## 👥 Roles & Permissions

### ADMIN
- See all sessions ✅
- Delete any session ✅
- Manage users ✅
- Admin access ✅

### MODERATOR
- See all sessions ✅
- Delete sessions ✅
- Cannot manage users ❌

### USER (Default)
- See own sessions only ✅
- Update own sessions ✅
- Delete own sessions ✅
- Cannot see others ❌

### GUEST
- Chat only ✅
- Create sessions ✅
- View sessions ❌

---

## 🔒 Password Requirements

- Minimum 8 characters
- At least 1 UPPERCASE letter
- At least 1 lowercase letter  
- At least 1 digit (0-9)
- At least 1 special (!@#$%^&*)

**Valid:** `MyPassword123!` `Secure@Pass99` `TTC#Chat2024`
**Invalid:** `password` `Pass123` `P@ss`

---

## 📚 Full Documentation

| File | What's Inside |
|------|---|
| `AUTHENTICATION_SETUP_GUIDE.md` | Step-by-step setup & testing |
| `AUTHENTICATION_IMPLEMENTATION.md` | What was implemented |
| `backend/AUTHENTICATION.md` | Complete auth reference |
| `backend/readme.md` | Backend overview |

---

## 🆘 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| "ModuleNotFoundError: jose" | Run `pip install -r requirements.txt` |
| "Invalid token" | Token expired - get new one with `/login` |
| "Invalid credentials" | Wrong username/password |
| "Access denied" | Not admin - can't access that resource |
| "Cannot access other's session" | Users can only see their own |

---

## ⚡ Common Tasks

### Create New User
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "email": "alice@example.com",
    "password": "SecurePass123!",
    "full_name": "Alice Smith"
  }'
```

### Refresh Token (Before Expiry)
```bash
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Authorization: Bearer {current_token}"
```

### Reset User Password
```bash
python backend/admin_setup.py reset admin NewPassword123!
```

### List All Users
```bash
python backend/admin_setup.py list
```

### Create Authenticated Session
```bash
TOKEN="eyJhbGc..."
curl -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"topic":"Line 1 Delays"}'
```

---

## 🏃 Production Checklist

- [ ] Change SECRET_KEY environment variable
- [ ] Change all default passwords
- [ ] Use PostgreSQL instead of SQLite
- [ ] Enable HTTPS
- [ ] Restrict CORS origins
- [ ] Review security settings
- [ ] Enable audit logging
- [ ] Test with real users

---

## 🔧 Environment Variables

```bash
# JWT Security (CHANGE THESE IN PRODUCTION!)
export SECRET_KEY="your-secret-key-here"
export ADMIN_SETUP_KEY="different-secret-key"

# Database
export DATABASE_URL="postgresql://user:pass@localhost/db"

# Server
export PORT=8000
export DEBUG=false
```

---

## 📖 Interactive Documentation

Visit `http://localhost:8000/docs` for:
- ✅ All endpoints with parameters
- ✅ Real-time testing
- ✅ Request/response examples
- ✅ Error codes and meanings

---

## 🎯 What You Have Now

✅ User registration & login
✅ JWT token authentication
✅ Role-based access control
✅ Secure password hashing
✅ Input validation
✅ Default admin credentials
✅ Protected API routes
✅ Session linking to users
✅ Complete documentation
✅ Admin management tools

---

## 💡 Pro Tips

1. **Test with Swagger UI** - Visit `/docs` for interactive testing
2. **Save tokens** - Reuse tokens within 30-minute window
3. **Check headers** - Send `Authorization: Bearer {token}`
4. **Watch for 403** - Means you don't have permission (not admin)
5. **Watch for 401** - Means token is invalid or missing

---

## 🚀 Ready to Go!

Everything is implemented and ready to use. Follow the Quick Start above to begin!

For in-depth information, see the documentation files listed above.

---

**Questions?** Check `backend/AUTHENTICATION.md` for comprehensive docs.
