"""
Authentication and authorization module.
Handles JWT tokens, password hashing, and role-based access control.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session as DBSession
from backend.models import User, UserRole
from functools import wraps
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
# Use pbkdf2_sha256 as the primary scheme for local/dev stability.
# Keep bcrypt as a fallback so existing bcrypt hashes can still be verified.
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


class TokenData:
    """JWT token payload data."""
    def __init__(self, username: str, role: str, user_id: str):
        self.username = username
        self.role = role
        self.user_id = user_id


# ============================================================================
# Password Management
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================================
# JWT Token Management
# ============================================================================

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary with token claims (username, role, user_id, etc.)
        expires_delta: Optional custom expiration time
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        TokenData with claims or None if invalid
    
    Raises:
        JWTError: If token is invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        user_id: str = payload.get("user_id")
        
        if username is None:
            return None
        
        return TokenData(username=username, role=role, user_id=user_id)
    except JWTError:
        return None


# ============================================================================
# Authentication Functions
# ============================================================================

def authenticate_user(username: str, password: str, db: DBSession) -> Optional[User]:
    """
    Authenticate a user by username and password.
    
    Args:
        username: Username to authenticate
        password: Plain password to verify
        db: Database session
    
    Returns:
        User object if authentication successful, None otherwise
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None

    # Account status checks are handled by the login route so we can
    # return field-scoped vs form-scoped errors accurately.
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """
    Get current authenticated user from JWT token.
    
    Use as FastAPI dependency:
        @app.get("/protected")
        async def protected(user: TokenData = Depends(get_current_user)):
            pass
    """
    token = credentials.credentials
    token_data = decode_token(token)
    
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_data


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
) -> Optional[TokenData]:
    """Get current user if a valid token is provided, otherwise return None."""
    if credentials is None:
        return None

    token_data = decode_token(credentials.credentials)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


# ============================================================================
# Role-Based Access Control
# ============================================================================

ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        "users:create",
        "users:read",
        "users:update",
        "users:delete",
        "sessions:read:all",
        "sessions:delete:all",
        "chat:access",
        "messages:read:all",
        "admin:access",
    ],
    UserRole.MODERATOR: [
        "users:read",
        "sessions:read:all",
        "sessions:delete:all",
        "chat:access",
        "messages:read:all",
    ],
    UserRole.USER: [
        "sessions:read:own",
        "sessions:update:own",
        "chat:access",
        "messages:read:own",
        "feedback:create",
    ],
    UserRole.GUEST: [
        "chat:access",
        "sessions:create",
    ],
}


def require_role(*allowed_roles: UserRole):
    """
    Decorator to require specific roles.
    
    Use:
        @require_role(UserRole.ADMIN, UserRole.MODERATOR)
        def admin_route(current_user: User = Depends(get_current_user)):
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: Optional[User] = None, **kwargs):
            if current_user is None or current_user.role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}",
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator


def require_permission(*permissions: str):
    """
    Decorator to require specific permissions.
    
    Use:
        @require_permission("sessions:read:all")
        def read_all_sessions(current_user: User = Depends(get_current_user)):
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: Optional[User] = None, **kwargs):
            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )
            
            user_perms = ROLE_PERMISSIONS.get(current_user.role, [])
            if not any(perm in user_perms for perm in permissions):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied. Required: {permissions}",
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator


def check_permission(user: User, permission: str) -> bool:
    """Check if user has a specific permission."""
    user_perms = ROLE_PERMISSIONS.get(user.role, [])
    return permission in user_perms


def can_access_session(user: User, session_id: str, db: DBSession, read_only: bool = True) -> bool:
    """
    Check if user can access a specific session.
    
    Admins and moderators can access all sessions.
    Users can only access their own sessions.
    """
    if user.role in [UserRole.ADMIN, UserRole.MODERATOR]:
        return True
    
    from backend.models import Session
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        return False
    
    # User can access if they own the session or if user_id matches
    return session.user_id == user.username or session.user_id == user.id


# ============================================================================
# Admin Credential Setup
# ============================================================================

def create_default_admin(username: str, email: str, password: str, db: DBSession) -> User:
    """
    Create default admin user if it doesn't exist.
    
    Args:
        username: Admin username
        email: Admin email
        password: Admin password (will be hashed)
        db: Database session
    
    Returns:
        Created or existing admin user
    """
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return existing
    
    admin = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
        full_name="System Administrator",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


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
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
        full_name="System Administrator",
    )
    db.add(admin)
    
    # Create demo user
    demo_user = User(
        username="demo",
        email="demo@ttc-chatbot.local",
        hashed_password=hash_password("demo123"),
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
        full_name="Demo User",
    )
    db.add(demo_user)
    
    # Create demo moderator
    moderator = User(
        username="moderator",
        email="moderator@ttc-chatbot.local",
        hashed_password=hash_password("mod123"),
        role=UserRole.MODERATOR,
        is_active=True,
        is_verified=True,
        full_name="Moderator User",
    )
    db.add(moderator)
    
    db.commit()
