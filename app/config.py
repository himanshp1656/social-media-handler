from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    AI_PROVIDER: str = "groq"  # "groq" or "gemini"
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8000/youtube/callback"
    NEWS_API_KEY: str = ""
    DATABASE_URL: str = "sqlite:///./data/content.db"
    DEFAULT_LANGUAGE: str = "english"  # "english" or "hinglish"

    model_config = {"env_file": ".env"}


settings = Settings()
