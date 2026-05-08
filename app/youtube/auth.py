import json
from datetime import datetime, timezone
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from app.config import settings
from app.database import SessionLocal
from app.models import OAuthToken

PROVIDER = "youtube"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def _get_client_config() -> dict:
    return {
        "web": {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "redirect_uris": [settings.YOUTUBE_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def _get_token_row(db=None):
    """Get the YouTube token row from DB."""
    close = False
    if db is None:
        db = SessionLocal()
        close = True
    try:
        return db.query(OAuthToken).filter(OAuthToken.provider == PROVIDER).first()
    finally:
        if close:
            db.close()


def get_auth_url() -> str:
    flow = Flow.from_client_config(_get_client_config(), scopes=SCOPES)
    flow.redirect_uri = settings.YOUTUBE_REDIRECT_URI
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    return auth_url


def handle_callback(code: str) -> None:
    flow = Flow.from_client_config(_get_client_config(), scopes=SCOPES)
    flow.redirect_uri = settings.YOUTUBE_REDIRECT_URI
    flow.fetch_token(code=code)

    creds = flow.credentials

    db = SessionLocal()
    try:
        row = db.query(OAuthToken).filter(OAuthToken.provider == PROVIDER).first()
        if row:
            row.token = creds.token
            row.refresh_token = creds.refresh_token
            row.token_uri = creds.token_uri
            row.updated_at = datetime.now(timezone.utc)
        else:
            row = OAuthToken(
                provider=PROVIDER,
                token=creds.token,
                refresh_token=creds.refresh_token,
                token_uri=creds.token_uri,
            )
            db.add(row)
        db.commit()
    finally:
        db.close()


def is_authenticated() -> bool:
    """Check if YouTube OAuth token exists in DB."""
    return _get_token_row() is not None


def get_credentials() -> Credentials:
    row = _get_token_row()
    if not row:
        raise FileNotFoundError(
            f"YouTube not authenticated. Visit this URL to authorize:\n{get_auth_url()}"
        )

    creds = Credentials(
        token=row.token,
        refresh_token=row.refresh_token,
        token_uri=row.token_uri or "https://oauth2.googleapis.com/token",
        client_id=settings.YOUTUBE_CLIENT_ID,
        client_secret=settings.YOUTUBE_CLIENT_SECRET,
    )

    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        try:
            creds.refresh(Request())
            # Save refreshed token back to DB
            db = SessionLocal()
            try:
                db_row = db.query(OAuthToken).filter(OAuthToken.provider == PROVIDER).first()
                if db_row:
                    db_row.token = creds.token
                    db_row.refresh_token = creds.refresh_token
                    db_row.updated_at = datetime.now(timezone.utc)
                    db.commit()
            finally:
                db.close()
        except Exception:
            # Refresh token revoked or expired — remove from DB
            db = SessionLocal()
            try:
                db_row = db.query(OAuthToken).filter(OAuthToken.provider == PROVIDER).first()
                if db_row:
                    db.delete(db_row)
                    db.commit()
            finally:
                db.close()
            return None

    return creds
