from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models import Script, Upload, Analytics


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

    db.commit()
    return updated


def get_top_scripts(db: Session, limit: int = 10) -> list[dict]:
    """Get top scripts by views."""
    scripts = (
        db.query(Script)
        .filter(Script.score > 0)
        .order_by(desc(Script.score))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "title": s.title,
            "angle": s.angle,
            "hook_type": s.hook_type,
            "views": s.views,
            "likes": s.likes,
            "comments": s.comments,
            "platform": s.platform or "youtube_shorts",
            "duration": s.duration or "30s",
        }
        for s in scripts
    ]


def get_performance_insights(db: Session) -> dict:
    """Aggregate performance insights by angle, hook type, and CTA goal."""
    scored = db.query(Script).filter(Script.score > 0).all()
    if not scored:
        return {"message": "No scored scripts yet. Link videos and update scores first."}

    def _aggregate(key_fn):
        buckets = {}
        for s in scored:
            k = key_fn(s)
            buckets.setdefault(k, []).append(s.score)
        return {
            k: {"avg_score": round(sum(v) / len(v), 1), "count": len(v)}
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
