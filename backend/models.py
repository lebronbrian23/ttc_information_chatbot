"""
SQLAlchemy models for session, conversation, and authentication storage.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer, Float, Boolean, Enum
from sqlalchemy.orm import relationship
from backend.database import Base
import enum


class Session(Base):
    """
    Represents a user conversation session.
    Multiple messages belong to one session.
    """
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)  # Link to authenticated user
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Conversation metadata
    topic = Column(String(255), nullable=True)  # e.g., "Line 1 delays"
    feedback_score = Column(Integer, nullable=True)  # User rating 1-5
    
    # Relationships
    user = relationship("User", backref="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "topic": self.topic,
            "feedback_score": self.feedback_score,
            "message_count": len(self.messages),
        }


class Message(Base):
    """
    Represents a single message in a conversation.
    Stores both user and bot messages with metadata.
    """
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    
    # Message content
    role = Column(String(10), nullable=False)  # "user" or "bot"
    content = Column(Text, nullable=False)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # ML-related metadata (for bot messages)
    ml_used = Column(Boolean, default=False)  # Was ML predictor used?
    ml_model_version = Column(String(50), nullable=True)  # Model version used
    prediction_data = Column(Text, nullable=True)  # JSON string of prediction result
    
    # Extracted entities (for user messages)
    extracted_line = Column(String(50), nullable=True)
    extracted_station = Column(String(255), nullable=True)
    extracted_time = Column(String(50), nullable=True)
    extracted_day = Column(String(20), nullable=True)
    
    # Confidence/quality metrics
    confidence_score = Column(Float, nullable=True)  # 0.0-1.0
    intent = Column(String(50), nullable=True)  # e.g., "delay_query", "general_question"
    
    # Relationship
    session = relationship("Session", back_populates="messages")
    
    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "ml_used": self.ml_used,
            "ml_model_version": self.ml_model_version,
            "extracted_line": self.extracted_line,
            "extracted_station": self.extracted_station,
            "extracted_time": self.extracted_time,
            "extracted_day": self.extracted_day,
            "confidence_score": self.confidence_score,
            "intent": self.intent,
        }


class UserRole(str, enum.Enum):
    """User role enumeration."""
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    GUEST = "guest"


class User(Base):
    """
    Represents a system user with authentication credentials.
    """
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False, index=True)
    
    # Status tracking
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_login = Column(DateTime, nullable=True)
    
    # Metadata
    full_name = Column(String(255), nullable=True)
    permissions = Column(Text, nullable=True)  # JSON list of custom permissions
    
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "full_name": self.full_name,
            "created_at": self.created_at.isoformat(),
        }


class Permission(Base):
    """
    Represents a system permission that can be assigned to roles.
    """
    __tablename__ = "permissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), unique=True, nullable=False, index=True)  # e.g., "chat:create", "sessions:read"
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }
