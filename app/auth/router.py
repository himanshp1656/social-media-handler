from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserSession, new_id

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())

SESSION_DURATION_DAYS = 7


def _create_session(db: Session, user_id: str) -> UserSession:
    sess = UserSession(
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS),
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def _set_session_cookie(response: RedirectResponse, session_id: str) -> RedirectResponse:
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=SESSION_DURATION_DAYS * 86400,
        path="/",
    )
    return response


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not _verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password"},
            status_code=400,
        )

    sess = _create_session(db, user.id)
    response = RedirectResponse(url="/", status_code=302)
    return _set_session_cookie(response, sess.id)


@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request, "error": None})


@router.post("/signup")
def signup(
    request: Request,
    display_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Email already registered"},
            status_code=400,
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Password must be at least 6 characters"},
            status_code=400,
        )

    user = User(
        id=new_id(),
        email=email.strip().lower(),
        display_name=display_name.strip(),
        password_hash=_hash_password(password),
    )
    db.add(user)
    db.commit()

    sess = _create_session(db, user.id)
    response = RedirectResponse(url="/", status_code=302)
    return _set_session_cookie(response, sess.id)


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if session_id:
        sess = db.query(UserSession).filter(UserSession.id == session_id).first()
        if sess:
            db.delete(sess)
            db.commit()

    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("session_id", path="/")
    return response
