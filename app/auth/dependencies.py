from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserSession


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """For HTML page routes — redirects to login if not authenticated."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})

    sess = (
        db.query(UserSession)
        .filter(UserSession.id == session_id, UserSession.expires_at > datetime.now(timezone.utc))
        .first()
    )
    if not sess:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})

    user = db.query(User).filter(User.id == sess.user_id).first()
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    return user


def get_current_user_api(request: Request, db: Session = Depends(get_db)) -> User:
    """For API routes called by fetch() — returns 401 JSON."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sess = (
        db.query(UserSession)
        .filter(UserSession.id == session_id, UserSession.expires_at > datetime.now(timezone.utc))
        .first()
    )
    if not sess:
        raise HTTPException(status_code=401, detail="Session expired")

    user = db.query(User).filter(User.id == sess.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
