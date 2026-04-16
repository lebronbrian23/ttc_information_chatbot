"""
Comprehensive tests for database implementation.
Tests session/message storage, CRUD operations, and chat integration.
"""

import pytest
import json
from datetime import datetime
from backend.models import Session, Message
from backend.services import SessionService, MessageService


class TestSessionModel:
    """Test Session model and basic operations."""
    
    def test_session_creation(self, db_session):
        """Test creating a new session."""
        session = Session(user_id="user123", topic="Line 1 delays")
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        assert session.id is not None
        assert session.user_id == "user123"
        assert session.topic == "Line 1 delays"
        assert session.created_at is not None
        
    def test_session_to_dict(self, db_session):
        """Test session to_dict conversion."""
        session = Session(user_id="user123", topic="Test topic")
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        session_dict = session.to_dict()
        assert session_dict["user_id"] == "user123"
        assert session_dict["topic"] == "Test topic"
        assert "message_count" in session_dict


class TestMessageModel:
    """Test Message model and storage."""
    
    def test_message_creation(self, db_session):
        """Test creating a new message."""
        # Create session first
        session = Session(user_id="user123")
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        # Create message
        message = Message(
            session_id=session.id,
            role="user",
            content="Will Line 1 be delayed at 5pm?"
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)
        
        assert message.id is not None
        assert message.session_id == session.id
        assert message.role == "user"
        assert message.content == "Will Line 1 be delayed at 5pm?"
        
    def test_message_with_entities(self, db_session):
        """Test message with extracted entities."""
        session = Session()
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        message = Message(
            session_id=session.id,
            role="user",
            content="Line 1 at Bloor around 5pm Thursday",
            extracted_line="Line 1",
            extracted_station="BLOOR STATION",
            extracted_time="17:00",
            extracted_day="Thursday",
            intent="delay_query",
            confidence_score=0.95
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)
        
        assert message.extracted_line == "Line 1"
        assert message.extracted_station == "BLOOR STATION"
        assert message.extracted_time == "17:00"
        assert message.intent == "delay_query"
        assert message.confidence_score == 0.95
        
    def test_bot_message_with_prediction(self, db_session):
        """Test bot message with ML prediction data."""
        session = Session()
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        prediction_data = {
            "delayed": True,
            "delay_probability": 0.63,
            "predicted_duration_minutes": 7.2
        }
        
        message = Message(
            session_id=session.id,
            role="bot",
            content="There is a 63% chance of delays on Line 1...",
            ml_used=True,
            ml_model_version="v20260307_055529",
            prediction_data=json.dumps(prediction_data)
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)
        
        assert message.ml_used is True
        assert message.ml_model_version == "v20260307_055529"
        assert json.loads(message.prediction_data)["delay_probability"] == 0.63


class TestSessionService:
    """Test SessionService CRUD operations."""
    
    def test_create_session(self, db_session):
        """Test SessionService.create_session via direct instantiation."""
        session = Session(user_id="user456", topic="Test topic")
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        retrieved = SessionService.get_session(session.id, db_session)
        assert retrieved is not None
        assert retrieved.user_id == "user456"
        
    def test_get_or_create_session_existing(self, db_session):
        """Test get_or_create with existing session."""
        # Create a session
        session = Session(user_id="user789")
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        # Get existing session
        retrieved = SessionService.get_or_create_session(session.id, db_session)
        assert retrieved.id == session.id
        assert retrieved.user_id == "user789"
        
    def test_get_or_create_session_new(self, db_session):
        """Test get_or_create creates new session."""
        # Should create new session with None session_id
        session = SessionService.get_or_create_session(None, db_session)
        assert session.id is not None
        
    def test_list_sessions(self, db_session):
        """Test SessionService.list_sessions."""
        # Create multiple sessions
        for i in range(3):
            session = Session(user_id=f"user{i}")
            db_session.add(session)
        db_session.commit()
        
        # List all
        sessions = db_session.query(Session).all()
        assert len(sessions) >= 3
        
    def test_update_session(self, db_session):
        """Test SessionService.update_session."""
        session = Session(user_id="user999")
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        # Update
        updated = SessionService.update_session(
            session.id,
            topic="Updated topic",
            feedback_score=4,
            db=db_session
        )
        assert updated.topic == "Updated topic"
        assert updated.feedback_score == 4
        
    def test_get_session_context(self, db_session):
        """Test SessionService.get_session_context."""
        session = Session(user_id="user111")
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        # Add messages with entities
        msg1 = Message(
            session_id=session.id,
            role="user",
            content="Line 1",
            extracted_line="Line 1"
        )
        msg2 = Message(
            session_id=session.id,
            role="user",
            content="Bloor Station",
            extracted_station="BLOOR STATION"
        )
        db_session.add(msg1)
        db_session.add(msg2)
        db_session.commit()
        
        context = SessionService.get_session_context(session.id, db_session)
        assert context["session_id"] == session.id
        assert "recent_entities" in context


class TestMessageService:
    """Test MessageService operations."""
    
    def test_add_user_message(self, db_session):
        """Test MessageService.add_user_message."""
        session = Session()
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        message = MessageService.add_user_message(
            session_id=session.id,
            content="Will Line 2 be delayed?",
            db=db_session,
            extracted_line="Line 2",
            intent="delay_query",
            confidence_score=0.92
        )
        
        assert message.id is not None
        assert message.session_id == session.id
        assert message.role == "user"
        assert message.extracted_line == "Line 2"
        assert message.confidence_score == 0.92
        
    def test_add_bot_message(self, db_session):
        """Test MessageService.add_bot_message."""
        session = Session()
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        prediction = {"delayed": True, "probability": 0.75}
        message = MessageService.add_bot_message(
            session_id=session.id,
            content="Yes, Line 2 has a 75% chance of delays.",
            db=db_session,
            ml_used=True,
            ml_model_version="v20260310_000000",
            prediction_data=prediction
        )
        
        assert message.id is not None
        assert message.role == "bot"
        assert message.ml_used is True
        assert message.ml_model_version == "v20260310_000000"
        
    def test_get_session_messages(self, db_session):
        """Test MessageService.get_session_messages."""
        session = Session()
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        
        # Add multiple messages
        for i in range(3):
            msg = Message(
                session_id=session.id,
                role="user" if i % 2 == 0 else "bot",
                content=f"Message {i}"
            )
            db_session.add(msg)
        db_session.commit()
        
        messages = MessageService.get_session_messages(session.id, db_session)
        assert len(messages) == 3
        assert all(m.session_id == session.id for m in messages)


class TestChatIntegration:
    """Test chat endpoint with database integration."""
    
    def test_chat_creates_session(self, client):
        """Test that /chat creates a session in database."""
        response = client.post(
            "/chat",
            json={
                "message": "Will Line 1 be delayed?",
                "session_id": "test_session_123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "session_id" in data
        assert data["session_id"]
        
    def test_chat_with_context(self, client):
        """Test chat endpoint passes context correctly."""
        session_id = "test_context_session"
        
        # Send first message
        response1 = client.post(
            "/chat",
            json={
                "message": "What about Line 1?",
                "session_id": session_id
            }
        )
        assert response1.status_code == 200
        
        # Send follow-up message
        response2 = client.post(
            "/chat",
            json={
                "message": "What about delays at 5pm?",
                "session_id": session_id,
                "context": {"previous_line": "Line 1"}
            }
        )
        assert response2.status_code == 200


class TestSessionAPIEndpoints:
    """Test session management API endpoints."""
    
    def test_create_session_endpoint(self, client):
        """Test POST /api/sessions."""
        response = client.post(
            "/api/sessions",
            json={
                "user_id": "test_user_1",
                "topic": "Line 1 delays"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        # Session user_id is linked from auth context, not request payload.
        assert data["user_id"] is None
        assert data["topic"] == "Line 1 delays"
        
    def test_get_session_endpoint(self, client):
        """Test GET /api/sessions/{session_id}."""
        # Create a session first
        create_response = client.post(
            "/api/sessions",
            json={"user_id": "test_user_2", "topic": "Test"}
        )
        session_id = create_response.json()["id"]
        
        # Get it back
        get_response = client.get(f"/api/sessions/{session_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["id"] == session_id
        
    def test_list_sessions_endpoint(self, client):
        """Test GET /api/sessions."""
        # Create a session
        client.post(
            "/api/sessions",
            json={"user_id": "test_user_3"}
        )
        
        # List sessions
        response = client.get("/api/sessions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_update_session_endpoint(self, client):
        """Test PATCH /api/sessions/{session_id}."""
        # Create session
        create_response = client.post(
            "/api/sessions",
            json={"user_id": "test_user_4"}
        )
        session_id = create_response.json()["id"]
        
        # Update
        update_response = client.patch(
            f"/api/sessions/{session_id}",
            json={
                "topic": "Updated topic"
            }
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["topic"] == "Updated topic"
        assert data["feedback_score"] is None
        
    def test_submit_feedback_endpoint(self, client):
        """Test POST /api/sessions/{session_id}/feedback."""
        # Create session
        create_response = client.post(
            "/api/sessions",
            json={"user_id": "test_user_5"}
        )
        session_id = create_response.json()["id"]
        
        # Submit feedback
        feedback_response = client.post(
            f"/api/sessions/{session_id}/feedback",
            json={"feedback_score": 4, "feedback_text": "Good response"}
        )
        assert feedback_response.status_code == 200
        
    def test_get_messages_endpoint(self, client):
        """Test GET /api/sessions/{session_id}/messages."""
        # Create session with messages
        create_response = client.post(
            "/api/sessions",
            json={"user_id": "test_user_6"}
        )
        session_id = create_response.json()["id"]
        
        # Send chat messages (which saves to DB)
        client.post(
            "/chat",
            json={
                "message": "Test message",
                "session_id": session_id
            }
        )
        
        # Get messages
        messages_response = client.get(
            f"/api/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        data = messages_response.json()
        assert isinstance(data, list)
