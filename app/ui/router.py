from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.models import ContentBrief, Script, Beat, Upload, TrendSuggestion, ScheduledPost, CommentReply
from app.feedback.scorer import get_top_scripts
from app.youtube.auth import is_authenticated

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory="templates")


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    briefs = db.query(ContentBrief).order_by(desc(ContentBrief.created_at)).limit(5).all()
    suggestions = db.query(TrendSuggestion).order_by(desc(TrendSuggestion.created_at)).limit(5).all()

    stats = {
        "briefs": db.query(func.count(ContentBrief.id)).scalar() or 0,
        "scripts": db.query(func.count(Script.id)).scalar() or 0,
        "uploads": db.query(func.count(Upload.id)).filter(Upload.upload_status == "uploaded").scalar() or 0,
        "suggestions": db.query(func.count(TrendSuggestion.id)).scalar() or 0,
    }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active": "dashboard",
        "stats": stats,
        "briefs": [_brief_dict(b) for b in briefs],
        "suggestions": [_suggestion_dict(s) for s in suggestions],
    })


@router.get("/ui/generate")
def generate_page(request: Request, brief: str = "", template_id: str = "", suggestion_id: str = "", db: Session = Depends(get_db)):
    template = None
    if template_id:
        from app.models import ScriptTemplate
        tpl = db.query(ScriptTemplate).filter(ScriptTemplate.id == template_id).first()
        if tpl:
            template = _template_dict(tpl)
    return templates.TemplateResponse("generate.html", {
        "request": request,
        "active": "generate",
        "prefill": brief,
        "template": template,
        "suggestion_id": suggestion_id,
    })


@router.get("/ui/batch")
def batch_page(request: Request):
    return templates.TemplateResponse("batch.html", {
        "request": request,
        "active": "batch",
    })


@router.get("/ui/templates")
def templates_page(request: Request, db: Session = Depends(get_db)):
    from app.models import ScriptTemplate
    tpls = db.query(ScriptTemplate).order_by(desc(ScriptTemplate.created_at)).all()
    return templates.TemplateResponse("templates.html", {
        "request": request,
        "active": "templates",
        "templates": [_template_dict(t) for t in tpls],
    })


@router.get("/ui/briefs")
def briefs_page(request: Request, db: Session = Depends(get_db)):
    briefs = db.query(ContentBrief).order_by(desc(ContentBrief.created_at)).limit(50).all()
    return templates.TemplateResponse("briefs.html", {
        "request": request,
        "active": "briefs",
        "briefs": [_brief_dict(b) for b in briefs],
    })


@router.get("/ui/briefs/{brief_id}")
def brief_detail_page(brief_id: str, request: Request, db: Session = Depends(get_db)):
    brief = db.query(ContentBrief).filter(ContentBrief.id == brief_id).first()
    if not brief:
        return templates.TemplateResponse("briefs.html", {
            "request": request,
            "active": "briefs",
            "briefs": [],
        })

    scripts = db.query(Script).filter(Script.brief_id == brief_id).all()

    # Build a map of script_id -> list of upload dicts (1 script can have multiple uploads)
    script_ids = [s.id for s in scripts]
    uploads = db.query(Upload).filter(Upload.script_id.in_(script_ids)).all() if script_ids else []
    upload_map = {}
    for u in uploads:
        upload_map.setdefault(u.script_id, []).append({
            "id": u.id,
            "youtube_video_id": u.youtube_video_id,
            "upload_status": u.upload_status,
            "uploaded_at": str(u.uploaded_at) if u.uploaded_at else "",
        })

    # Build beats map: script_id -> list of beat dicts
    beats_map = {}
    all_beats = db.query(Beat).filter(Beat.script_id.in_(script_ids)).order_by(Beat.beat_number).all() if script_ids else []
    for b in all_beats:
        beats_map.setdefault(b.script_id, []).append({
            "id": b.id,
            "beat": b.beat_number,
            "type": b.beat_type,
            "timestamp": b.timestamp,
            "duration_seconds": b.duration_seconds,
            "voiceover": b.voiceover,
            "on_screen_text": b.on_screen_text,
            "visual_cue": b.visual_cue,
            "camera": b.camera,
        })

    return templates.TemplateResponse("brief_detail.html", {
        "request": request,
        "active": "briefs",
        "brief": _brief_dict(brief),
        "scripts": [_script_dict(s) for s in scripts],
        "beats_map": beats_map,
        "upload_map": upload_map,
        "youtube_authenticated": is_authenticated(),
    })


@router.get("/ui/teleprompter/{script_id}")
def teleprompter_page(script_id: str, request: Request, db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        return templates.TemplateResponse("briefs.html", {"request": request, "active": "briefs", "briefs": []})

    beats = db.query(Beat).filter(Beat.script_id == script_id).order_by(Beat.beat_number).all()
    return templates.TemplateResponse("teleprompter.html", {
        "request": request,
        "script": _script_dict(script),
        "beats": [
            {"type": b.beat_type, "timestamp": b.timestamp, "duration_seconds": b.duration_seconds,
             "voiceover": b.voiceover, "on_screen_text": b.on_screen_text, "visual_cue": b.visual_cue, "camera": b.camera}
            for b in beats
        ],
    })


@router.get("/ui/trends")
def trends_page(request: Request, db: Session = Depends(get_db)):
    suggestions = db.query(TrendSuggestion).order_by(desc(TrendSuggestion.created_at)).limit(30).all()
    return templates.TemplateResponse("trends.html", {
        "request": request,
        "active": "trends",
        "suggestions": [_suggestion_dict(s) for s in suggestions],
    })


@router.get("/ui/calendar")
def calendar_page(request: Request, date: str = "", db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    import calendar as cal_module

    if date:
        base = datetime.strptime(date, "%Y-%m-%d")
    else:
        base = datetime.now(timezone.utc)

    year = base.year
    month = base.month

    first_day = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day_num = cal_module.monthrange(year, month)[1]
    last_day = datetime(year, month, last_day_num, 23, 59, 59, tzinfo=timezone.utc)

    posts = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.scheduled_at >= first_day)
        .filter(ScheduledPost.scheduled_at <= last_day)
        .order_by(ScheduledPost.scheduled_at)
        .all()
    )

    posts_by_date = {}
    for p in posts:
        script = db.query(Script).filter(Script.id == p.script_id).first()
        day_key = p.scheduled_at.strftime("%Y-%m-%d")
        posts_by_date.setdefault(day_key, []).append({
            "id": p.id,
            "title": script.title if script else "Unknown",
            "time": p.scheduled_at.strftime("%H:%M"),
            "status": p.status,
        })

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build 6×7 grid starting Sunday
    cal = cal_module.Calendar(firstweekday=6)
    weeks = cal.monthdatescalendar(year, month)

    grid = []
    for week in weeks:
        week_days = []
        for d in week:
            ds = d.strftime("%Y-%m-%d")
            week_days.append({
                "date": ds,
                "day": d.day,
                "is_current_month": d.month == month,
                "is_today": ds == today_str,
                "posts": posts_by_date.get(ds, []),
            })
        grid.append(week_days)

    if month == 1:
        prev_month_date = datetime(year - 1, 12, 1)
    else:
        prev_month_date = datetime(year, month - 1, 1)
    if month == 12:
        next_month_date = datetime(year + 1, 1, 1)
    else:
        next_month_date = datetime(year, month + 1, 1)

    scripts = db.query(Script).order_by(desc(Script.created_at)).limit(50).all()

    return templates.TemplateResponse("calendar.html", {
        "request": request,
        "active": "calendar",
        "grid": grid,
        "month_name": first_day.strftime("%B %Y"),
        "prev_month": prev_month_date.strftime("%Y-%m-%d"),
        "next_month": next_month_date.strftime("%Y-%m-%d"),
        "scripts": [_script_dict(s) for s in scripts],
    })


@router.get("/ui/comments")
def comments_page(request: Request, upload_id: str = "", db: Session = Depends(get_db)):
    uploads = (
        db.query(Upload)
        .filter(Upload.upload_status.in_(["uploaded", "linked"]))
        .all()
    )
    upload_list = []
    for u in uploads:
        script = db.query(Script).filter(Script.id == u.script_id).first()
        upload_list.append({
            "id": u.id,
            "title": script.title if script else "Unknown",
            "youtube_video_id": u.youtube_video_id or "",
        })

    comments = []
    if upload_id:
        comment_rows = (
            db.query(CommentReply)
            .filter(CommentReply.upload_id == upload_id)
            .order_by(desc(CommentReply.created_at))
            .all()
        )
        comments = [
            {
                "id": c.id,
                "author": c.author,
                "comment_text": c.comment_text,
                "suggested_reply": c.suggested_reply,
                "status": c.status,
                "created_at": str(c.created_at),
            }
            for c in comment_rows
        ]

    return templates.TemplateResponse("comments.html", {
        "request": request,
        "active": "comments",
        "uploads": upload_list,
        "selected_upload": upload_id,
        "comments": comments,
    })


@router.get("/ui/insights")
def insights_page(request: Request, db: Session = Depends(get_db)):
    top = get_top_scripts(db, limit=10)
    return templates.TemplateResponse("insights.html", {
        "request": request,
        "active": "insights",
        "scripts": top,
    })


@router.get("/ui/lineage/overview")
def lineage_overview(request: Request, db: Session = Depends(get_db)):
    from app.lineage.router import pipeline_stats as _pipeline_stats
    stats = _pipeline_stats(db)
    return templates.TemplateResponse("lineage.html", {
        "request": request,
        "active": "lineage",
        "mode": "overview",
        "stats": stats,
    })


@router.get("/ui/lineage/{entity_type}/{entity_id}")
def lineage_entity(entity_type: str, entity_id: str, request: Request, db: Session = Depends(get_db)):
    import json as _json
    from app.lineage.router import get_lineage as _get_lineage
    data = _get_lineage(entity_type, entity_id, db)
    if "error" in data:
        return templates.TemplateResponse("lineage.html", {
            "request": request, "active": "lineage", "mode": "overview",
            "stats": {"funnel": {"trends": 0, "briefs": 0, "scripts": 0, "uploads": 0},
                      "trend_sourced": {"count": 0, "avg_score": 0, "uploaded": 0},
                      "manual": {"count": 0, "avg_score": 0, "uploaded": 0},
                      "template_based": {"count": 0, "avg_score": 0, "uploaded": 0},
                      "freeform": {"count": 0, "avg_score": 0, "uploaded": 0},
                      "top_trends": [], "top_templates": []},
        })

    return templates.TemplateResponse("lineage.html", {
        "request": request,
        "active": "lineage",
        "mode": "entity",
        "entity": data.get("root", {}),
        "upstream": data.get("upstream", []),
        "downstream": data.get("downstream", []),
        "versions": data.get("versions", []),
        "lineage_stats": data.get("stats", {}),
        "lineage_json": _json.dumps(data).replace("</", "<\\/"),
    })


# ---- helpers to convert SQLAlchemy models to dicts for templates ----

def _brief_dict(b: ContentBrief) -> dict:
    return {
        "id": b.id,
        "topic": b.topic,
        "raw_brief": b.raw_brief,
        "suggestion_id": b.suggestion_id,
        "created_at": str(b.created_at) if b.created_at else "",
    }


def _script_dict(s: Script) -> dict:
    import json
    try:
        hashtags = json.loads(s.hashtags) if s.hashtags else []
    except (json.JSONDecodeError, TypeError):
        hashtags = []
    return {
        "id": s.id,
        "brief_id": s.brief_id,
        "angle": s.angle,
        "hook_type": s.hook_type,
        "platform": s.platform or "youtube_shorts",
        "duration": s.duration or "30s",
        "title": s.title,
        "hook": s.hook,
        "body": s.body,
        "cta": s.cta,
        "cta_goal": s.cta_goal,
        "hashtags": hashtags,
        "thumbnail_suggestion": s.thumbnail_suggestion,
        "predicted_performance": s.predicted_performance,
        "score": s.score,
        "template_id": s.template_id,
    }


def _suggestion_dict(s: TrendSuggestion) -> dict:
    return {
        "id": s.id,
        "keyword": s.keyword,
        "source": s.source,
        "trend_score": s.trend_score,
        "suggested_brief": s.suggested_brief,
        "status": s.status,
        "created_at": str(s.created_at) if s.created_at else "",
    }


def _template_dict(t) -> dict:
    import json
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description or "",
        "angle": t.angle,
        "hook_type": t.hook_type,
        "platform": t.platform or "youtube_shorts",
        "duration": t.duration or "30s",
        "cta_goal": t.cta_goal,
        "beat_structure": json.loads(t.beat_structure) if t.beat_structure else [],
        "source_script_id": t.source_script_id,
        "created_at": str(t.created_at) if t.created_at else "",
    }
