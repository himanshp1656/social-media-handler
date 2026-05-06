from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.models import Upload, Analytics, Script, new_id
from app.youtube.auth import get_credentials


def fetch_analytics_for_upload(db: Session, upload: Upload) -> dict | None:
    if not upload.youtube_video_id:
        return None

    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    response = youtube.videos().list(
        part="statistics",
        id=upload.youtube_video_id,
    ).execute()

    items = response.get("items", [])
    if not items:
        return None

    stats = items[0]["statistics"]

    analytics = Analytics(
        id=new_id(),
        upload_id=upload.id,
        views=int(stats.get("viewCount", 0)),
        likes=int(stats.get("likeCount", 0)),
        comments=int(stats.get("commentCount", 0)),
        watch_time_minutes=0.0,  # Requires YouTube Analytics API (separate call)
        ctr=0.0,  # Requires YouTube Analytics API
    )
    db.add(analytics)
    db.commit()

    return {
        "upload_id": upload.id,
        "youtube_video_id": upload.youtube_video_id,
        "views": analytics.views,
        "likes": analytics.likes,
        "comments": analytics.comments,
    }


def fetch_all_analytics(db: Session) -> list[dict]:
    uploads = db.query(Upload).filter(Upload.upload_status.in_(["uploaded", "linked"])).all()
    results = []
    for upload in uploads:
        result = fetch_analytics_for_upload(db, upload)
        if result:
            results.append(result)
    return results
