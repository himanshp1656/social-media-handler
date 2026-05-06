from datetime import datetime, timezone
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from sqlalchemy.orm import Session

from app.models import Upload, Script, new_id
from app.youtube.auth import get_credentials


def upload_video(
    db: Session,
    script_id: str,
    video_file_path: str,
    privacy_status: str = "private",
) -> dict:
    # Get script for metadata
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise ValueError(f"Script {script_id} not found")

    # Create upload record
    upload = Upload(id=new_id(), script_id=script_id)
    db.add(upload)
    db.commit()

    try:
        creds = get_credentials()
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": script.title,
                "description": f"{script.body}\n\n{script.cta}",
                "tags": [script.angle, script.hook_type, script.cta_goal],
                "categoryId": "22",  # People & Blogs
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(video_file_path, resumable=True)

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = request.execute()

        upload.youtube_video_id = response["id"]
        upload.upload_status = "uploaded"
        upload.uploaded_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "upload_id": upload.id,
            "youtube_video_id": response["id"],
            "status": "uploaded",
        }

    except Exception as e:
        upload.upload_status = "failed"
        db.commit()
        raise RuntimeError(f"Upload failed: {e}") from e
