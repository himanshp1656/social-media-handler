from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.models import ContentBrief, Script, Beat, Upload, Analytics, TrendSuggestion, ScheduledPost, CommentReply, User, Team, new_id
from app.feedback.scorer import get_top_scripts, get_bottom_scripts, get_heatmap_data, _engagement_rates, _get_script_analytics
from app.youtube.auth import is_authenticated
from app.auth.dependencies import get_current_user


def _team_filter(query, model, user):
    """Apply team_id filter based on user's active team."""
    if user.active_team_id and hasattr(model, 'team_id'):
        return query.filter(model.team_id == user.active_team_id)
    return query


def _all_teams(db: Session) -> list[dict]:
    """Get all teams for the team switcher."""
    teams = db.query(Team).order_by(Team.name).all()
    return [{"id": t.id, "name": t.name} for t in teams]


def _active_team_name(db: Session, user: User) -> str:
    """Get active team name."""
    if not user.active_team_id:
        return "No Team"
    team = db.query(Team).filter(Team.id == user.active_team_id).first()
    return team.name if team else "No Team"

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory="templates")


def _user_map(db: Session) -> dict:
    """Build {user_id: display_name} lookup for attribution badges."""
    users = db.query(User).all()
    return {u.id: u.display_name for u in users}


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    briefs = _team_filter(db.query(ContentBrief), ContentBrief, user).order_by(desc(ContentBrief.created_at)).limit(5).all()
    suggestions = _team_filter(db.query(TrendSuggestion), TrendSuggestion, user).order_by(desc(TrendSuggestion.created_at)).limit(5).all()
    umap = _user_map(db)

    tid = user.active_team_id
    brief_q = db.query(func.count(ContentBrief.id))
    script_q = db.query(func.count(Script.id))
    upload_q = db.query(func.count(Upload.id)).filter(Upload.upload_status == "uploaded")
    suggest_q = db.query(func.count(TrendSuggestion.id))
    if tid:
        brief_q = brief_q.filter(ContentBrief.team_id == tid)
        script_q = script_q.filter(Script.team_id == tid)
        upload_q = upload_q.filter(Upload.team_id == tid)
        suggest_q = suggest_q.filter(TrendSuggestion.team_id == tid)
    stats = {
        "briefs": brief_q.scalar() or 0,
        "scripts": script_q.scalar() or 0,
        "uploads": upload_q.scalar() or 0,
        "suggestions": suggest_q.scalar() or 0,
    }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active": "dashboard",
        "current_user": user,
        "user_map": umap,
        "stats": stats,
        "briefs": [_brief_dict(b) for b in briefs],
        "suggestions": [_suggestion_dict(s) for s in suggestions],
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.get("/ui/generate")
def generate_page(request: Request, brief: str = "", template_id: str = "", suggestion_id: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    template = None
    if template_id:
        from app.models import ScriptTemplate
        tpl = db.query(ScriptTemplate).filter(ScriptTemplate.id == template_id).first()
        if tpl:
            template = _template_dict(tpl)
    return templates.TemplateResponse("generate.html", {
        "request": request,
        "active": "generate",
        "current_user": user,
        "prefill": brief,
        "template": template,
        "suggestion_id": suggestion_id,
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.get("/ui/batch")
def batch_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return templates.TemplateResponse("batch.html", {
        "request": request,
        "active": "batch",
        "current_user": user,
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.get("/ui/templates")
def templates_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models import ScriptTemplate
    tpls = _team_filter(db.query(ScriptTemplate), ScriptTemplate, user).order_by(desc(ScriptTemplate.created_at)).all()
    umap = _user_map(db)
    return templates.TemplateResponse("templates.html", {
        "request": request,
        "active": "templates",
        "current_user": user,
        "user_map": umap,
        "templates": [_template_dict(t) for t in tpls],
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.get("/ui/briefs")
def briefs_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    briefs = _team_filter(db.query(ContentBrief), ContentBrief, user).order_by(desc(ContentBrief.created_at)).limit(50).all()
    umap = _user_map(db)
    return templates.TemplateResponse("briefs.html", {
        "request": request,
        "active": "briefs",
        "current_user": user,
        "user_map": umap,
        "briefs": [_brief_dict(b) for b in briefs],
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.get("/ui/briefs/{brief_id}")
def brief_detail_page(brief_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    brief = db.query(ContentBrief).filter(ContentBrief.id == brief_id).first()
    if not brief:
        return templates.TemplateResponse("briefs.html", {
            "request": request,
            "active": "briefs",
            "current_user": user,
            "briefs": [],
            "teams": _all_teams(db),
            "active_team_name": _active_team_name(db, user),
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

    # Build comparison data for scripts with analytics
    comparison = []
    for s in scripts:
        rates = _engagement_rates(s.views, s.likes, s.comments)
        analytics = _get_script_analytics(db, s.id)
        comparison.append({
            "id": s.id,
            "title": s.title,
            "angle": s.angle,
            "hook_type": s.hook_type,
            "cta_goal": s.cta_goal,
            "views": s.views,
            "likes": s.likes,
            "comments": s.comments,
            "score": s.score,
            "like_rate": rates["like_rate"],
            "comment_rate": rates["comment_rate"],
            "engagement_rate": rates["engagement_rate"],
            "watch_time_minutes": analytics["watch_time_minutes"],
            "ctr": analytics["ctr"],
        })

    umap = _user_map(db)
    return templates.TemplateResponse("brief_detail.html", {
        "request": request,
        "active": "briefs",
        "current_user": user,
        "user_map": umap,
        "brief": _brief_dict(brief),
        "scripts": [_script_dict(s) for s in scripts],
        "comparison": comparison,
        "beats_map": beats_map,
        "upload_map": upload_map,
        "youtube_authenticated": is_authenticated(),
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.get("/ui/teleprompter/{script_id}")
def teleprompter_page(script_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        return templates.TemplateResponse("briefs.html", {"request": request, "active": "briefs", "current_user": user, "briefs": [], "teams": _all_teams(db), "active_team_name": _active_team_name(db, user)})

    beats = db.query(Beat).filter(Beat.script_id == script_id).order_by(Beat.beat_number).all()
    return templates.TemplateResponse("teleprompter.html", {
        "request": request,
        "current_user": user,
        "script": _script_dict(script),
        "beats": [
            {"type": b.beat_type, "timestamp": b.timestamp, "duration_seconds": b.duration_seconds,
             "voiceover": b.voiceover, "on_screen_text": b.on_screen_text, "visual_cue": b.visual_cue, "camera": b.camera}
            for b in beats
        ],
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.get("/ui/trends")
def trends_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    suggestions = _team_filter(db.query(TrendSuggestion), TrendSuggestion, user).order_by(desc(TrendSuggestion.created_at)).limit(30).all()
    return templates.TemplateResponse("trends.html", {
        "request": request,
        "active": "trends",
        "current_user": user,
        "suggestions": [_suggestion_dict(s) for s in suggestions],
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.get("/ui/calendar")
def calendar_page(request: Request, date: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
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

    pq = db.query(ScheduledPost).filter(ScheduledPost.scheduled_at >= first_day).filter(ScheduledPost.scheduled_at <= last_day)
    if user.active_team_id:
        pq = pq.filter(ScheduledPost.team_id == user.active_team_id)
    posts = pq.order_by(ScheduledPost.scheduled_at).all()

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

    scripts = _team_filter(db.query(Script), Script, user).order_by(desc(Script.created_at)).limit(50).all()

    return templates.TemplateResponse("calendar.html", {
        "request": request,
        "active": "calendar",
        "current_user": user,
        "grid": grid,
        "month_name": first_day.strftime("%B %Y"),
        "prev_month": prev_month_date.strftime("%Y-%m-%d"),
        "next_month": next_month_date.strftime("%Y-%m-%d"),
        "scripts": [_script_dict(s) for s in scripts],
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.get("/ui/comments")
def comments_page(request: Request, upload_id: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    uq = db.query(Upload).filter(Upload.upload_status.in_(["uploaded", "linked"]))
    if user.active_team_id:
        uq = uq.filter(Upload.team_id == user.active_team_id)
    uploads = uq.all()
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
        "current_user": user,
        "uploads": upload_list,
        "selected_upload": upload_id,
        "comments": comments,
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.get("/ui/insights")
def insights_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    import json as _json
    top = get_top_scripts(db, limit=10)
    bottom = get_bottom_scripts(db, limit=10)
    heatmap = get_heatmap_data(db)
    umap = _user_map(db)
    return templates.TemplateResponse("insights.html", {
        "request": request,
        "active": "insights",
        "current_user": user,
        "user_map": umap,
        "scripts": top,
        "bottom_scripts": bottom,
        "heatmap_json": _json.dumps(heatmap),
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.get("/ui/lineage/overview")
def lineage_overview(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    import json as _json
    # Build full graph: ScriptLab -> Trends -> Briefs -> Scripts -> Uploads
    # Briefs without a trend connect directly to ScriptLab
    briefs_all = _team_filter(db.query(ContentBrief), ContentBrief, user).all()

    # Compute total score per brief for sorting
    brief_scores = {}
    for b in briefs_all:
        total = db.query(func.coalesce(func.sum(Script.score), 0)).filter(Script.brief_id == b.id).scalar()
        brief_scores[b.id] = total or 0

    def _build_brief_node(b):
        b_node = {
            "type": "brief", "id": b.id,
            "label": b.raw_brief[:80],
            "topic": b.topic,
            "suggestion_id": b.suggestion_id,
            "created_at": str(b.created_at) if b.created_at else "",
            "total_score": brief_scores[b.id],
            "children": [],
        }
        scripts = db.query(Script).filter(Script.brief_id == b.id).order_by(desc(Script.score)).all()
        for s in scripts:
            s_node = {
                "type": "script", "id": s.id,
                "label": s.title, "brief_id": s.brief_id,
                "angle": s.angle, "hook_type": s.hook_type,
                "score": s.score or 0, "platform": s.platform,
                "duration": s.duration, "template_id": s.template_id,
                "children": [],
            }
            uploads = db.query(Upload).filter(Upload.script_id == s.id).all()
            for u in uploads:
                a = db.query(Analytics).filter(Analytics.upload_id == u.id).order_by(desc(Analytics.fetched_at)).first()
                u_node = {
                    "type": "upload", "id": u.id,
                    "label": u.youtube_video_id or "pending",
                    "status": u.upload_status,
                    "platform": s.platform or "youtube_shorts",
                    "views": a.views if a else 0,
                    "likes": a.likes if a else 0,
                    "comments": a.comments if a else 0,
                    "ctr": a.ctr if a else 0,
                    "watch_time_minutes": (a.watch_time_minutes or 0) if a else 0,
                    "children": [],
                }
                s_node["children"].append(u_node)
            b_node["children"].append(s_node)
        return b_node

    # Group briefs by suggestion_id
    trend_briefs = {}  # suggestion_id -> [briefs]
    manual_briefs = []
    for b in briefs_all:
        if b.suggestion_id:
            trend_briefs.setdefault(b.suggestion_id, []).append(b)
        else:
            manual_briefs.append(b)

    # Build all downstream nodes (trends + manual briefs) with their total scores
    # so we can sort them together by score
    downstream_items = []  # [(total_score, node)]

    suggestion_ids = list(trend_briefs.keys())
    if suggestion_ids:
        trends = db.query(TrendSuggestion).filter(TrendSuggestion.id.in_(suggestion_ids)).all()
        trend_map = {t.id: t for t in trends}
        for sid in suggestion_ids:
            t = trend_map.get(sid)
            if not t:
                manual_briefs.extend(trend_briefs[sid])
                continue
            t_node = {
                "type": "trend", "id": t.id,
                "label": t.keyword,
                "source": t.source,
                "score": t.trend_score,
                "brief": t.suggested_brief,
                "status": t.status,
                "children": [],
            }
            total = 0
            for b in sorted(trend_briefs[sid], key=lambda b: brief_scores.get(b.id, 0), reverse=True):
                t_node["children"].append(_build_brief_node(b))
                total += brief_scores.get(b.id, 0)
            downstream_items.append((total, t_node))

    for b in manual_briefs:
        downstream_items.append((brief_scores.get(b.id, 0), _build_brief_node(b)))

    # Sort all top-level nodes by total score descending
    downstream_items.sort(key=lambda x: x[0], reverse=True)

    root = {"type": "scriptlab", "id": "scriptlab", "label": "ScriptLab"}
    downstream = [item[1] for item in downstream_items]

    data = {"root": root, "upstream": [], "downstream": downstream, "versions": [], "stats": {}}

    return templates.TemplateResponse("lineage.html", {
        "request": request,
        "active": "lineage",
        "current_user": user,
        "mode": "entity",
        "entity": root,
        "upstream": [],
        "downstream": downstream,
        "versions": [],
        "lineage_stats": {},
        "lineage_json": _json.dumps(data).replace("</", "<\\/"),
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.get("/ui/lineage/{entity_type}/{entity_id}")
def lineage_entity(entity_type: str, entity_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    import json as _json
    from app.lineage.router import get_lineage as _get_lineage
    data = _get_lineage(entity_type, entity_id, db, user)
    if "error" in data:
        import json as _json2
        fallback = {"root": {"type": "scriptlab", "id": "scriptlab", "label": "ScriptLab"}, "upstream": [], "downstream": [], "versions": [], "stats": {}}
        return templates.TemplateResponse("lineage.html", {
            "request": request, "active": "lineage", "current_user": user, "mode": "entity",
            "entity": fallback["root"], "upstream": [], "downstream": [], "versions": [], "lineage_stats": {},
            "lineage_json": _json2.dumps(fallback),
            "teams": _all_teams(db),
            "active_team_name": _active_team_name(db, user),
        })

    return templates.TemplateResponse("lineage.html", {
        "request": request,
        "active": "lineage",
        "current_user": user,
        "mode": "entity",
        "entity": data.get("root", {}),
        "upstream": data.get("upstream", []),
        "downstream": data.get("downstream", []),
        "versions": data.get("versions", []),
        "lineage_stats": data.get("stats", {}),
        "lineage_json": _json.dumps(data).replace("</", "<\\/"),
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


# ---- Team create ----

@router.get("/ui/team/create")
def team_create_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return templates.TemplateResponse("team_create.html", {
        "request": request,
        "current_user": user,
        "error": None,
        "teams": _all_teams(db),
        "active_team_name": _active_team_name(db, user),
    })


@router.post("/ui/team/create")
def team_create(
    request: Request,
    team_name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    name = team_name.strip()
    if not name:
        return templates.TemplateResponse("team_create.html", {
            "request": request,
            "current_user": user,
            "error": "Team name is required",
            "teams": _all_teams(db),
            "active_team_name": _active_team_name(db, user),
        })

    team = Team(id=new_id(), name=name, created_by=user.id)
    db.add(team)
    user.active_team_id = team.id
    db.commit()
    return RedirectResponse(url="/", status_code=302)


# ---- helpers to convert SQLAlchemy models to dicts for templates ----

def _brief_dict(b: ContentBrief) -> dict:
    return {
        "id": b.id,
        "topic": b.topic,
        "raw_brief": b.raw_brief,
        "suggestion_id": b.suggestion_id,
        "created_by": b.created_by,
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
        "created_by": s.created_by,
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
