from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.feedback.scorer import update_all_scores, get_top_scripts, get_bottom_scripts, get_heatmap_data
from app.feedback.analyzer import generate_weekly_report
from app.auth.dependencies import get_current_user_api

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/update-scores")
def update_scores(db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    updated = update_all_scores(db)
    return {"updated": len(updated), "scripts": updated}


@router.get("/insights")
def insights(db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    return {"scripts": get_top_scripts(db), "bottom": get_bottom_scripts(db), "heatmap": get_heatmap_data(db)}


@router.get("/report")
def weekly_report(db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    return generate_weekly_report(db)
