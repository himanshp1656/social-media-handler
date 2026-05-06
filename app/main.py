from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

from app.database import init_db, SessionLocal
from app.scripts.router import router as scripts_router
from app.youtube.router import router as youtube_router
from app.trends.router import router as trends_router
from app.feedback.router import router as feedback_router
from app.calendar.router import router as calendar_router
from app.comments.router import router as comments_router
from app.lineage.router import router as lineage_router
from app.ui.router import router as ui_router
from app.youtube.analytics import fetch_all_analytics
from app.feedback.scorer import update_all_scores
from app.calendar.poster import process_scheduled_posts, mark_missed_posts

scheduler = BackgroundScheduler()


def scheduled_analytics_fetch():
    """Cron job: fetch YouTube analytics and update scores every 6 hours."""
    db = SessionLocal()
    try:
        fetch_all_analytics(db)
        update_all_scores(db)
    except Exception as e:
        print(f"Scheduled analytics fetch failed: {e}")
    finally:
        db.close()


def scheduled_post_check():
    """Cron job: check for posts due and upload them to YouTube."""
    db = SessionLocal()
    try:
        process_scheduled_posts(db)
        mark_missed_posts(db)
    except Exception as e:
        print(f"Scheduled post check failed: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    scheduler.add_job(scheduled_analytics_fetch, "interval", hours=6, id="analytics_fetch")
    scheduler.add_job(scheduled_post_check, "interval", minutes=1, id="scheduled_post_check")
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown()


app = FastAPI(
    title="Social Media Content Engine",
    description="AI-powered multi-angle script generation, YouTube upload, feedback loops, and trend-based suggestions",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# API routers
app.include_router(scripts_router)
app.include_router(youtube_router)
app.include_router(trends_router)
app.include_router(feedback_router)
app.include_router(calendar_router)
app.include_router(comments_router)
app.include_router(lineage_router)

# UI router (serves HTML pages) — must be last so /ui/* doesn't shadow API routes
app.include_router(ui_router)
