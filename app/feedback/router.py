from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.feedback.scorer import update_all_scores, get_top_scripts
from app.feedback.analyzer import generate_weekly_report

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/update-scores")
def update_scores(db: Session = Depends(get_db)):
    updated = update_all_scores(db)
    return {"updated": len(updated), "scripts": updated}


@router.get("/insights")
def insights(db: Session = Depends(get_db)):
    return {"scripts": get_top_scripts(db)}


@router.get("/report")
def weekly_report(db: Session = Depends(get_db)):
    return generate_weekly_report(db)
