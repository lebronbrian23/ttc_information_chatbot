# 🔧 Security Fixes - Implementation Guide

Quick fixes for all security issues found in the audit. **Estimated time: 2-3 hours for all fixes.**

---

## 🚨 CRITICAL FIXES (Do These First - 45 minutes total)

### Fix #1: Remove Weak Default SECRET_KEY (10 minutes)

**File:** `backend/auth.py`

Replace:
```python
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
```

With:
```python
SECRET_KEY = os.getenv("SECRET_KEY")

# FAIL LOUDLY if SECRET_KEY not set
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise ValueError(
        "🚨 FATAL ERROR: SECRET_KEY not properly configured!\n\n"
        "This is a critical security issue. The app will not start.\n\n"
        "Fix:\n"
        "1. Generate a secure key:\n"
        "   python -c \"import secrets; print(secrets.token_urlsafe(32))\"\n\n"
        "2. Set the environment variable:\n"
        "   export SECRET_KEY='<paste-generated-key-here>'\n\n"
        "3. Restart the application\n"
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
```

---

### Fix #2: Fix CORS Configuration (15 minutes)

**File:** `main.py`

Replace:
```python
# CORS - update origins before production deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # TODO: restrict to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

With:
```python
# ============================================================================
# CORS Configuration - SECURITY CRITICAL
# ============================================================================
import os

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Define allowed origins
if ENVIRONMENT == "production":
    # In production, ONLY allow your specific domains
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
    if not ALLOWED_ORIGINS or ALLOWED_ORIGINS == [""]:
        raise ValueError(
            "FATAL: ALLOWED_ORIGINS not set in production! "
            "Set env var: export ALLOWED_ORIGINS='https://yourdomain.com,https://www.yourdomain.com'"
        )
else:
    # Development: allow localhost
    ALLOWED_ORIGINS = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000"]

log.info(f"CORS Allowed Origins: {ALLOWED_ORIGINS}")

# Apply CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,          # Specific domains only
    allow_credentials=False,                # Don't allow credentials with wildcard
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,                           # Cache preflight requests
)
```

---

### Fix #3: Remove Default Credentials from Code (20 minutes)

**Files:** `backend/auth.py`, `backend/admin_setup.py`, `backend/AUTHENTICATION.md`

**Step 1:** Update `backend/auth.py` line ~155

Replace:
```python
def setup_default_users(db: DBSession) -> None:
    """
    Set up default users and permissions on first run.
    
    Creates:
    - Admin user (changeme / changeme@example.com)
    - Permissions for all roles
    """
    # Check if users already exist
    if db.query(User).count() > 0:
        return
    
    # Create default admin
    admin = User(
        username="admin",
        email="admin@ttc-chatbot.local",
        hashed_password=hash_password("changeme"),
        # ... rest
```

With:
```python
def setup_default_users(db: DBSession) -> None:
    """
    Set up default users and permissions on first run.
    
    Creates demo users with SECURE random passwords from environment variables.
    ⚠️ IMPORTANT: Change these passwords immediately in production!
    """
    import secrets
    
    # Check if users already exist
    if db.query(User).count() > 0:
        return
    
    # Generate secure random passwords for demo users
    # In production, these should be set via environment variables
    admin_password = os.getenv("DEMO_ADMIN_PASSWORD", secrets.token_urlsafe(16))
    demo_password = os.getenv("DEMO_USER_PASSWORD", secrets.token_urlsafe(16))
    mod_password = os.getenv("DEMO_MOD_PASSWORD", secrets.token_urlsafe(16))
    
    print(f"\n⚠️ DEFAULT DEMO CREDENTIALS (Change Immediately in Production!):")
    print(f"   admin   / {admin_password}")
    print(f"   demo    / {demo_password}")
    print(f"   moderator / {mod_password}\n")
    
    # Create default admin
    admin = User(
        username="admin",
        email="admin@ttc-chatbot.local",
        hashed_password=hash_password(admin_password),
        # ... rest
```

**Step 2:** Update `backend/admin_setup.py` documentation

Replace all references to hardcoded passwords with environment variables.

**Step 3:** Update `backend/AUTHENTICATION.md`

Replace "Password: changeme" examples with "See output of `python main.py` on first run"

---

## 🔴 HIGH PRIORITY FIXES (2-3 hours)

### Fix #4: Add Rate Limiting to Login (30 minutes)

**Step 1:** Add dependency

```bash
pip install slowapi>=0.1.9
```

**Step 2:** Create rate limiter

**File:** `backend/rate_limits.py` (new file)

```python
"""
Rate limiting configuration for security endpoints.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/day", "10/minute"],
    storage_uri="memory://",  # Use Redis in production
)

@limiter.error_handler
async def rate_limit_error_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Too many requests. Please try again later."
        },
    )
```

**Step 3:** Apply to auth routes

**File:** `backend/auth_routes.py`

Add import at top:
```python
from backend.rate_limits import limiter
```

Add decorator to login endpoint:
```python
@router.post(
    "/login",
    response_model=TokenResponse,
)
@limiter.limit("5/minute")  # Max 5 login attempts per minute
async def login(
    request: Request,  # Add this parameter
    login_request: UserLoginRequest = Body(...),
    db: DBSession = Depends(get_db),
):
    # ... existing code
```

---

### Fix #5: Add Account Lockout (45 minutes)

**Step 1:** Update User model

**File:** `backend/models.py` - Update User class:

```python
from sqlalchemy import Integer, DateTime

class User(Base):
    __tablename__ = "users"
    
    # ... existing fields ...
    
    # Security fields
    login_attempts = Column(Integer, default=0, index=True)
    lockout_until = Column(DateTime, nullable=True, index=True)
```

**Step 2:** Update authenticate_user function

**File:** `backend/auth.py`

Replace:
```python
def authenticate_user(username: str, password: str, db: DBSession) -> Optional[User]:
    """
    Authenticate a user by username and password.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    if not user.is_active:
        return None
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user
```

With:
```python
def authenticate_user(username: str, password: str, db: DBSession) -> Optional[User]:
    """
    Authenticate a user by username and password.
    Implements account lockout after 5 failed attempts.
    """
    user = db.query(User).filter(User.username == username).first()
    
    # Check account lockout FIRST
    if user and user.lockout_until:
        if user.lockout_until > datetime.utcnow():
            minutes_remaining = (user.lockout_until - datetime.utcnow()).seconds // 60
            raise ValueError(f"Account locked. Try again in {minutes_remaining} minutes.")
        else:
            # Unlock account
            user.login_attempts = 0
            user.lockout_until = None
            db.commit()
    
    # Dummy user to prevent timing attacks
    if not user:
        dummy_hash = pwd_context.hash("dummy-for-timing")
        pwd_context.verify(password, dummy_hash)
        return None
    
    # Verify password
    if not verify_password(password, user.hashed_password):
        # Increment failed attempts
        user.login_attempts += 1
        
        # Lock after 5 failed attempts
        if user.login_attempts >= 5:
            user.lockout_until = datetime.utcnow() + timedelta(minutes=15)
            db.commit()
            raise ValueError("Too many failed attempts. Account locked for 15 minutes.")
        
        db.commit()
        return None
    
    # Successful login - reset failed attempts
    if not user.is_active:
        return None
    
    user.login_attempts = 0
    user.lockout_until = None
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user
```

**Step 3:** Update login endpoint to handle lockout errors

**File:** `backend/auth_routes.py`

```python
@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    request_data: UserLoginRequest,
    db: DBSession = Depends(get_db),
):
    try:
        user = authenticate_user(request_data.username, request_data.password, db)
    except ValueError as e:
        # Account locked or other validation error
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # ... rest of login logic
```

---

### Fix #6: Add Audit Logging (60 minutes)

**Step 1:** Create audit logger

**File:** `backend/audit_log.py` (new file)

```python
"""
Security audit logging for tracking authentication and authorization events.
"""

import logging
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path

class SecurityEvent(str, Enum):
    """Security-relevant events to log."""
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    ADMIN_CREATED = "ADMIN_CREATED"
    PASSWORD_RESET = "PASSWORD_RESET"
    UNAUTHORIZED_ACCESS_ATTEMPT = "UNAUTHORIZED_ACCESS_ATTEMPT"

# Create logs directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Configure audit logger
audit_logger = logging.getLogger("security_audit")
audit_logger.setLevel(logging.INFO)

# File handler
file_handler = logging.FileHandler(LOG_DIR / "security_audit.log")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
audit_logger.addHandler(file_handler)

# Console handler (for development)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.WARNING)
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)
audit_logger.addHandler(console_handler)

def log_audit_event(
    event: SecurityEvent,
    user: str = "unknown",
    details: dict = None,
    severity: str = "INFO"
) -> None:
    """
    Log a security-relevant event.
    
    Args:
        event: SecurityEvent enum value
        user: Username or identifier
        details: Additional context (dict)
        severity: Log level (INFO, WARNING, ERROR)
    """
    import json
    
    detail_str = json.dumps(details) if details else "{}"
    message = f"event={event.value} | user={user} | details={detail_str}"
    
    if severity == "ERROR":
        audit_logger.error(message)
    elif severity == "WARNING":
        audit_logger.warning(message)
    else:
        audit_logger.info(message)
```

**Step 2:** Integrate into auth_routes.py

Add import:
```python
from backend.audit_log import log_audit_event, SecurityEvent
```

Add logging to login:
```python
@router.post("/login")
async def login(request: UserLoginRequest, db: DBSession = Depends(get_db)):
    try:
        user = authenticate_user(request.username, request.password, db)
    except ValueError as e:
        # Account locked
        log_audit_event(
            SecurityEvent.ACCOUNT_LOCKED,
            request.username,
            {"reason": str(e)},
            severity="WARNING"
        )
        raise HTTPException(status_code=429, detail=str(e))
    
    if not user:
        log_audit_event(
            SecurityEvent.LOGIN_FAILURE,
            request.username,
            {"reason": "invalid_credentials"}
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    log_audit_event(
        SecurityEvent.LOGIN_SUCCESS,
        user.username,
        {"user_id": user.id}
    )
    
    # Generate token and return...
```

---

## 🟡 MEDIUM PRIORITY FIXES (1 hour)

### Fix #7 & #8: Add Security Headers (20 minutes)

**File:** `main.py`

Add after CORS middleware:
```python
# ============================================================================
# Security Headers
# ============================================================================

@app.middleware("http")
async def add_security_headers(request, call_next):
    """Add important security headers to all responses."""
    response = await call_next(request)
    
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # Prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # XSS Protection
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Referrer Policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Permissions Policy (formerly Feature Policy)
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # HSTS (only in production)
    if ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
    
    return response
```

---

### Fix #9: Add HTTPS Enforcement (20 minutes)

**File:** `main.py`

Add import:
```python
from fastapi.middleware.redirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
```

Add after app creation, before CORS:
```python
if ENVIRONMENT == "production":
    # Redirect HTTP to HTTPS
    app.add_middleware(HTTPSRedirectMiddleware)
    
    # Verify trusted hosts
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv(
            "TRUSTED_HOSTS",
            "yourdomain.com,www.yourdomain.com"
        ).split(",")
    )
```

---

### Fix #10: Add UUID Validation (10 minutes)

**File:** `backend/routes.py`

Add import at top:
```python
import uuid
from fastapi import HTTPException, status

def validate_uuid(session_id: str) -> str:
    """Validate that session_id is a valid UUID."""
    try:
        uuid.UUID(session_id)
        return session_id
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format. Must be a valid UUID."
        )
```

Use in routes:
```python
@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str = Depends(validate_uuid),  # Add this
    db: DBSession = Depends(get_db),
    current_user: Optional[TokenData] = None,
):
    # ... rest of code
```

---

## Testing Your Fixes

After implementing all fixes, run these tests:

```bash
# Test 1: SECRET_KEY enforcement
unset SECRET_KEY
python main.py 2>&1 | grep -i "fatal\|error"
# Should fail with error

export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
python main.py
# Should start successfully

# Test 2: CORS verification  
curl -v -H "Origin: attacker.com" http://localhost:8000/api/auth/login 2>&1 | grep -i "access-control"
# Should NOT have Access-Control-Allow-Origin header

# Test 3: Rate limiting
for i in {1..10}; do
  curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"test","password":"test"}' | grep -o "429\|401"
done
# Should get 429 after 5 attempts

# Test 4: Security headers
curl -I http://localhost:8000/docs | grep -E "X-Frame|X-Content|Referrer"
# Should show security headers

# Test 5: Check audit log
tail -f logs/security_audit.log
# Should show LOGIN_FAILURE events
```

---

## Estimated Implementation Time

| Fix | Difficulty | Time |
|-----|-----------|------|
| #1 - SECRET_KEY | Easy | 10 min |
| #2 - CORS | Easy | 15 min |
| #3 - Credentials | Medium | 20 min |
| #4 - Rate Limiting | Medium | 30 min |
| #5 - Account Lockout | Hard | 45 min |
| #6 - Audit Logging | Medium | 60 min |
| #7 - Security Headers | Easy | 20 min |
| #8 - HTTPS | Easy | 20 min |
| #9 - UUID Validation | Easy | 10 min |
| **TOTAL** | | **220 min (3.5 hrs)** |

---

## Deployment Verification Checklist

Before deploying to production:

```
Security Fixes:
[ ] SECRET_KEY is set and not using default
[ ] CORS is configured for specific domains only
[ ] No hardcoded default credentials in code
[ ] Rate limiting enabled on /login endpoint
[ ] Account lockout working (5 attempts = 15 min lock)
[ ] Audit logging to logs/security_audit.log
[ ] Security headers present (X-Frame-Options, etc.)
[ ] HTTPS redirect enabled
[ ] UUID validation on all ID parameters

Production Environment:
[ ] DATABASE_URL set (not SQLite)
[ ] ENVIRONMENT set to "production"
[ ] ALLOWED_ORIGINS configured for your domain
[ ] TRUSTED_HOSTS configured
[ ] SECRET_KEY is 32+ characters
[ ] ADMIN_PASSWORD set to unique value
[ ] All demo passwords changed
[ ] HTTPS certificates installed
[ ] .env file configured and secured
[ ] logs/ directory exists and writable
```

---

**Ready to implement these fixes? Start with Fix #1 (SECRET_KEY) - it's critical!**

Questions? See `SECURITY_AUDIT_REPORT.md` for detailed explanations.
