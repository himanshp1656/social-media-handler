# ScriptLab — AI Content Engine for Finance Creators

## The Problem

Finance creators on YouTube and Instagram face a brutal content treadmill:

1. **Trend discovery is manual** — scrolling through news, Twitter, Google Trends to find what's hot
2. **Script writing is slow** — a single 60-second short takes 30-60 minutes to write, and you need multiple angles to test what works
3. **No feedback loop** — creators don't know which hook type, angle, or CTA actually drives engagement, so they keep guessing
4. **Multi-platform is painful** — the same topic needs different scripts for YouTube Shorts vs Instagram Reels vs long-form
5. **Team coordination is messy** — a YouTube team and Instagram team working on the same topics can't see or reuse each other's work without manual sharing
6. **Scheduling and uploads are fragmented** — separate tools for writing, uploading, scheduling, and analytics

Creators end up using 5+ tools (Google Trends, ChatGPT, Google Docs, YouTube Studio, spreadsheets) with no connection between them.

## The Solution

ScriptLab is a single platform that handles the entire content pipeline:

```
Discover Trends → Generate Scripts → Record → Schedule → Upload → Track Performance → Learn & Improve
```

### What it does

- **Trend Engine** — Pulls live finance news via NewsAPI, uses AI to score topics by viral potential and auto-generate content briefs
- **AI Script Generator** — Takes a brief and generates 5 script variants with different angles (contrarian, educational, storytelling), hooks (question, bold claim, statistic), and platforms (YouTube Shorts, Instagram Reels). Each script includes beat-by-beat breakdowns with voiceover, visuals, camera cues, and timing
- **Templates** — Save a winning script structure and reuse it on new topics. If "contrarian + bold claim" works, templatize it
- **Content Calendar** — Schedule video uploads to specific dates/times. Blocks past-date scheduling. Auto-uploads via YouTube API
- **YouTube Integration** — OAuth-based upload, link existing videos, fetch real analytics (views, likes, CTR, watch time)
- **Performance Insights** — Angle x Hook heatmap shows which combinations drive engagement. Top/bottom script rankings. Score propagation flows from uploads → scripts → briefs → trends
- **Content Lineage** — Visual graph tracing every piece of content from the trend that inspired it, through the brief, to every script variant, to the uploaded video
- **Team Namespaces** — Content is scoped to teams (YouTube Team, Instagram Team, etc.). Switch teams in one click to see only that team's content. "All Content" team for shared work
- **AI Comment Replies** — Suggested replies for YouTube comments

### The feedback loop

This is the key differentiator. Most tools stop at "generate a script." ScriptLab closes the loop:

1. Generate 5 scripts with different angles/hooks
2. Upload them to YouTube
3. Analytics flow back automatically every 6 hours
4. Scores propagate up: Upload → Script → Brief → Trend
5. The Insights heatmap shows which angle + hook combos actually perform
6. Next time you generate, you know what works — not what you think works

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| **Backend** | Python + FastAPI | Async support, auto-generated API docs, Pydantic validation. Fast to build, easy to extend |
| **AI** | Groq (LLaMA) / Gemini | Groq for speed (script generation in ~3s), Gemini as fallback. Structured JSON output for reliable parsing |
| **Database** | SQLite + SQLAlchemy | Zero infrastructure for a single-server app. SQLAlchemy ORM for clean queries and easy migration to Postgres later |
| **Frontend** | Jinja2 + Vanilla JS | Server-rendered HTML. No build step, no npm, no React overhead. Fast page loads, works everywhere |
| **YouTube** | Google OAuth2 + YouTube Data API v3 | Direct upload, analytics fetching, comment management. No third-party middleman |
| **News** | NewsAPI | Real-time finance headlines for trend discovery |
| **Scheduling** | APScheduler | In-process cron jobs for analytics fetching (every 6h) and auto-posting (every 1m) |
| **Auth** | Session-based (bcrypt + httpOnly cookies) | Simple, secure. No JWT complexity for a server-rendered app |
| **Containerization** | Docker + Docker Compose | One command to run. Consistent across environments |

### Why not React/Next.js?

This is a tools-first product, not a consumer app. Server-rendered Jinja2 templates with vanilla JS give us:
- Zero build step — edit a template, refresh the page
- Smaller payload — no 200KB JS bundle for a form
- Simpler deployment — one Python process, no Node server
- Faster iteration — add a new page in minutes, not hours

### Why SQLite?

For a single-server content tool, SQLite is the right choice:
- Zero setup — no database server to manage
- Fast — for read-heavy workloads with <100 concurrent users, SQLite outperforms Postgres
- Portable — the entire database is one file, easy to backup
- Upgradeable — SQLAlchemy ORM means switching to Postgres is a config change, not a rewrite

## Architecture

```
                          ┌──────────────┐
                          │   NewsAPI     │
                          │  (Finance)   │
                          └──────┬───────┘
                                 │ headlines
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                         │
│                                                                     │
│  ┌─────────────────────── API Layer ──────────────────────────┐    │
│  │                                                             │    │
│  │  /trends      /scripts     /calendar    /youtube    /auth   │    │
│  │  /feedback    /lineage     /comments    /ui                 │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│         │               │                │                          │
│         ▼               ▼                ▼                          │
│  ┌────────────┐  ┌────────────┐  ┌─────────────┐                  │
│  │  Trend     │  │  Script    │  │  YouTube    │                  │
│  │  Suggester │  │  Generator │  │  OAuth2     │                  │
│  │            │  │            │  │             │                  │
│  │  Score &   │  │  5 angles  │  │  Upload     │                  │
│  │  rank news │  │  per brief │  │  Analytics  │                  │
│  └────────────┘  └─────┬──────┘  └──────┬──────┘                  │
│                        │                 │                          │
│                        │    ┌────────────┘                          │
│                        ▼    ▼                                       │
│               ┌──────────────────┐                                  │
│               │  Feedback Loop   │◄──── scores propagate:          │
│               │                  │      Upload → Script → Brief    │
│               │  Top 3 winners   │           → Trend               │
│               │  Bottom 3 losers │                                  │
│               │       │          │                                  │
│               │       ▼          │                                  │
│               │  Injected into   │                                  │
│               │  next AI prompt  │                                  │
│               └──────────────────┘                                  │
│                        │                                            │
│         ┌──────────────┼──────────────┐                            │
│         ▼              ▼              ▼                             │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                     │
│  │  Lineage   │ │  Insights  │ │  Comment   │                     │
│  │  Graph     │ │  Heatmap   │ │  AI Reply  │                     │
│  │            │ │            │ │            │                     │
│  │  Trend →   │ │  Angle x   │ │  Suggested │                     │
│  │  Brief →   │ │  Hook perf │ │  responses │                     │
│  │  Script →  │ │  matrix    │ │            │                     │
│  │  Upload    │ │            │ │            │                     │
│  └────────────┘ └────────────┘ └────────────┘                     │
│                                                                     │
│  ┌─────────────────── Data Layer ─────────────────────────────┐    │
│  │                                                             │    │
│  │  SQLite + SQLAlchemy ORM                                    │    │
│  │                                                             │    │
│  │  Teams │ Trends │ Briefs │ Scripts │ Beats │ Templates      │    │
│  │  Uploads │ Analytics │ Comments │ Scheduled Posts            │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─────────────────── Background Jobs ────────────────────────┐    │
│  │  APScheduler                                                │    │
│  │  ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐  │    │
│  │  │ Fetch Analytics │  │ Auto-Upload  │  │ Score Update │  │    │
│  │  │ every 6 hours   │  │ every 1 min  │  │ after fetch  │  │    │
│  │  └─────────────────┘  └──────────────┘  └──────────────┘  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
         │                                          │
         ▼                                          ▼
┌──────────────┐                          ┌──────────────┐
│  YouTube     │                          │  Groq /      │
│  Data API v3 │                          │  Gemini AI   │
└──────────────┘                          └──────────────┘
```

## Data Model

```
Team (namespace)
 └── TrendSuggestion (AI-scored from news)
      └── ContentBrief (topic + raw brief)
           └── Script (angle, hook, platform, beats)
                ├── Upload (YouTube video link)
                │    └── Analytics (views, likes, CTR)
                │    └── CommentReply (AI-suggested)
                ├── ScriptTemplate (reusable structure)
                └── ScriptVersion (edit history)
```

## Getting Started

### Prerequisites
- Python 3.11+
- API keys: Groq or Gemini (AI), NewsAPI (trends), YouTube OAuth2 (uploads)

### Local Setup

```bash
# Clone
git clone https://github.com/himanshp1656/social-media-handler.git
cd social-media-handler

# Virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Edit .env with your API keys

# Run
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 — the app auto-creates tables and seeds demo data on first run.

### Docker

```bash
docker compose up --build
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AI_PROVIDER` | Yes | `groq` or `gemini` |
| `GROQ_API_KEY` | If using Groq | Groq API key |
| `GEMINI_API_KEY` | If using Gemini | Google Gemini API key |
| `NEWS_API_KEY` | Yes | NewsAPI.org key for trend discovery |
| `YOUTUBE_CLIENT_ID` | For YouTube | Google OAuth2 client ID |
| `YOUTUBE_CLIENT_SECRET` | For YouTube | Google OAuth2 client secret |
| `YOUTUBE_REDIRECT_URI` | For YouTube | OAuth callback URL |
| `DATABASE_URL` | No | Defaults to `sqlite:///./data/content.db` |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/scripts/generate` | Generate 5 script variants from a brief |
| POST | `/scripts/batch` | Batch generate from multiple briefs |
| POST | `/trends/suggest` | Fetch news and generate trend suggestions |
| GET | `/trends/suggestions` | List trend suggestions |
| POST | `/youtube/upload/{script_id}` | Upload video to YouTube |
| POST | `/youtube/link` | Link existing YouTube video |
| POST | `/calendar/schedule` | Schedule a video post |
| GET | `/calendar/week` | Get week's scheduled posts |
| GET | `/feedback/scores` | Get script performance rankings |
| GET | `/lineage/{type}/{id}` | Get content lineage graph |
| GET | `/` | Dashboard |
