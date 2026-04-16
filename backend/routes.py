"""
Backend routes for session and conversation management.
Includes optional authentication for accessing user sessions.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from backend.database import get_db
from backend.services import SessionService, MessageService
from backend.models import Session, Message, User, UserRole
from backend.schemas import (
    SessionResponse,
    MessageResponse,
    SessionCreateRequest,
    SessionUpdateRequest,
    SessionFeedbackRequest,
)
from backend.auth import (
    get_current_user_optional,
    TokenData,
    check_permission,
)

router = APIRouter(prefix="/api", tags=["sessions"])


# ============================================================================
# Session Endpoints
# ============================================================================

@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    request: SessionCreateRequest,
    db: DBSession = Depends(get_db),
    current_user: Optional[TokenData] = Depends(get_current_user_optional),
):
    """
    Create a new conversation session.
    
    Optional: Provide JWT token to link session to authenticated user.
    """
    session = Session(
        user_id=current_user.user_id if current_user else None,
        topic=request.topic,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        topic=session.topic,
        feedback_score=session.feedback_score,
        message_count=len(session.messages),
    )


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
)
async def get_session(
    session_id: str,
    db: DBSession = Depends(get_db),
    current_user: Optional[TokenData] = Depends(get_current_user_optional),
):
    """
    Get session details.
    
    If authenticated, can only access own sessions unless admin.
    """
    session = SessionService.get_session(session_id, db)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    # Check access permissions
    if current_user:
        user_db = db.query(User).filter(User.id == current_user.user_id).first()
        if user_db and user_db.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            if session.user_id != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot access other users' sessions",
                )
    
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        topic=session.topic,
        feedback_score=session.feedback_score,
        message_count=len(session.messages),
    )


@router.get(
    "/sessions",
    response_model=List[SessionResponse],
)
async def list_sessions(
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: DBSession = Depends(get_db),
    current_user: Optional[TokenData] = Depends(get_current_user_optional),
):
    """
    List sessions.
    
    - If authenticated: Returns your sessions (admins see all)
    - If not authenticated: Returns all public sessions
    """
    # Determine which sessions to return
    if current_user:
        user_db = db.query(User).filter(User.id == current_user.user_id).first()
        if user_db and user_db.role in [UserRole.ADMIN, UserRole.MODERATOR]:
            # Admins and moderators can see all sessions
            sessions = SessionService.list_sessions(user_id=user_id, limit=limit, db=db)
        else:
            # Regular users only see their own
            sessions = SessionService.list_sessions(user_id=current_user.user_id, limit=limit, db=db)
    else:
        # Unauthenticated users see all (or filtered by user_id if specified)
        sessions = SessionService.list_sessions(user_id=user_id, limit=limit, db=db)
    
    return [
        SessionResponse(
            id=s.id,
            user_id=s.user_id,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
            topic=s.topic,
            feedback_score=s.feedback_score,
            message_count=len(s.messages),
        )
        for s in sessions
    ]


@router.patch(
    "/sessions/{session_id}",
    response_model=SessionResponse,
)
async def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    db: DBSession = Depends(get_db),
    current_user: Optional[TokenData] = Depends(get_current_user_optional),
):
    """
    Update session metadata.
    
    If authenticated, can only update own sessions unless admin.
    """
    session = SessionService.get_session(session_id, db)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    # Check access permissions
    if current_user:
        user_db = db.query(User).filter(User.id == current_user.user_id).first()
        if user_db and user_db.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            if session.user_id != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot update other users' sessions",
                )
    
    updated = SessionService.update_session(
        session_id,
        topic=request.topic,
        db=db,
    )
    return SessionResponse(
        id=updated.id,
        user_id=updated.user_id,
        created_at=updated.created_at.isoformat(),
        updated_at=updated.updated_at.isoformat(),
        topic=updated.topic,
        feedback_score=updated.feedback_score,
        message_count=len(updated.messages),
    )


@router.post("/sessions/{session_id}/feedback")
async def submit_feedback(
    session_id: str,
    request: SessionFeedbackRequest,
    db: DBSession = Depends(get_db),
    current_user: Optional[TokenData] = Depends(get_current_user_optional),
):
    """
    Submit feedback/rating for a session.
    
    Score must be between 1 and 5.
    """
    session = SessionService.get_session(session_id, db)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    # Check access permissions
    if current_user:
        user_db = db.query(User).filter(User.id == current_user.user_id).first()
        if user_db and user_db.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            if session.user_id != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot rate other users' sessions",
                )
    
    updated = SessionService.update_session(
        session_id,
        feedback_score=request.feedback_score,
        db=db,
    )
    return {
        "message": "Feedback recorded",
        "score": updated.feedback_score,
    }


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_session(
    session_id: str,
    db: DBSession = Depends(get_db),
    current_user: Optional[TokenData] = Depends(get_current_user_optional),
):
    """
    Delete a session and all its messages.
    
    If authenticated, can only delete own sessions unless admin.
    """
    session = SessionService.get_session(session_id, db)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    # Check access permissions
    if current_user:
        user_db = db.query(User).filter(User.id == current_user.user_id).first()
        if user_db and user_db.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            if session.user_id != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot delete other users' sessions",
                )
    
    db.delete(session)
    db.commit()
    return {"message": "Session deleted"}


@router.post(
    "/sessions/{session_id}/export",
    response_model=dict,
)
async def export_session(
    session_id: str,
    db: DBSession = Depends(get_db),
    current_user: Optional[TokenData] = Depends(get_current_user_optional),
):
    """
    Export session conversation as JSON.
    
    If authenticated, can only export own sessions unless admin.
    """
    session = SessionService.get_session(session_id, db)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    # Check access permissions
    if current_user:
        user_db = db.query(User).filter(User.id == current_user.user_id).first()
        if user_db and user_db.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            if session.user_id != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot export other users' sessions",
                )
    
    messages = MessageService.get_session_messages(session_id, db)
    return {
        "session": session.to_dict(),
        "messages": [m.to_dict() for m in messages],
    }


# ============================================================================
# Message Endpoints
# ============================================================================

@router.get(
    "/sessions/{session_id}/messages",
    response_model=List[MessageResponse],
)
async def get_session_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=1000),
    db: DBSession = Depends(get_db),
    current_user: Optional[TokenData] = Depends(get_current_user_optional),
):
    """
    Get all messages in a session.
    
    If authenticated, can only access messages from own sessions unless admin.
    """
    session = SessionService.get_session(session_id, db)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    # Check access permissions
    if current_user:
        user_db = db.query(User).filter(User.id == current_user.user_id).first()
        if user_db and user_db.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            if session.user_id != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot access messages from other users' sessions",
                )
    
    messages = MessageService.get_session_messages(session_id, db, limit=limit)
    return [
        MessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at.isoformat(),
            ml_used=m.ml_used,
            ml_model_version=m.ml_model_version,
            extracted_line=m.extracted_line,
            extracted_station=m.extracted_station,
            extracted_time=m.extracted_time,
            extracted_day=m.extracted_day,
            confidence_score=m.confidence_score,
            intent=m.intent,
        )
        for m in messages
    ]


@router.get(
    "/messages/{message_id}",
    response_model=MessageResponse,
)
async def get_message(
    message_id: str,
    db: DBSession = Depends(get_db),
    current_user: Optional[TokenData] = Depends(get_current_user_optional),
):
    """
    Get a specific message.
    
    If authenticated, can only access messages from own sessions unless admin.
    """
    message = MessageService.get_message(message_id, db)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    
    # Check access permissions
    if current_user:
        session = db.query(Session).filter(Session.id == message.session_id).first()
        user_db = db.query(User).filter(User.id == current_user.user_id).first()
        if user_db and user_db.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            if session and session.user_id != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot access messages from other users' sessions",
                )
    
    return MessageResponse(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at.isoformat(),
        ml_used=message.ml_used,
        ml_model_version=message.ml_model_version,
        extracted_line=message.extracted_line,
        extracted_station=message.extracted_station,
        extracted_time=message.extracted_time,
        extracted_day=message.extracted_day,
        confidence_score=message.confidence_score,
        intent=message.intent,
    )

