from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Text, ForeignKey, DateTime
from app.database import Base
from nanoid import generate


def new_id() -> str:
    return generate(size=12)


class ContentBrief(Base):
    __tablename__ = "content_briefs"

    id = Column(String, primary_key=True, default=new_id)
    topic = Column(String, nullable=False)
    raw_brief = Column(Text, nullable=False)
    suggestion_id = Column(String, ForeignKey("trend_suggestions.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Script(Base):
    __tablename__ = "scripts"

    id = Column(String, primary_key=True, default=new_id)
    brief_id = Column(String, ForeignKey("content_briefs.id"), nullable=False)
    template_id = Column(String, ForeignKey("script_templates.id"), nullable=True)
    angle = Column(String, nullable=False)  # fear | opportunity | myth_busting | news_based | contrarian
    hook_type = Column(String, nullable=False)  # curiosity | emotional | reliability
    platform = Column(String, default="youtube_shorts")  # instagram_reels | youtube_shorts
    duration = Column(String, default="30s")  # 15s | 30s | 60s
    title = Column(String, nullable=False)
    hook = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    cta = Column(Text, nullable=False)
    cta_goal = Column(String, nullable=False)  # awareness | conversion | retention
    hashtags = Column(Text, nullable=True)  # JSON array as string
    thumbnail_suggestion = Column(Text, nullable=True)
    predicted_performance = Column(String, nullable=True)  # low | medium | high
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Beat(Base):
    __tablename__ = "beats"

    id = Column(String, primary_key=True, default=new_id)
    script_id = Column(String, ForeignKey("scripts.id"), nullable=False)
    beat_number = Column(Integer, nullable=False)
    beat_type = Column(String, nullable=False)  # hook | problem | insight | proof | cta | twist
    timestamp = Column(String, nullable=False)  # "0:00-0:03"
    duration_seconds = Column(Integer, nullable=False)
    voiceover = Column(Text, nullable=False)
    on_screen_text = Column(Text, nullable=True)
    visual_cue = Column(Text, nullable=True)
    camera = Column(Text, nullable=True)


class ScriptTemplate(Base):
    __tablename__ = "script_templates"

    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    angle = Column(String, nullable=False)
    hook_type = Column(String, nullable=False)
    platform = Column(String, default="youtube_shorts")
    duration = Column(String, default="30s")
    cta_goal = Column(String, nullable=False)
    beat_structure = Column(Text, nullable=False)  # JSON array of beat templates
    source_script_id = Column(String, nullable=True)  # script it was derived from
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(String, primary_key=True, default=new_id)
    script_id = Column(String, ForeignKey("scripts.id"), nullable=False)
    youtube_video_id = Column(String, nullable=True)
    upload_status = Column(String, default="pending")  # pending | uploaded | linked | failed
    uploaded_at = Column(DateTime, nullable=True)


class Analytics(Base):
    __tablename__ = "analytics"

    id = Column(String, primary_key=True, default=new_id)
    upload_id = Column(String, ForeignKey("uploads.id"), nullable=False)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    watch_time_minutes = Column(Float, default=0.0)
    ctr = Column(Float, default=0.0)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id = Column(String, primary_key=True, default=new_id)
    script_id = Column(String, ForeignKey("scripts.id"), nullable=False)
    video_file_path = Column(String, nullable=True)
    scheduled_at = Column(DateTime, nullable=False)
    privacy_status = Column(String, default="public")  # public | unlisted | private
    status = Column(String, default="scheduled")  # scheduled | posting | posted | failed | missed
    youtube_video_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CommentReply(Base):
    __tablename__ = "comment_replies"

    id = Column(String, primary_key=True, default=new_id)
    upload_id = Column(String, ForeignKey("uploads.id"), nullable=False)
    youtube_comment_id = Column(String, nullable=False)
    author = Column(String, nullable=True)
    comment_text = Column(Text, nullable=False)
    suggested_reply = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending | approved | posted | skipped
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TrendSuggestion(Base):
    __tablename__ = "trend_suggestions"

    id = Column(String, primary_key=True, default=new_id)
    keyword = Column(String, nullable=False)
    source = Column(String, nullable=False)  # google_trends | news_api
    trend_score = Column(Float, default=0.0)
    suggested_brief = Column(Text, nullable=False)
    status = Column(String, default="suggested")  # suggested | accepted | rejected | used
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ScriptVersion(Base):
    __tablename__ = "script_versions"

    id = Column(String, primary_key=True, default=new_id)
    script_id = Column(String, ForeignKey("scripts.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    change_type = Column(String, nullable=False)  # regenerated | edited
    title = Column(String, nullable=False)
    angle = Column(String, nullable=False)
    hook_type = Column(String, nullable=False)
    cta_goal = Column(String, nullable=False)
    hashtags = Column(Text, nullable=True)
    thumbnail_suggestion = Column(Text, nullable=True)
    predicted_performance = Column(String, nullable=True)
    beats_snapshot = Column(Text, nullable=False)  # JSON array of beat dicts
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
