"""
Request/response schemas with input validation.
Uses Pydantic for data validation and serialization.
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List
from datetime import datetime
from backend.models import UserRole
import re


# ============================================================================
# User/Authentication Schemas
# ============================================================================

class UserRegisterRequest(BaseModel):
    """Schema for user registration."""
    username: str = Field(
        ...,
        min_length=3,
        max_length=255,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Username (alphanumeric, underscore, hyphen)"
    )
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=255,
        description="Password (min 8 chars, must contain upper, lower, digit, special)"
    )
    full_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Full name"
    )

    @validator("password")
    def validate_password_complexity(cls, v):
        """Ensure password meets complexity requirements."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserLoginRequest(BaseModel):
    """Schema for user login."""
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class TokenResponse(BaseModel):
    """Schema for authentication token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes in seconds
    user_id: str
    username: str
    role: str


class UserResponse(BaseModel):
    """Schema for user profile response."""
    id: str
    username: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


# ============================================================================
# Session/Message Schemas
# ============================================================================

class MessageCreateRequest(BaseModel):
    """Schema for creating a message."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Message content"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID (optional, creates new if not provided)"
    )

    @validator("message")
    def validate_message_content(cls, v):
        """Validate message content."""
        # Remove excessive whitespace
        v = v.strip()
        if len(v) == 0:
            raise ValueError("Message cannot be empty")
        if len(v) > 5000:
            raise ValueError("Message exceeds maximum length of 5000 characters")
        return v


class SessionCreateRequest(BaseModel):
    """Schema for creating a session."""
    topic: Optional[str] = Field(
        None,
        max_length=255,
        description="Session topic"
    )


class SessionFeedbackRequest(BaseModel):
    """Schema for session feedback."""
    feedback_score: int = Field(
        ...,
        ge=1,
        le=5,
        description="Feedback score 1-5"
    )
    feedback_text: Optional[str] = Field(
        None,
        max_length=2000,
        description="Optional feedback text"
    )

    @validator("feedback_text")
    def validate_feedback(cls, v):
        """Validate feedback text."""
        if v and len(v.strip()) == 0:
            raise ValueError("Feedback text cannot be empty or whitespace only")
        return v


class SessionUpdateRequest(BaseModel):
    """Schema for updating a session."""
    topic: Optional[str] = Field(
        None,
        max_length=255,
        description="Updated topic"
    )


class MessageResponse(BaseModel):
    """Schema for message response."""
    id: str
    session_id: str
    role: str
    content: str
    extracted_line: Optional[str]
    extracted_station: Optional[str]
    extracted_time: Optional[str]
    extracted_day: Optional[str]
    intent: Optional[str]
    confidence_score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    """Schema for session response."""
    id: str
    user_id: Optional[str]
    created_at: datetime
    topic: Optional[str]
    feedback_score: Optional[int]
    message_count: int = 0
    messages: Optional[List[MessageResponse]] = None

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Schema for session list response."""
    sessions: List[SessionResponse]
    total: int
    page: int
    page_size: int


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str
    timestamp: datetime
    database: str
    version: str = "1.0.0"


class ChatMessageRequest(BaseModel):
    """Schema for chat message request."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User message"
    )
    session_id: Optional[str] = Field(
        None,
        description="Optional session ID to continue conversation"
    )
    context_window: int = Field(
        5,
        ge=1,
        le=20,
        description="Number of previous messages to include in context"
    )

    @validator("message")
    def validate_message(cls, v):
        """Validate chat message."""
        v = v.strip()
        if len(v) == 0:
            raise ValueError("Message cannot be empty")
        if len(v) > 5000:
            raise ValueError("Message exceeds maximum length")
        return v


class ChatResponse(BaseModel):
    """Schema for chat response."""
    session_id: str
    user_message: str
    bot_response: str
    confidence: float
    line: Optional[str]
    station: Optional[str]
    time: Optional[str]
    day: Optional[str]
    model_used: str
    timestamp: datetime

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str
    detail: Optional[str]
    code: int


# ============================================================================
# Admin Schemas
# ============================================================================

class AdminInitRequest(BaseModel):
    """Schema for admin initialization."""
    security_key: str = Field(..., description="Security key for admin creation")
    username: str = Field(..., min_length=3, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=255)


class BulkUserCreateRequest(BaseModel):
    """Schema for bulk user creation."""
    users: List[UserRegisterRequest] = Field(..., max_items=100)


class PermissionResponse(BaseModel):
    """Schema for permission."""
    name: str
    description: Optional[str]

    class Config:
        from_attributes = True


# ============================================================================
# Validation Helpers
# ============================================================================

def validate_pagination(page: int = 1, page_size: int = 20) -> tuple:
    """
    Validate pagination parameters.
    
    Args:
        page: Page number (1-indexed)
        page_size: Items per page
    
    Returns:
        Tuple of (page, page_size) if valid
    
    Raises:
        ValueError: If parameters are invalid
    """
    if page < 1:
        raise ValueError("Page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise ValueError("Page size must be between 1 and 100")
    return page, page_size
