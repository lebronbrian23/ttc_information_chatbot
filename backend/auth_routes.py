"""
Authentication routes for user registration, login, and token management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session as DBSession
from datetime import timedelta

from backend.database import get_db
from backend.auth import (
    authenticate_user,
    create_access_token,
    hash_password,
    get_current_user,
    decode_token,
    setup_default_users,
    TokenData,
)
from backend.models import User, UserRole
from backend.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    ErrorResponse,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ============================================================================
# Registration & Login
# ============================================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input or user exists"},
        500: {"model": ErrorResponse, "description": "Server error"},
    },
)
async def register(
    request: UserRegisterRequest,
    db: DBSession = Depends(get_db),
):
    """
    Register a new user account.
    
    - **username**: Alphanumeric with underscore/hyphen, 3-255 chars
    - **email**: Valid email address
    - **password**: Min 8 chars, must contain uppercase, lowercase, digit, special char
    - **full_name**: Optional full name
    """
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.username == request.username) | (User.email == request.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )
    
    # Create new user
    user = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        role=UserRole.USER,
        is_active=True,
        is_verified=False,  # Email verification would go here
        full_name=request.full_name,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        403: {"model": ErrorResponse, "description": "Account inactive"},
    },
)
async def login(
    request: UserLoginRequest,
    db: DBSession = Depends(get_db),
):
    """
    Authenticate user and return JWT access token.
    
    - **username**: Registered username
    - **password**: User password
    
    Returns access token valid for 30 minutes.
    """
    # Authenticate user
    user = authenticate_user(request.username, request.password, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "role": user.role.value,
        }
    )
    
    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        username=user.username,
        role=user.role.value,
    )


# ============================================================================
# Token Refresh
# ============================================================================

@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
)
async def refresh_token(
    current_user: TokenData = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """
    Refresh an expired access token.
    
    Requires valid JWT token in Authorization header.
    Returns new token valid for another 30 minutes.
    """
    # Get full user record
    user = db.query(User).filter(User.id == current_user.user_id).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Create new access token
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "role": user.role.value,
        }
    )
    
    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        username=user.username,
        role=user.role.value,
    )


# ============================================================================
# User Profile
# ============================================================================

@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
)
async def get_current_user_info(
    current_user: TokenData = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """
    Get current authenticated user's profile.
    
    Requires valid JWT token in Authorization header.
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return user


@router.put(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        400: {"model": ErrorResponse, "description": "Invalid update data"},
    },
)
async def update_user_profile(
    full_name: str = Query(None, max_length=255),
    current_user: TokenData = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """
    Update current user's profile information.
    
    Only full_name can be updated via this endpoint.
    For password changes, use /resetPassword endpoint.
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if full_name:
        user.full_name = full_name
        db.commit()
        db.refresh(user)
    
    return user


# ============================================================================
# Password Management (Future Enhancement)
# ============================================================================

@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    old_password: str = Query(...),
    new_password: str = Query(..., min_length=8),
    current_user: TokenData = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """
    Change the current user's password.
    
    - **old_password**: Current password for verification
    - **new_password**: New password (min 8 chars, must meet complexity requirements)
    """
    from backend.auth import verify_password
    
    user = db.query(User).filter(User.id == current_user.user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    # Verify old password
    if not verify_password(old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Old password is incorrect",
        )
    
    # Update password
    user.hashed_password = hash_password(new_password)
    db.commit()
    
    return {"detail": "Password updated successfully"}


# ============================================================================
# Admin Setup Endpoint
# ============================================================================

@router.post(
    "/setup-admin",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Admin already exists"},
        403: {"model": ErrorResponse, "description": "Invalid security key"},
    },
)
async def setup_admin(
    request: UserRegisterRequest,
    security_key: str = Query(...),
    db: DBSession = Depends(get_db),
):
    """
    Initialize default admin user (first run only).
    
    Security key must match ADMIN_SETUP_KEY environment variable.
    Only works if no admin users exist in the database.
    
    **IMPORTANT**: Change the default security key in production!
    Set ADMIN_SETUP_KEY environment variable.
    """
    import os
    
    admin_setup_key = os.getenv("ADMIN_SETUP_KEY", "change-me-in-production")
    
    # Verify security key
    if security_key != admin_setup_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid security key",
        )
    
    # Check if admin already exists
    existing_admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin user already exists",
        )
    
    # Create admin user
    admin = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
        full_name=request.full_name or "System Administrator",
    )
    
    db.add(admin)
    
    # Set up default users (demo user and moderator)
    setup_default_users(db)
    
    return admin


# ============================================================================
# Health Check with Auth
# ============================================================================

@router.get("/health")
async def auth_health():
    """Health check endpoint for auth service."""
    return {
        "status": "healthy",
        "service": "authentication",
        "endpoints": [
            "POST /register - Create new user",
            "POST /login - Login with credentials",
            "POST /refresh - Refresh access token",
            "GET /me - Get current user profile",
            "PUT /me - Update user profile",
            "POST /reset-password - Change password",
            "POST /setup-admin - Initialize admin (first run only)",
        ],
    }
