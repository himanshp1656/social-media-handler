import json
import os
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from app.config import settings

TOKEN_PATH = "data/youtube-token.json"

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
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        json.dump({
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        }, f, indent=2)


def is_authenticated() -> bool:
    """Check if YouTube OAuth token exists."""
    return os.path.exists(TOKEN_PATH)


def get_credentials() -> Credentials:
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(
            f"YouTube not authenticated. Visit this URL to authorize:\n{get_auth_url()}"
        )

    with open(TOKEN_PATH) as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id", settings.YOUTUBE_CLIENT_ID),
        client_secret=token_data.get("client_secret", settings.YOUTUBE_CLIENT_SECRET),
    )

    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        try:
            creds.refresh(Request())
            # Save refreshed token
            with open(TOKEN_PATH, "w") as f:
                json.dump({
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                }, f, indent=2)
        except Exception:
            # Refresh token revoked or expired — delete stale token
            os.remove(TOKEN_PATH)
            return None

    return creds
