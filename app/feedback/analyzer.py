from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Script
from app.feedback.scorer import get_top_scripts


def generate_weekly_report(db: Session) -> dict:
    """Generate a weekly performance analysis report using AI."""
    top = get_top_scripts(db, limit=10)

    if not top:
        return {"message": "No scored scripts yet. Link videos and update scores first."}

    from app.ai_client import generate_json

    top_text = "\n".join(
        f"- [{s['angle']}/{s['hook_type']}] \"{s['title']}\" — views: {s['views']}, likes: {s['likes']}, comments: {s['comments']}"
        for s in top
    )

    bottom_scripts = (
        db.query(Script)
        .filter(Script.score > 0)
        .order_by(Script.score)
        .limit(5)
        .all()
    )
    bottom_text = "\n".join(
        f"- [{s.angle}/{s.hook_type}] \"{s.title}\" — views: {s.views}, likes: {s.likes}, comments: {s.comments}"
        for s in bottom_scripts
    )

    prompt = f"""Analyze this content performance data and generate actionable insights.

TOP PERFORMING SCRIPTS:
{top_text}

WORST PERFORMING SCRIPTS:
{bottom_text}

Generate a report with:
1. summary: 2-3 sentence executive summary
2. winning_patterns: What angles, hooks, and CTAs are working and why
3. losing_patterns: What to avoid and why
4. recommendations: 3-5 specific actionable recommendations for next week's content
5. suggested_briefs: 3 content brief ideas based on what's working

Respond ONLY with valid JSON."""

    return generate_json(prompt, max_tokens=2048, temperature=0.7)
