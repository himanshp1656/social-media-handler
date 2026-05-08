import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import (
    User, Team, TrendSuggestion, ContentBrief, Script, Beat,
    Upload, Analytics, CommentReply,
)

MOCK_DIR = Path(__file__).resolve().parent.parent / "mock"

SEED_TEAM_ALL = "team_all_content"
SEED_TEAM_ID = "team_youtube"
SEED_TEAM_INSTA_ID = "team_instagram"


def _load(filename: str) -> list[dict]:
    path = MOCK_DIR / filename
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    return datetime.fromisoformat(val).replace(tzinfo=timezone.utc)


def is_seeded(db: Session) -> bool:
    """Check if mock data is already loaded."""
    return db.query(User).filter(User.id == "user_himanshu").first() is not None


def seed(db: Session) -> dict:
    """Load all mock JSON files into the database. Skips if already seeded."""
    if is_seeded(db):
        return {"status": "skipped", "message": "Mock data already loaded"}

    counts = {}

    # Teams
    db.add(Team(id=SEED_TEAM_ALL, name="All Content", created_by="user_himanshu"))
    db.add(Team(id=SEED_TEAM_ID, name="YouTube Team", created_by="user_himanshu"))
    db.add(Team(id=SEED_TEAM_INSTA_ID, name="Instagram Team", created_by="user_himanshu"))
    counts["teams"] = 3

    # Users (default to All Content team)
    for u in _load("users.json"):
        db.add(User(
            id=u["id"], email=u["email"],
            display_name=u["display_name"],
            password_hash=u["password_hash"],
            active_team_id=SEED_TEAM_ALL,
        ))
    counts["users"] = len(_load("users.json"))

    # Trends (assign to YouTube team)
    for t in _load("trends.json"):
        db.add(TrendSuggestion(
            id=t["id"], keyword=t["keyword"], source=t["source"],
            trend_score=t["trend_score"], suggested_brief=t["suggested_brief"],
            status=t["status"], team_id=SEED_TEAM_ID,
        ))
    counts["trends"] = len(_load("trends.json"))

    # Briefs (assign to YouTube team)
    for b in _load("briefs.json"):
        db.add(ContentBrief(
            id=b["id"], topic=b["topic"], raw_brief=b["raw_brief"],
            suggestion_id=b.get("suggestion_id"),
            created_by=b.get("created_by"),
            team_id=SEED_TEAM_ID,
        ))
    counts["briefs"] = len(_load("briefs.json"))

    # Scripts (assign based on platform)
    for s in _load("scripts.json"):
        platform = s.get("platform", "youtube_shorts")
        tid = SEED_TEAM_INSTA_ID if "instagram" in platform else SEED_TEAM_ID
        db.add(Script(
            id=s["id"], brief_id=s["brief_id"],
            angle=s["angle"], hook_type=s["hook_type"],
            platform=platform,
            duration=s.get("duration", "30s"),
            title=s["title"], hook=s["hook"], body=s["body"],
            cta=s["cta"], cta_goal=s["cta_goal"],
            hashtags=s.get("hashtags"),
            thumbnail_suggestion=s.get("thumbnail_suggestion"),
            predicted_performance=s.get("predicted_performance"),
            views=s.get("views", 0), likes=s.get("likes", 0),
            comments=s.get("comments", 0), score=s.get("score", 0),
            created_by=s.get("created_by"),
            team_id=tid,
        ))
    counts["scripts"] = len(_load("scripts.json"))

    # Beats
    for b in _load("beats.json"):
        db.add(Beat(
            id=b["id"], script_id=b["script_id"],
            beat_number=b["beat_number"], beat_type=b["beat_type"],
            timestamp=b["timestamp"], duration_seconds=b["duration_seconds"],
            voiceover=b["voiceover"],
            on_screen_text=b.get("on_screen_text"),
            visual_cue=b.get("visual_cue"),
            camera=b.get("camera"),
        ))
    counts["beats"] = len(_load("beats.json"))

    # Uploads (assign to YouTube team)
    for u in _load("uploads.json"):
        db.add(Upload(
            id=u["id"], script_id=u["script_id"],
            youtube_video_id=u.get("youtube_video_id"),
            upload_status=u.get("upload_status", "pending"),
            created_by=u.get("created_by"),
            uploaded_at=_parse_dt(u.get("uploaded_at")),
            team_id=SEED_TEAM_ID,
        ))
    counts["uploads"] = len(_load("uploads.json"))

    # Analytics
    for a in _load("analytics.json"):
        db.add(Analytics(
            id=a["id"], upload_id=a["upload_id"],
            views=a["views"], likes=a["likes"], comments=a["comments"],
            watch_time_minutes=a.get("watch_time_minutes", 0),
            ctr=a.get("ctr", 0),
            fetched_at=_parse_dt(a.get("fetched_at")),
        ))
    counts["analytics"] = len(_load("analytics.json"))

    # Comments
    for c in _load("comments.json"):
        db.add(CommentReply(
            id=c["id"], upload_id=c["upload_id"],
            youtube_comment_id=c["youtube_comment_id"],
            author=c.get("author"),
            comment_text=c["comment_text"],
            suggested_reply=c.get("suggested_reply"),
            status=c.get("status", "pending"),
        ))
    counts["comments"] = len(_load("comments.json"))

    db.commit()
    return {"status": "seeded", "counts": counts}
