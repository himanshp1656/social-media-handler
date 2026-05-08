from sqlalchemy.orm import Session

from app.models import TrendSuggestion, new_id
from app.trends.news import fetch_finance_news, fetch_top_headlines


def _generate_briefs_from_news(news: list[dict]) -> list[dict]:
    """Use AI to turn recent news into content brief suggestions."""
    from app.ai_client import generate_json

    news_text = "\n".join(
        f"- {n['title']} ({n['source']})"
        for n in news[:15]
    )

    prompt = f"""You are a finance content strategist for YouTube. Given recent news, suggest content brief ideas that would go viral.

RECENT NEWS:
{news_text}

For each suggestion, provide:
1. keyword: The main keyword/topic
2. source: "news_api"
3. trend_score: 0-100 how likely this will perform well
4. suggested_brief: A 1-2 sentence content brief topic (NOT instructions like "Produce a video" or "Create a video" — just the topic and angle, e.g. "Why RBI's new FD rules could double your returns in 2026")

Generate 5-8 suggestions. Focus on topics with high viral potential in the Indian finance space.

Respond ONLY with a valid JSON array. No markdown, no explanation."""

    return generate_json(prompt, max_tokens=2048, temperature=0.7)


def suggest_content(db: Session, team_id: str | None = None) -> list[dict]:
    """Pull news, generate content suggestions, save to DB."""
    news = fetch_finance_news()
    headlines = fetch_top_headlines()
    all_news = news + headlines
    suggestions = _generate_briefs_from_news(all_news)

    saved = []
    for s in suggestions:
        suggestion = TrendSuggestion(
            id=new_id(),
            keyword=s["keyword"],
            source=s.get("source", "news_api"),
            trend_score=float(s.get("trend_score", 50)),
            suggested_brief=s["suggested_brief"],
            team_id=team_id,
        )
        db.add(suggestion)
        saved.append({
            "id": suggestion.id,
            "keyword": suggestion.keyword,
            "source": suggestion.source,
            "trend_score": suggestion.trend_score,
            "suggested_brief": suggestion.suggested_brief,
            "status": suggestion.status,
        })

    db.commit()
    return saved
