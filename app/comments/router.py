from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from app.database import get_db
from app.models import CommentReply, Upload, Script, User, new_id
from app.youtube.auth import is_authenticated, get_credentials
from app.auth.dependencies import get_current_user_api

router = APIRouter(prefix="/comments", tags=["comments"])


@router.post("/fetch/{upload_id}")
def fetch_comments(upload_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """Fetch YouTube comments for a video and save them."""
    if not is_authenticated():
        return {"error": "YouTube not connected"}

    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload or not upload.youtube_video_id:
        return {"error": "Upload not found or no YouTube video linked"}

    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError:
        return {"error": "Google API client not installed. Run: pip install google-api-python-client"}

    creds = get_credentials()
    if not creds:
        return {"error": "YouTube not authenticated. Connect YouTube first."}

    youtube = build("youtube", "v3", credentials=creds)

    # Get existing comment IDs to avoid duplicates
    existing = set(
        r.youtube_comment_id
        for r in db.query(CommentReply.youtube_comment_id)
        .filter(CommentReply.upload_id == upload_id)
        .all()
    )

    # Paginate through comments (cap at 500 to avoid runaway fetches)
    max_comments = 500
    saved = 0
    total_fetched = 0
    page_token = None

    try:
        while total_fetched < max_comments:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=upload.youtube_video_id,
                maxResults=100,
                order="relevance",
                pageToken=page_token,
            )
            response = request.execute()

            items = response.get("items", [])
            total_fetched += len(items)

            for item in items:
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                comment_id = item["snippet"]["topLevelComment"]["id"]

                if comment_id in existing:
                    continue

                reply = CommentReply(
                    id=new_id(),
                    upload_id=upload_id,
                    youtube_comment_id=comment_id,
                    author=snippet.get("authorDisplayName", ""),
                    comment_text=snippet.get("textDisplay", ""),
                )
                db.add(reply)
                saved += 1

            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except HttpError as e:
        if "insufficientPermissions" in str(e) or "403" in str(e):
            return {"error": "Insufficient YouTube permissions. Delete data/youtube-token.json and re-authenticate to grant comment access."}
        return {"error": f"YouTube API error: {str(e)[:200]}"}
    except Exception as e:
        return {"error": f"Failed to fetch comments: {str(e)[:200]}"}

    db.commit()
    return {"fetched": saved, "total": total_fetched}


@router.post("/generate-replies/{upload_id}")
def generate_replies(upload_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """Generate AI replies for pending comments on a video."""
    pending = (
        db.query(CommentReply)
        .filter(CommentReply.upload_id == upload_id)
        .filter(CommentReply.status == "pending")
        .filter(CommentReply.suggested_reply.is_(None))
        .order_by(asc(CommentReply.created_at))
        .limit(20)
        .all()
    )

    if not pending:
        return {"generated": 0, "message": "No pending comments without replies"}

    # Get the script context for better replies
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    script = db.query(Script).filter(Script.id == upload.script_id).first() if upload else None

    script_context = ""
    if script:
        script_context = f"Video title: {script.title}\nAngle: {script.angle}\nTopic: {script.body[:200]}"

    comments_text = "\n".join(
        f'{i+1}. @{c.author}: "{c.comment_text}"'
        for i, c in enumerate(pending)
    )

    from app.ai_client import generate_json
    prompt = f"""You are a content creator replying to YouTube comments on your video.

{script_context}

Reply to each comment below. Rules:
- Be friendly, genuine, and specific to what they said
- Never be generic ("thanks for watching!")
- If they ask a question, answer it helpfully
- If they compliment, acknowledge and add value
- If they disagree, be respectful and open
- Keep each reply under 2 sentences
- Match their energy — casual if they're casual, detailed if they're detailed

COMMENTS:
{comments_text}

Return a JSON array where each item has:
- index: the comment number (1, 2, 3...)
- reply: your suggested reply text

Respond ONLY with valid JSON array."""

    replies = generate_json(prompt, max_tokens=2048, temperature=0.8)

    count = 0
    for r in replies:
        idx = r.get("index", 0) - 1
        if 0 <= idx < len(pending):
            pending[idx].suggested_reply = r.get("reply", "")
            count += 1

    db.commit()
    return {"generated": count}


@router.get("/list/{upload_id}")
def list_comments(upload_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """List all comments and replies for a video."""
    comments = (
        db.query(CommentReply)
        .filter(CommentReply.upload_id == upload_id)
        .order_by(desc(CommentReply.created_at))
        .all()
    )
    return [
        {
            "id": c.id,
            "youtube_comment_id": c.youtube_comment_id,
            "author": c.author,
            "comment_text": c.comment_text,
            "suggested_reply": c.suggested_reply,
            "status": c.status,
            "created_at": str(c.created_at),
        }
        for c in comments
    ]


class UpdateReplyRequest(BaseModel):
    reply_text: str = ""
    status: str = ""  # approved | skipped


@router.patch("/{comment_id}")
def update_reply(comment_id: str, req: UpdateReplyRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """Update a reply (edit text or change status)."""
    comment = db.query(CommentReply).filter(CommentReply.id == comment_id).first()
    if not comment:
        return {"error": "Comment not found"}

    if req.reply_text:
        comment.suggested_reply = req.reply_text
    if req.status:
        comment.status = req.status

    db.commit()
    return {"id": comment.id, "status": comment.status}


@router.post("/post/{comment_id}")
def post_reply(comment_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """Post an approved reply to YouTube."""
    if not is_authenticated():
        return {"error": "YouTube not connected"}

    comment = db.query(CommentReply).filter(CommentReply.id == comment_id).first()
    if not comment:
        return {"error": "Comment not found"}
    if not comment.suggested_reply:
        return {"error": "No reply text"}

    from googleapiclient.discovery import build
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "parentId": comment.youtube_comment_id,
            "textOriginal": comment.suggested_reply,
        }
    }

    youtube.comments().insert(part="snippet", body=body).execute()
    comment.status = "posted"
    db.commit()
    return {"id": comment.id, "status": "posted"}


@router.post("/post-all/{upload_id}")
def post_all_approved(upload_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    """Post all approved replies for a video."""
    if not is_authenticated():
        return {"error": "YouTube not connected"}

    approved = (
        db.query(CommentReply)
        .filter(CommentReply.upload_id == upload_id)
        .filter(CommentReply.status == "approved")
        .all()
    )

    if not approved:
        return {"posted": 0, "message": "No approved replies"}

    from googleapiclient.discovery import build
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    posted = 0
    for comment in approved:
        if not comment.suggested_reply:
            continue
        try:
            body = {
                "snippet": {
                    "parentId": comment.youtube_comment_id,
                    "textOriginal": comment.suggested_reply,
                }
            }
            youtube.comments().insert(part="snippet", body=body).execute()
            comment.status = "posted"
            posted += 1
        except Exception:
            continue

    db.commit()
    return {"posted": posted}
