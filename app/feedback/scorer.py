from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models import Script, Upload, Analytics, ContentBrief, TrendSuggestion


def _engagement_rates(views: int, likes: int, comments: int) -> dict:
    """Calculate engagement rates as percentages."""
    if views == 0:
        return {"like_rate": 0, "comment_rate": 0, "engagement_rate": 0}
    return {
        "like_rate": round(likes / views * 100, 2),
        "comment_rate": round(comments / views * 100, 2),
        "engagement_rate": round((likes + comments) / views * 100, 2),
    }


def _get_script_analytics(db: Session, script_id: str) -> dict:
    """Get aggregated analytics for a script including watch time and CTR."""
    uploads = db.query(Upload).filter(
        Upload.script_id == script_id,
        Upload.upload_status.in_(["uploaded", "linked"]),
    ).all()

    total = {"watch_time_minutes": 0.0, "ctr": 0.0, "analytics_count": 0}
    for u in uploads:
        a = db.query(Analytics).filter(Analytics.upload_id == u.id).order_by(desc(Analytics.fetched_at)).first()
        if a:
            total["watch_time_minutes"] += a.watch_time_minutes or 0
            total["ctr"] += a.ctr or 0
            total["analytics_count"] += 1

    if total["analytics_count"] > 0:
        total["ctr"] = round(total["ctr"] / total["analytics_count"], 2)
    total["watch_time_minutes"] = round(total["watch_time_minutes"], 1)
    return total


def update_all_scores(db: Session) -> list[dict]:
    """Fetch analytics numbers and store them directly on scripts.
    Aggregates across all uploads for scripts with multiple videos."""
    uploads = db.query(Upload).filter(Upload.upload_status.in_(["uploaded", "linked"])).all()

    # Group uploads by script_id and aggregate analytics
    script_totals = {}  # script_id -> {views, likes, comments}
    for upload in uploads:
        latest_analytics = (
            db.query(Analytics)
            .filter(Analytics.upload_id == upload.id)
            .order_by(desc(Analytics.fetched_at))
            .first()
        )
        if not latest_analytics:
            continue

        sid = upload.script_id
        if sid not in script_totals:
            script_totals[sid] = {"views": 0, "likes": 0, "comments": 0}
        script_totals[sid]["views"] += latest_analytics.views or 0
        script_totals[sid]["likes"] += latest_analytics.likes or 0
        script_totals[sid]["comments"] += latest_analytics.comments or 0

    updated = []
    for sid, totals in script_totals.items():
        script = db.query(Script).filter(Script.id == sid).first()
        if not script:
            continue

        script.views = totals["views"]
        script.likes = totals["likes"]
        script.comments = totals["comments"]
        script.score = script.views + (script.likes * 10) + (script.comments * 20)

        updated.append({
            "script_id": script.id,
            "title": script.title,
            "views": script.views,
            "likes": script.likes,
            "comments": script.comments,
        })

    # Propagate scores up to trends via briefs
    # Sum all script scores per trend's briefs
    trends = db.query(TrendSuggestion).all()
    for trend in trends:
        briefs = db.query(ContentBrief).filter(ContentBrief.suggestion_id == trend.id).all()
        if not briefs:
            continue
        total = 0
        for b in briefs:
            brief_total = db.query(func.coalesce(func.sum(Script.score), 0)).filter(Script.brief_id == b.id).scalar()
            total += brief_total or 0
        trend.trend_score = total

    db.commit()
    return updated


def _script_to_dict(db: Session, s: Script) -> dict:
    """Convert a script to a dict with engagement rates and analytics."""
    rates = _engagement_rates(s.views, s.likes, s.comments)
    analytics = _get_script_analytics(db, s.id)
    return {
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
        "platform": s.platform or "youtube_shorts",
        "duration": s.duration or "30s",
        "created_by": s.created_by,
    }


def get_top_scripts(db: Session, limit: int = 10) -> list[dict]:
    """Get top scripts by score."""
    scripts = (
        db.query(Script)
        .filter(Script.score > 0)
        .order_by(desc(Script.score))
        .limit(limit)
        .all()
    )
    return [_script_to_dict(db, s) for s in scripts]


def get_bottom_scripts(db: Session, limit: int = 10) -> list[dict]:
    """Get worst performing scripts by score."""
    scripts = (
        db.query(Script)
        .filter(Script.score > 0)
        .order_by(Script.score)
        .limit(limit)
        .all()
    )
    return [_script_to_dict(db, s) for s in scripts]


def get_heatmap_data(db: Session) -> dict:
    """Build angle x hook_type performance heatmap."""
    scored = db.query(Script).filter(Script.score > 0).all()
    if not scored:
        return {"angles": [], "hooks": [], "cells": []}

    # Collect all angles and hooks
    angles = sorted(set(s.angle for s in scored))
    hooks = sorted(set(s.hook_type for s in scored))

    # Build grid: {(angle, hook): [engagement_rates]}
    grid = {}
    for s in scored:
        key = (s.angle, s.hook_type)
        rates = _engagement_rates(s.views, s.likes, s.comments)
        grid.setdefault(key, []).append({
            "score": s.score,
            "engagement_rate": rates["engagement_rate"],
            "views": s.views,
        })

    cells = []
    for angle in angles:
        for hook in hooks:
            entries = grid.get((angle, hook), [])
            if entries:
                avg_score = round(sum(e["score"] for e in entries) / len(entries), 1)
                avg_engagement = round(sum(e["engagement_rate"] for e in entries) / len(entries), 2)
                total_views = sum(e["views"] for e in entries)
                cells.append({
                    "angle": angle,
                    "hook": hook,
                    "count": len(entries),
                    "avg_score": avg_score,
                    "avg_engagement": avg_engagement,
                    "total_views": total_views,
                })
            else:
                cells.append({
                    "angle": angle,
                    "hook": hook,
                    "count": 0,
                    "avg_score": 0,
                    "avg_engagement": 0,
                    "total_views": 0,
                })

    return {"angles": angles, "hooks": hooks, "cells": cells}


def get_performance_insights(db: Session) -> dict:
    """Aggregate performance insights by angle, hook type, and CTA goal."""
    scored = db.query(Script).filter(Script.score > 0).all()
    if not scored:
        return {"message": "No scored scripts yet. Link videos and update scores first."}

    def _aggregate(key_fn):
        buckets = {}
        for s in scored:
            k = key_fn(s)
            rates = _engagement_rates(s.views, s.likes, s.comments)
            buckets.setdefault(k, []).append({
                "score": s.score,
                "engagement_rate": rates["engagement_rate"],
            })
        return {
            k: {
                "avg_score": round(sum(e["score"] for e in v) / len(v), 1),
                "avg_engagement": round(sum(e["engagement_rate"] for e in v) / len(v), 2),
                "count": len(v),
            }
            for k, v in buckets.items()
        }

    by_angle = _aggregate(lambda s: s.angle)
    by_hook = _aggregate(lambda s: s.hook_type)
    by_cta = _aggregate(lambda s: s.cta_goal)

    best_angle = max(by_angle, key=lambda k: by_angle[k]["avg_score"])
    best_hook = max(by_hook, key=lambda k: by_hook[k]["avg_score"])

    return {
        "total_scored": len(scored),
        "best_angle": best_angle,
        "best_hook": best_hook,
        "by_angle": by_angle,
        "by_hook_type": by_hook,
        "by_cta_goal": by_cta,
    }
