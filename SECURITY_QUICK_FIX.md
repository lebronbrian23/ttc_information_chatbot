# 🚀 Quick Security Fix Checklist

**Priority: CRITICAL → HIGH → MEDIUM**

---

## ⚡ CRITICAL FIXES (Do immediately - 45 minutes)

### ☐ Fix #1: SECRET_KEY Enforcement (10 min)
**File:** `backend/auth.py` line 17

**What:** Replace weak default with environment variable requirement
```python
# FROM: SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key...")
# TO: Fail if SECRET_KEY not set or too short
```
**Test:** `unset SECRET_KEY && python main.py` → Should error

---

### ☐ Fix #2: CORS Configuration (15 min)
**File:** `main.py` lines 137-144

**What:** Replace `allow_origins=["*"]` with specific domains
```python
# FROM: allow_origins=["*"], allow_credentials=True
# TO: allow_origins=["https://yourdomain.com"], allow_credentials=False
```
**Test:** `curl -H "Origin: attacker.com" http://localhost:8000/api/` → No CORS header

---

### ☐ Fix #3: Remove Hardcoded Credentials (20 min)
**Files:** `backend/auth.py`, `backend/admin_setup.py`

**What:** Change "changeme" / "demo123" to random generated passwords
```python
# FROM: admin_password = "changeme"
# TO: admin_password = os.getenv("DEMO_ADMIN_PASSWORD", secrets.token_urlsafe(16))
```
**Test:** Passwords printed to console on startup, not visible in code

---

## 🔴 HIGH PRIORITY FIXES (Do before production - 2-3 hours)

### ☐ Fix #4: Rate Limiting (30 min)
**Files:** Create `backend/rate_limits.py`, Update `backend/auth_routes.py`

**What:** Add `@limiter.limit("5/minute")` to login endpoint
```bash
pip install slowapi
```
**Test:** `for i in {1..10}; do curl -X POST /login; done` → 429 after 5

---

### ☐ Fix #5: Account Lockout (45 min)
**Files:** Update `backend/models.py` and `backend/auth.py`

**What:** Add `login_attempts`, `lockout_until` to User model, lock after 5 fails
**Test:** 5 failed logins → Account locked for 15 minutes

---

### ☐ Fix #6: Audit Logging (60 min)
**Files:** Create `backend/audit_log.py`, Update `backend/auth_routes.py`

**What:** Log all auth events (LOGIN_SUCCESS, LOGIN_FAILURE, etc.) to `logs/security_audit.log`
**Test:** `tail logs/security_audit.log` → See login attempts logged

---

## 🟡 MEDIUM PRIORITY FIXES (Nice to have - 1 hour)

### ☐ Fix #7: Security Headers (20 min)
**File:** `main.py` - Add middleware after CORS
```python
response.headers["X-Frame-Options"] = "DENY"
response.headers["X-Content-Type-Options"] = "nosniff"
response.headers["Strict-Transport-Security"] = "max-age=31536000"
```
**Test:** `curl -I http://localhost:8000` → See security headers

---

### ☐ Fix #8: HTTPS Enforcement (20 min)
**File:** `main.py` - Add middleware in production
```python
if ENVIRONMENT == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
```

---

### ☐ Fix #9: UUID Validation (10 min)
**File:** `backend/routes.py` - Validate session_id format before database query

---

## 📋 Environment Variables Setup

Add to `.env` file:
```bash
# CRITICAL
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
ENVIRONMENT=production
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# HIGH Priority
DEMO_ADMIN_PASSWORD=<new secure password>
DEMO_USER_PASSWORD=<new secure password>
DEMO_MOD_PASSWORD=<new secure password>

# MEDIUM Priority  
TRUSTED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=postgresql://user:password@localhost/dbname
```

---

## 🧪 Pre-Production Testing (30 minutes)

```bash
# Generate SECRET_KEY
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Start app
python main.py

# Test rate limiting - should get 429 after 5 attempts
for i in {1..7}; do
  echo "Attempt $i:"
  curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"wrong"}' | jq .detail
done

# Test CORS - should NOT have Access-Control headers
curl -v -H "Origin: attacker.com" http://localhost:8000/api/auth/profile 2>&1 | grep -i "access-control"

# Test security headers
curl -I http://localhost:8000/docs | grep -E "X-Frame|X-Content|Strict-Transport"

# Check audit log
cat logs/security_audit.log | tail -20
```

---

## 📊 Summary

| Fix | Time | Severity |
|-----|------|----------|
| SECRET_KEY | 10m | 🚨 CRITICAL |
| CORS | 15m | 🚨 CRITICAL |
| Credentials | 20m | 🚨 CRITICAL |
| Rate Limiting | 30m | 🔴 HIGH |
| Account Lockout | 45m | 🔴 HIGH |
| Audit Logging | 60m | 🔴 HIGH |
| Security Headers | 20m | 🟡 MEDIUM |
| HTTPS | 20m | 🟡 MEDIUM |
| UUID Validation | 10m | 🟡 MEDIUM |
| **TOTAL** | **230m** | |

---

## ✅ Pre-Deployment Verification

Before going to production, verify:
- [ ] SECRET_KEY is set and 32+ characters
- [ ] CORS only allows your domain
- [ ] No hardcoded passwords in code
- [ ] Rate limiting responds with 429
- [ ] Failed logins lock account after 5 attempts
- [ ] Audit log file exists and has entries
- [ ] Security headers present on all responses
- [ ] HTTPS redirect enabled
- [ ] UUID validation prevents bad IDs

---

**💡 Pro Tip:** Do CRITICAL fixes first (45 min), then test thoroughly before doing HIGH/MEDIUM fixes.

**📖 Reference:** See `SECURITY_FIXES_GUIDE.md` for detailed implementation code.
