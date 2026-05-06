import os
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import ScheduledPost, Script, User, new_id
from app.auth.dependencies import get_current_user_api

router = APIRouter(prefix="/calendar", tags=["calendar"])

UPLOAD_DIR = "data/scheduled_videos"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ScheduleRequest(BaseModel):
    script_id: str
    scheduled_at: str  # ISO format: "2026-04-30T14:00:00"
    privacy_status: str = "public"
    notes: str = ""


@router.post("/schedule")
async def schedule_post(
    script_id: str = Form(...),
    scheduled_at: str = Form(...),
    privacy_status: str = Form("public"),
    notes: str = Form(""),
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_api),
):
    """Schedule a video to be posted at a specific time."""
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        return {"error": "Script not found"}

    # Save video file
    file_path = os.path.join(UPLOAD_DIR, f"{new_id()}_{video.filename}")
    with open(file_path, "wb") as f:
        content = await video.read()
        f.write(content)

    scheduled_dt = datetime.fromisoformat(scheduled_at).replace(tzinfo=timezone.utc)

    post = ScheduledPost(
        id=new_id(),
        script_id=script_id,
        video_file_path=file_path,
        scheduled_at=scheduled_dt,
        privacy_status=privacy_status,
        notes=notes,
        created_by=user.id,
    )
    db.add(post)
    db.commit()

    return {
        "id": post.id,
        "script_id": script_id,
        "scheduled_at": str(post.scheduled_at),
        "status": post.status,
    }


@router.get("/week")
def get_week(date: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """Get all scheduled posts for a week. Pass date as YYYY-MM-DD (defaults to this week)."""
    if date:
        base = datetime.strptime(date, "%Y-%m-%d")
    else:
        base = datetime.now(timezone.utc)

    # Get Monday of that week
    monday = base - timedelta(days=base.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=7)

    posts = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.scheduled_at >= monday)
        .filter(ScheduledPost.scheduled_at < sunday)
        .order_by(ScheduledPost.scheduled_at)
        .all()
    )

    result = []
    for p in posts:
        script = db.query(Script).filter(Script.id == p.script_id).first()
        result.append({
            "id": p.id,
            "script_id": p.script_id,
            "title": script.title if script else "Unknown",
            "angle": script.angle if script else "",
            "platform": script.platform if script else "",
            "scheduled_at": str(p.scheduled_at),
            "privacy_status": p.privacy_status,
            "status": p.status,
            "youtube_video_id": p.youtube_video_id,
            "notes": p.notes or "",
            "error_message": p.error_message or "",
        })

    return {
        "week_start": str(monday.date()),
        "week_end": str((sunday - timedelta(days=1)).date()),
        "posts": result,
    }


@router.patch("/{post_id}")
def reschedule(post_id: str, scheduled_at: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """Reschedule a post to a new time."""
    post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
    if not post:
        return {"error": "Post not found"}
    if post.status == "posted":
        return {"error": "Already posted"}

    post.scheduled_at = datetime.fromisoformat(scheduled_at).replace(tzinfo=timezone.utc)
    post.status = "scheduled"
    db.commit()
    return {"id": post.id, "scheduled_at": str(post.scheduled_at), "status": post.status}


@router.delete("/{post_id}")
def delete_post(post_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """Delete a scheduled post."""
    post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
    if not post:
        return {"error": "Post not found"}
    if post.status == "posted":
        return {"error": "Already posted, cannot delete"}

    # Clean up video file
    if post.video_file_path and os.path.exists(post.video_file_path):
        os.remove(post.video_file_path)

    db.delete(post)
    db.commit()
    return {"deleted": post_id}


@router.get("/upcoming")
def upcoming_posts(db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """Get next 10 upcoming scheduled posts."""
    now = datetime.now(timezone.utc)
    posts = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.status == "scheduled")
        .filter(ScheduledPost.scheduled_at >= now)
        .order_by(ScheduledPost.scheduled_at)
        .limit(10)
        .all()
    )
    result = []
    for p in posts:
        script = db.query(Script).filter(Script.id == p.script_id).first()
        result.append({
            "id": p.id,
            "title": script.title if script else "Unknown",
            "scheduled_at": str(p.scheduled_at),
            "status": p.status,
        })
    return result
