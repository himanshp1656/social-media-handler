"""Background job: auto-post scheduled videos when their time arrives."""

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.models import ScheduledPost, Script, Upload, new_id
from app.youtube.auth import is_authenticated, get_credentials


def process_scheduled_posts(db: Session):
    """Check for posts due in the next 2 minutes and upload them to YouTube."""
    if not is_authenticated():
        return

    now = datetime.now(timezone.utc)
    window = now + timedelta(minutes=2)

    due_posts = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.status == "scheduled")
        .filter(ScheduledPost.scheduled_at <= window)
        .all()
    )

    for post in due_posts:
        try:
            post.status = "posting"
            db.commit()

            script = db.query(Script).filter(Script.id == post.script_id).first()
            if not script:
                post.status = "failed"
                post.error_message = "Script not found"
                db.commit()
                continue

            if not post.video_file_path:
                post.status = "failed"
                post.error_message = "No video file"
                db.commit()
                continue

            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds = get_credentials()
            youtube = build("youtube", "v3", credentials=creds)

            body = {
                "snippet": {
                    "title": script.title,
                    "description": f"{script.body}\n\n{script.cta}",
                    "tags": [script.angle, script.hook_type, script.cta_goal],
                    "categoryId": "22",
                },
                "status": {
                    "privacyStatus": post.privacy_status or "public",
                    "selfDeclaredMadeForKids": False,
                },
            }

            media = MediaFileUpload(post.video_file_path, resumable=True)
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )
            response = request.execute()

            post.youtube_video_id = response["id"]
            post.status = "posted"

            # Also create an Upload record so it appears in analytics
            upload = Upload(
                id=new_id(),
                script_id=script.id,
                youtube_video_id=response["id"],
                upload_status="uploaded",
                uploaded_at=datetime.now(timezone.utc),
            )
            db.add(upload)
            db.commit()

        except Exception as e:
            post.status = "failed"
            post.error_message = str(e)[:500]
            db.commit()


def mark_missed_posts(db: Session):
    """Mark posts that are past due and never posted as missed."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    missed = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.status == "scheduled")
        .filter(ScheduledPost.scheduled_at < cutoff)
        .all()
    )
    for post in missed:
        post.status = "missed"
    if missed:
        db.commit()
