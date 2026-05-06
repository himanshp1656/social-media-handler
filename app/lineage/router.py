from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models import (
    TrendSuggestion, ContentBrief, Script, Beat, Upload, Analytics,
    ScriptTemplate, ScheduledPost, ScriptVersion, User,
)
from app.auth.dependencies import get_current_user_api

router = APIRouter(prefix="/lineage", tags=["lineage"])


def _trend_node(t):
    return {"type": "trend", "id": t.id, "label": t.keyword, "brief": t.suggested_brief, "score": t.trend_score, "source": t.source, "status": t.status}


def _brief_node(b):
    return {"type": "brief", "id": b.id, "label": b.raw_brief[:80], "topic": b.topic, "suggestion_id": b.suggestion_id, "created_at": str(b.created_at) if b.created_at else ""}


def _script_node(s):
    return {"type": "script", "id": s.id, "label": s.title, "brief_id": s.brief_id, "angle": s.angle, "hook_type": s.hook_type, "score": s.score, "platform": s.platform, "duration": s.duration, "template_id": s.template_id}


def _upload_node(u):
    return {"type": "upload", "id": u.id, "label": u.youtube_video_id or "pending", "status": u.upload_status}


def _analytics_node(a):
    return {"type": "analytics", "id": a.id, "label": f"{a.views} views", "views": a.views, "likes": a.likes, "comments": a.comments, "ctr": a.ctr}


def _template_node(t):
    return {"type": "template", "id": t.id, "label": t.name, "angle": t.angle, "hook_type": t.hook_type}


def _get_downstream_from_brief(db: Session, brief_id: str):
    """Get all downstream entities from a brief."""
    scripts = db.query(Script).filter(Script.brief_id == brief_id).all()
    script_nodes = []
    total_views = 0
    best_script = None

    for s in scripts:
        node = _script_node(s)
        node["children"] = []

        # Template reference
        if s.template_id:
            tpl = db.query(ScriptTemplate).filter(ScriptTemplate.id == s.template_id).first()
            if tpl:
                node["template"] = _template_node(tpl)

        # Uploads
        uploads = db.query(Upload).filter(Upload.script_id == s.id).all()
        for u in uploads:
            u_node = _upload_node(u)
            u_node["children"] = []
            analytics = db.query(Analytics).filter(Analytics.upload_id == u.id).order_by(desc(Analytics.fetched_at)).first()
            if analytics:
                u_node["children"].append(_analytics_node(analytics))
                total_views += analytics.views or 0
            node["children"].append(u_node)

        # Track best
        if best_script is None or s.score > best_script.score:
            best_script = s

        script_nodes.append(node)

    stats = {
        "total_scripts": len(scripts),
        "uploaded": sum(1 for s in script_nodes if s["children"]),
        "total_views": total_views,
    }
    if best_script:
        stats["best_script"] = {"id": best_script.id, "title": best_script.title, "score": best_script.score}

    return script_nodes, stats


@router.get("/{entity_type}/{entity_id}")
def get_lineage(entity_type: str, entity_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """Get full upstream + downstream lineage graph for any entity."""

    if entity_type == "brief":
        brief = db.query(ContentBrief).filter(ContentBrief.id == entity_id).first()
        if not brief:
            return {"error": "Brief not found"}

        root = _brief_node(brief)
        upstream = []
        if brief.suggestion_id:
            trend = db.query(TrendSuggestion).filter(TrendSuggestion.id == brief.suggestion_id).first()
            if trend:
                upstream.append(_trend_node(trend))

        downstream, stats = _get_downstream_from_brief(db, brief.id)
        return {"root": root, "upstream": upstream, "downstream": downstream, "stats": stats}

    elif entity_type == "script":
        script = db.query(Script).filter(Script.id == entity_id).first()
        if not script:
            return {"error": "Script not found"}

        root = _script_node(script)

        # Upstream: brief (with sibling scripts as children), then optionally trend
        upstream = []
        brief = db.query(ContentBrief).filter(ContentBrief.id == script.brief_id).first()
        if brief:
            brief_node = _brief_node(brief)
            # Include sibling scripts so the graph can show them via expand
            siblings = db.query(Script).filter(Script.brief_id == brief.id, Script.id != script.id).all()
            sibling_nodes = []
            for s in siblings:
                s_node = _script_node(s)
                # Include each sibling's uploads
                s_uploads = db.query(Upload).filter(Upload.script_id == s.id).all()
                s_node["children"] = []
                for u in s_uploads:
                    su_node = _upload_node(u)
                    su_node["children"] = []
                    a = db.query(Analytics).filter(Analytics.upload_id == u.id).order_by(desc(Analytics.fetched_at)).first()
                    if a:
                        su_node["children"].append(_analytics_node(a))
                    s_node["children"].append(su_node)
                sibling_nodes.append(s_node)
            brief_node["children"] = sibling_nodes
            upstream.append(brief_node)
            if brief.suggestion_id:
                trend = db.query(TrendSuggestion).filter(TrendSuggestion.id == brief.suggestion_id).first()
                if trend:
                    upstream.append(_trend_node(trend))

        # Template
        if script.template_id:
            tpl = db.query(ScriptTemplate).filter(ScriptTemplate.id == script.template_id).first()
            if tpl:
                root["template"] = _template_node(tpl)

        # Downstream: uploads + analytics
        downstream = []
        uploads = db.query(Upload).filter(Upload.script_id == script.id).all()
        for u in uploads:
            u_node = _upload_node(u)
            u_node["children"] = []
            analytics = db.query(Analytics).filter(Analytics.upload_id == u.id).order_by(desc(Analytics.fetched_at)).first()
            if analytics:
                u_node["children"].append(_analytics_node(analytics))
            downstream.append(u_node)

        # Versions
        versions = (
            db.query(ScriptVersion)
            .filter(ScriptVersion.script_id == script.id)
            .order_by(desc(ScriptVersion.version_number))
            .all()
        )
        version_list = [
            {"version": v.version_number, "change_type": v.change_type, "title": v.title, "created_at": str(v.created_at)}
            for v in versions
        ]

        return {"root": root, "upstream": upstream, "downstream": downstream, "versions": version_list, "stats": {}}

    elif entity_type == "trend":
        trend = db.query(TrendSuggestion).filter(TrendSuggestion.id == entity_id).first()
        if not trend:
            return {"error": "Trend not found"}

        root = _trend_node(trend)

        # Find all briefs sourced from this trend
        briefs = db.query(ContentBrief).filter(ContentBrief.suggestion_id == trend.id).all()
        downstream = []
        total_views = 0
        total_scripts = 0
        for b in briefs:
            b_node = _brief_node(b)
            scripts, stats = _get_downstream_from_brief(db, b.id)
            b_node["children"] = scripts
            total_views += stats.get("total_views", 0)
            total_scripts += stats.get("total_scripts", 0)
            downstream.append(b_node)

        stats = {"total_briefs": len(briefs), "total_scripts": total_scripts, "total_views": total_views}
        return {"root": root, "upstream": [], "downstream": downstream, "stats": stats}

    elif entity_type == "template":
        tpl = db.query(ScriptTemplate).filter(ScriptTemplate.id == entity_id).first()
        if not tpl:
            return {"error": "Template not found"}

        root = _template_node(tpl)

        # Upstream: source script
        upstream = []
        if tpl.source_script_id:
            source = db.query(Script).filter(Script.id == tpl.source_script_id).first()
            if source:
                upstream.append(_script_node(source))

        # Downstream: scripts generated from this template
        scripts = db.query(Script).filter(Script.template_id == tpl.id).all()
        downstream = [_script_node(s) for s in scripts]

        stats = {"scripts_generated": len(scripts), "avg_score": round(sum(s.score for s in scripts) / len(scripts), 1) if scripts else 0}
        return {"root": root, "upstream": upstream, "downstream": downstream, "stats": stats}

    return {"error": f"Unknown entity type: {entity_type}"}


@router.get("/stats/pipeline")
def pipeline_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """Aggregate pipeline stats: trend vs manual, template vs freeform."""
    total_trends = db.query(func.count(TrendSuggestion.id)).scalar() or 0
    total_briefs = db.query(func.count(ContentBrief.id)).scalar() or 0
    total_scripts = db.query(func.count(Script.id)).scalar() or 0
    total_uploads = db.query(func.count(Upload.id)).filter(Upload.upload_status.in_(["uploaded", "linked"])).scalar() or 0

    # Trend-sourced vs manual briefs
    trend_briefs = db.query(ContentBrief).filter(ContentBrief.suggestion_id.isnot(None)).all()
    trend_brief_ids = {b.id for b in trend_briefs}
    manual_brief_ids = {b.id for b in db.query(ContentBrief).filter(ContentBrief.suggestion_id.is_(None)).all()}

    trend_scripts = db.query(Script).filter(Script.brief_id.in_(trend_brief_ids)).all() if trend_brief_ids else []
    manual_scripts = db.query(Script).filter(Script.brief_id.in_(manual_brief_ids)).all() if manual_brief_ids else []

    # Template vs freeform
    template_scripts = db.query(Script).filter(Script.template_id.isnot(None)).all()
    freeform_scripts = db.query(Script).filter(Script.template_id.is_(None)).all()

    def _path_stats(scripts):
        if not scripts:
            return {"count": 0, "avg_score": 0, "uploaded": 0}
        scored = [s for s in scripts if s.score > 0]
        script_ids = [s.id for s in scripts]
        uploaded = db.query(func.count(Upload.id)).filter(Upload.script_id.in_(script_ids), Upload.upload_status.in_(["uploaded", "linked"])).scalar() or 0
        return {
            "count": len(scripts),
            "avg_score": round(sum(s.score for s in scored) / len(scored), 1) if scored else 0,
            "uploaded": uploaded,
        }

    # Top performing trends
    top_trends = []
    trend_suggestions = db.query(TrendSuggestion).filter(TrendSuggestion.status == "used").order_by(desc(TrendSuggestion.trend_score)).limit(5).all()
    for t in trend_suggestions:
        briefs = db.query(ContentBrief).filter(ContentBrief.suggestion_id == t.id).all()
        brief_ids = [b.id for b in briefs]
        scripts = db.query(Script).filter(Script.brief_id.in_(brief_ids)).all() if brief_ids else []
        total_score = sum(s.score for s in scripts)
        top_trends.append({"id": t.id, "keyword": t.keyword, "brief_count": len(briefs), "total_score": total_score})

    # Top performing templates
    top_templates = []
    templates = db.query(ScriptTemplate).all()
    for tpl in templates:
        scripts = db.query(Script).filter(Script.template_id == tpl.id).all()
        if scripts:
            avg = round(sum(s.score for s in scripts) / len(scripts), 1)
            top_templates.append({"id": tpl.id, "name": tpl.name, "script_count": len(scripts), "avg_score": avg})
    top_templates.sort(key=lambda x: x["avg_score"], reverse=True)

    # Conversion funnel
    funnel = {
        "trends": total_trends,
        "briefs": total_briefs,
        "scripts": total_scripts,
        "uploads": total_uploads,
    }

    return {
        "funnel": funnel,
        "trend_sourced": _path_stats(trend_scripts),
        "manual": _path_stats(manual_scripts),
        "template_based": _path_stats(template_scripts),
        "freeform": _path_stats(freeform_scripts),
        "top_trends": top_trends[:5],
        "top_templates": top_templates[:5],
    }
