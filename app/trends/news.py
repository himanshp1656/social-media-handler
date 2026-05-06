import httpx
from app.config import settings

NEWS_BASE_URL = "https://newsapi.org/v2"


def fetch_finance_news(query: str = "RBI OR fixed deposit OR FD rates OR interest rate India", page_size: int = 10) -> list[dict]:
    """Fetch latest finance news from NewsAPI."""
    if not settings.NEWS_API_KEY:
        return []

    response = httpx.get(
        f"{NEWS_BASE_URL}/everything",
        params={
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "apiKey": settings.NEWS_API_KEY,
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    articles = data.get("articles", [])
    return [
        {
            "title": a["title"],
            "description": a.get("description", ""),
            "source": a["source"]["name"],
            "url": a["url"],
            "published_at": a["publishedAt"],
        }
        for a in articles
        if a.get("title")
    ]


def fetch_top_headlines(country: str = "in", category: str = "business", page_size: int = 5) -> list[dict]:
    """Fetch top business headlines."""
    if not settings.NEWS_API_KEY:
        return []

    response = httpx.get(
        f"{NEWS_BASE_URL}/top-headlines",
        params={
            "country": country,
            "category": category,
            "pageSize": page_size,
            "apiKey": settings.NEWS_API_KEY,
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    articles = data.get("articles", [])
    return [
        {
            "title": a["title"],
            "description": a.get("description", ""),
            "source": a["source"]["name"],
            "url": a["url"],
            "published_at": a["publishedAt"],
        }
        for a in articles
        if a.get("title")
    ]
