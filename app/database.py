import os
from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_migrations(eng):
    """Add columns that didn't exist in older schema versions."""
    inspector = sa_inspect(eng)

    existing_tables = inspector.get_table_names()

    if "content_briefs" in existing_tables:
        brief_cols = {c["name"] for c in inspector.get_columns("content_briefs")}
        if "suggestion_id" not in brief_cols:
            with eng.connect() as conn:
                conn.execute(text("ALTER TABLE content_briefs ADD COLUMN suggestion_id VARCHAR"))
                conn.commit()

    if "scripts" in existing_tables:
        script_cols = {c["name"] for c in inspector.get_columns("scripts")}
        if "template_id" not in script_cols:
            with eng.connect() as conn:
                conn.execute(text("ALTER TABLE scripts ADD COLUMN template_id VARCHAR"))
                conn.commit()


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations(engine)
