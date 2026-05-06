from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import TrendSuggestion, User
from app.trends.suggester import suggest_content
from app.trends.news import fetch_finance_news
from app.auth.dependencies import get_current_user_api

router = APIRouter(prefix="/trends", tags=["trends"])


@router.post("/suggest")
def suggest(db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    suggestions = suggest_content(db)
    return {"count": len(suggestions), "suggestions": suggestions}


@router.get("/suggestions")
def list_suggestions(db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    suggestions = (
        db.query(TrendSuggestion)
        .order_by(desc(TrendSuggestion.created_at))
        .limit(20)
        .all()
    )
    return [
        {
            "id": s.id,
            "keyword": s.keyword,
            "source": s.source,
            "trend_score": s.trend_score,
            "suggested_brief": s.suggested_brief,
            "status": s.status,
            "created_at": str(s.created_at),
        }
        for s in suggestions
    ]


@router.patch("/suggestions/{suggestion_id}")
def update_suggestion_status(suggestion_id: str, status: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    suggestion = db.query(TrendSuggestion).filter(TrendSuggestion.id == suggestion_id).first()
    if not suggestion:
        return {"error": "Suggestion not found"}
    suggestion.status = status
    db.commit()
    return {"id": suggestion.id, "status": suggestion.status}


@router.get("/news")
def latest_news(user: User = Depends(get_current_user_api)):
    news = fetch_finance_news()
    return {"count": len(news), "articles": news}
