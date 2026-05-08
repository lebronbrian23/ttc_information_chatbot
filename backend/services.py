"""
Database operations and session management.
CRUD operations for sessions and messages.
"""

import json
from typing import Optional, List
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc
from backend.models import Session, Message
from datetime import datetime


class SessionService:
    """Service for managing sessions."""
    
    @staticmethod
    def create_session(user_id: Optional[str] = None, topic: Optional[str] = None) -> Session:
        """Create a new session."""
        db = next(_get_db_session())
        try:
            session = Session(user_id=user_id, topic=topic)
            db.add(session)
            db.commit()
            db.refresh(session)
            return session
        finally:
            db.close()
    
    @staticmethod
    def get_session(session_id: str, db: DBSession) -> Optional[Session]:
        """Retrieve a session by ID."""
        return db.query(Session).filter(Session.id == session_id).first()
    
    @staticmethod
    def get_or_create_session(session_id: Optional[str], db: DBSession) -> Session:
        """Get existing session or create new one."""
        if session_id:
            session = SessionService.get_session(session_id, db)
            if session:
                return session
        # Create new session if not found
        new_session = Session()
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session
    
    @staticmethod
    def list_sessions(user_id: Optional[str] = None, limit: int = 50, db: DBSession = None) -> List[Session]:
        """List sessions, optionally filtered by user_id."""
        if db is None:
            db = next(_get_db_session())
            close_db = True
        else:
            close_db = False
        
        try:
            query = db.query(Session).order_by(desc(Session.created_at))
            if user_id:
                query = query.filter(Session.user_id == user_id)
            return query.limit(limit).all()
        finally:
            if close_db:
                db.close()
    
    @staticmethod
    def update_session(session_id: str, topic: Optional[str] = None, 
                      feedback_score: Optional[int] = None, db: DBSession = None) -> Optional[Session]:
        """Update session metadata."""
        if db is None:
            db = next(_get_db_session())
            close_db = True
        else:
            close_db = False
        
        try:
            session = SessionService.get_session(session_id, db)
            if not session:
                return None
            if topic is not None:
                session.topic = topic
            if feedback_score is not None:
                session.feedback_score = feedback_score
            db.commit()
            db.refresh(session)
            return session
        finally:
            if close_db:
                db.close()
    
    @staticmethod
    def get_session_context(session_id: str, db: DBSession) -> dict:
        """Get conversation context from session history."""
        session = SessionService.get_session(session_id, db)
        if not session:
            return {}
        
        # Build context from recent messages
        recent_messages = db.query(Message).filter(
            Message.session_id == session_id
        ).order_by(desc(Message.created_at)).limit(5).all()
        
        context = {
            "session_id": session_id,
            "session_created": session.created_at.isoformat(),
            "topic": session.topic,
            "recent_entities": {},
        }
        
        # Extract most recent entities for context
        for msg in reversed(recent_messages):
            if msg.extracted_line and "line" not in context["recent_entities"]:
                context["recent_entities"]["line"] = msg.extracted_line
            if msg.extracted_station and "station" not in context["recent_entities"]:
                context["recent_entities"]["station"] = msg.extracted_station
            if msg.extracted_day and "day" not in context["recent_entities"]:
                context["recent_entities"]["day"] = msg.extracted_day
        
        return context


class MessageService:
    """Service for managing messages."""
    
    @staticmethod
    def add_user_message(session_id: str, content: str, db: DBSession,
                        extracted_line: Optional[str] = None,
                        extracted_station: Optional[str] = None,
                        extracted_time: Optional[str] = None,
                        extracted_day: Optional[str] = None,
                        intent: Optional[str] = None,
                        confidence_score: Optional[float] = None) -> Message:
        """Add a user message to the session."""
        message = Message(
            session_id=session_id,
            role="user",
            content=content,
            extracted_line=extracted_line,
            extracted_station=extracted_station,
            extracted_time=extracted_time,
            extracted_day=extracted_day,
            intent=intent,
            confidence_score=confidence_score,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message
    
    @staticmethod
    def add_bot_message(session_id: str, content: str, db: DBSession,
                       ml_used: bool = False,
                       ml_model_version: Optional[str] = None,
                       prediction_data: Optional[dict] = None) -> Message:
        """Add a bot message to the session."""
        message = Message(
            session_id=session_id,
            role="bot",
            content=content,
            ml_used=ml_used,
            ml_model_version=ml_model_version,
            prediction_data=json.dumps(prediction_data) if prediction_data else None,
        )
        db.add(message)
        
        # Update session's updated_at timestamp
        session = SessionService.get_session(session_id, db)
        if session:
            session.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(message)
        return message
    
    @staticmethod
    def get_session_messages(session_id: str, db: DBSession, limit: int = 100) -> List[Message]:
        """Get all messages in a session."""
        return db.query(Message).filter(
            Message.session_id == session_id
        ).order_by(Message.created_at).limit(limit).all()
    
    @staticmethod
    def get_message(message_id: str, db: DBSession) -> Optional[Message]:
        """Retrieve a message by ID."""
        return db.query(Message).filter(Message.id == message_id).first()


# Helper for database session injection outside of FastAPI context
def _get_db_session():
    """Get database session (internal use)."""
    from backend.database import SessionLocal
    db = SessionLocal()
    yield db
    db.close()
