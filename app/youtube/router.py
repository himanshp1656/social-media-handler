import os
import re
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Script, Upload, User, new_id
from app.youtube.auth import get_auth_url, handle_callback
from app.youtube.upload import upload_video
from app.youtube.analytics import fetch_all_analytics
from app.auth.dependencies import get_current_user_api

router = APIRouter(prefix="/youtube", tags=["youtube"])


@router.get("/auth")
def auth():
    url = get_auth_url()
    return RedirectResponse(url)


@router.get("/callback")
def callback(code: str = Query(...)):
    handle_callback(code)
    return RedirectResponse(url="/", status_code=302)


class UploadRequest(BaseModel):
    script_id: str
    video_file_path: str
    privacy_status: str = "private"


@router.post("/upload")
def upload(req: UploadRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    result = upload_video(db, req.script_id, req.video_file_path, req.privacy_status, created_by=user.id, team_id=user.active_team_id)
    return result


# ---- Link existing YouTube video to a script ----

class LinkRequest(BaseModel):
    script_id: str
    youtube_video_id: str


def _extract_video_id(raw: str) -> str:
    """Extract YouTube video ID from a URL or plain ID string."""
    raw = raw.strip()
    # Match various YouTube URL patterns
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        m = re.search(pattern, raw)
        if m:
            return m.group(1)
    # If it looks like a bare video ID (11 chars, alphanumeric + _ -)
    if re.fullmatch(r'[a-zA-Z0-9_-]{11}', raw):
        return raw
    raise ValueError(f"Cannot parse YouTube video ID from: {raw}")


@router.post("/link")
def link_video(req: LinkRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """Link an existing YouTube video to a script."""
    script = db.query(Script).filter(Script.id == req.script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")

    try:
        video_id = _extract_video_id(req.youtube_video_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    upload_record = Upload(
        id=new_id(),
        script_id=req.script_id,
        youtube_video_id=video_id,
        upload_status="linked",
        created_by=user.id,
        team_id=user.active_team_id,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(upload_record)
    db.commit()

    return {
        "upload_id": upload_record.id,
        "youtube_video_id": video_id,
        "status": "linked",
    }


# ---- Upload video file to YouTube ----

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv"}
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB


@router.post("/upload-file")
async def upload_file(
    script_id: str = Form(...),
    privacy_status: str = Form("private"),
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_api),
):
    """Upload a video file directly to YouTube for a given script."""
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")

    # Validate file extension
    ext = os.path.splitext(video.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Save to temp file, then upload via existing upload_video function
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        contents = await video.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large (max 2 GB)")
        tmp.write(contents)
        tmp.close()

        result = upload_video(db, script_id, tmp.name, privacy_status, created_by=user.id, team_id=user.active_team_id)
        return result
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


@router.get("/fetch-analytics")
def fetch_analytics(db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    results = fetch_all_analytics(db)
    return {"fetched": len(results), "results": results}
