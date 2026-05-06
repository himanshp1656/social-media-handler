from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

import json
from app.database import get_db
from app.models import ContentBrief, Script, Beat, ScriptTemplate, ScriptVersion, new_id
from app.scripts.generator import generate_scripts, regenerate_single_script, _snapshot_script

router = APIRouter(prefix="/scripts", tags=["scripts"])


class GenerateRequest(BaseModel):
    brief: str
    platform: str = "youtube_shorts"  # instagram_reels | youtube_shorts
    duration: str = "30s"  # 15s | 30s | 60s
    language: str = "english"  # english | hinglish
    trend_keywords: list[str] | None = None
    template_id: str | None = None
    suggestion_id: str | None = None


class BatchGenerateRequest(BaseModel):
    briefs: list[str]
    platform: str = "youtube_shorts"
    duration: str = "30s"
    language: str = "english"


@router.post("/generate")
def generate(req: GenerateRequest, db: Session = Depends(get_db)):
    result = generate_scripts(db, req.brief, req.platform, req.duration, req.language, req.trend_keywords, req.template_id, req.suggestion_id)
    return result


@router.post("/generate/batch")
def generate_batch(req: BatchGenerateRequest, db: Session = Depends(get_db)):
    results = []
    errors = []
    for brief in req.briefs:
        brief = brief.strip()
        if not brief:
            continue
        try:
            result = generate_scripts(db, brief, req.platform, req.duration, req.language)
            results.append(result)
        except Exception as e:
            errors.append({"brief": brief, "error": str(e)})
    return {"results": results, "errors": errors, "total": len(results)}


@router.get("/briefs")
def list_briefs(db: Session = Depends(get_db)):
    briefs = db.query(ContentBrief).order_by(desc(ContentBrief.created_at)).limit(20).all()
    return [
        {"id": b.id, "topic": b.topic, "raw_brief": b.raw_brief, "created_at": str(b.created_at)}
        for b in briefs
    ]


@router.get("/briefs/{brief_id}")
def get_scripts_for_brief(brief_id: str, db: Session = Depends(get_db)):
    scripts = db.query(Script).filter(Script.brief_id == brief_id).all()
    result = []
    for s in scripts:
        beats = (
            db.query(Beat)
            .filter(Beat.script_id == s.id)
            .order_by(Beat.beat_number)
            .all()
        )
        result.append({
            "id": s.id,
            "angle": s.angle,
            "hook_type": s.hook_type,
            "platform": s.platform,
            "duration": s.duration,
            "title": s.title,
            "hook": s.hook,
            "body": s.body,
            "cta": s.cta,
            "cta_goal": s.cta_goal,
            "hashtags": s.hashtags,
            "thumbnail_suggestion": s.thumbnail_suggestion,
            "predicted_performance": s.predicted_performance,
            "score": s.score,
            "beats": [
                {
                    "beat": b.beat_number,
                    "type": b.beat_type,
                    "timestamp": b.timestamp,
                    "duration_seconds": b.duration_seconds,
                    "voiceover": b.voiceover,
                    "on_screen_text": b.on_screen_text,
                    "visual_cue": b.visual_cue,
                    "camera": b.camera,
                }
                for b in beats
            ],
        })
    return result


@router.get("/briefs/{brief_id}/export")
def export_brief(brief_id: str, db: Session = Depends(get_db)):
    brief = db.query(ContentBrief).filter(ContentBrief.id == brief_id).first()
    if not brief:
        return PlainTextResponse("Brief not found", status_code=404)

    scripts = db.query(Script).filter(Script.brief_id == brief_id).all()
    lines = [f"BRIEF: {brief.raw_brief}", f"ID: {brief.id}", "=" * 60, ""]

    for i, s in enumerate(scripts, 1):
        beats = (
            db.query(Beat)
            .filter(Beat.script_id == s.id)
            .order_by(Beat.beat_number)
            .all()
        )
        platform_label = "Reels" if s.platform == "instagram_reels" else "Shorts"
        lines.append(f"SCRIPT {i}: {s.title}")
        lines.append(f"Angle: {s.angle} | Hook: {s.hook_type} | {platform_label} {s.duration} | CTA: {s.cta_goal}")
        lines.append("-" * 40)
        for b in beats:
            lines.append(f"[{b.beat_type.upper()} {b.timestamp}]")
            lines.append(f"  Voiceover: {b.voiceover}")
            if b.on_screen_text:
                lines.append(f"  Screen: {b.on_screen_text}")
            if b.visual_cue:
                lines.append(f"  Visual: {b.visual_cue}")
            if b.camera:
                lines.append(f"  Camera: {b.camera}")
            lines.append("")
        if s.thumbnail_suggestion:
            lines.append(f"Thumbnail: {s.thumbnail_suggestion}")
        try:
            hashtags = json.loads(s.hashtags) if s.hashtags else []
        except (json.JSONDecodeError, TypeError):
            hashtags = []
        if hashtags:
            lines.append(f"Hashtags: {' '.join(hashtags)}")
        lines.append("=" * 60)
        lines.append("")

    return PlainTextResponse("\n".join(lines), headers={
        "Content-Disposition": f'attachment; filename="brief-{brief_id}.txt"'
    })


# ---- Get single script with beats ----

@router.get("/{script_id}")
def get_script(script_id: str, db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        return {"error": "Script not found"}
    beats = db.query(Beat).filter(Beat.script_id == script.id).order_by(Beat.beat_number).all()
    return {
        "id": script.id,
        "title": script.title,
        "angle": script.angle,
        "hook_type": script.hook_type,
        "platform": script.platform,
        "duration": script.duration,
        "cta_goal": script.cta_goal,
        "score": script.score,
        "beats": [
            {"type": b.beat_type, "timestamp": b.timestamp, "duration_seconds": b.duration_seconds,
             "voiceover": b.voiceover, "on_screen_text": b.on_screen_text,
             "visual_cue": b.visual_cue, "camera": b.camera}
            for b in beats
        ],
    }


# ---- Regenerate single script ----

@router.post("/regenerate/{script_id}")
def regenerate(script_id: str, db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        return {"error": "Script not found"}
    brief = db.query(ContentBrief).filter(ContentBrief.id == script.brief_id).first()
    if not brief:
        return {"error": "Brief not found"}
    result = regenerate_single_script(db, script, brief.raw_brief)
    return {"script_id": script.id, "script": result}


# ---- Edit endpoints ----

class EditScriptRequest(BaseModel):
    title: str | None = None
    cta_goal: str | None = None
    thumbnail_suggestion: str | None = None


class EditBeatRequest(BaseModel):
    voiceover: str | None = None
    on_screen_text: str | None = None
    visual_cue: str | None = None
    camera: str | None = None


@router.patch("/beats/{beat_id}")
def edit_beat(beat_id: str, req: EditBeatRequest, db: Session = Depends(get_db)):
    beat = db.query(Beat).filter(Beat.id == beat_id).first()
    if not beat:
        return {"error": "Beat not found"}
    script = db.query(Script).filter(Script.id == beat.script_id).first()
    if script:
        _snapshot_script(db, script, "edited")
    if req.voiceover is not None:
        beat.voiceover = req.voiceover
    if req.on_screen_text is not None:
        beat.on_screen_text = req.on_screen_text
    if req.visual_cue is not None:
        beat.visual_cue = req.visual_cue
    if req.camera is not None:
        beat.camera = req.camera
    db.commit()
    return {"id": beat.id, "beat": beat.beat_number}


@router.patch("/{script_id}")
def edit_script(script_id: str, req: EditScriptRequest, db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        return {"error": "Script not found"}
    _snapshot_script(db, script, "edited")
    if req.title is not None:
        script.title = req.title
    if req.cta_goal is not None:
        script.cta_goal = req.cta_goal
    if req.thumbnail_suggestion is not None:
        script.thumbnail_suggestion = req.thumbnail_suggestion
    db.commit()
    return {"id": script.id, "title": script.title}


# ---- Version history ----

@router.get("/{script_id}/versions")
def list_versions(script_id: str, db: Session = Depends(get_db)):
    versions = (
        db.query(ScriptVersion)
        .filter(ScriptVersion.script_id == script_id)
        .order_by(desc(ScriptVersion.version_number))
        .all()
    )
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "change_type": v.change_type,
            "title": v.title,
            "angle": v.angle,
            "hook_type": v.hook_type,
            "cta_goal": v.cta_goal,
            "beats_snapshot": json.loads(v.beats_snapshot) if v.beats_snapshot else [],
            "created_at": str(v.created_at),
        }
        for v in versions
    ]


# ---- Template endpoints ----

class SaveTemplateRequest(BaseModel):
    script_id: str
    name: str
    description: str = ""


@router.post("/templates")
def save_template(req: SaveTemplateRequest, db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.id == req.script_id).first()
    if not script:
        return {"error": "Script not found"}

    beats = (
        db.query(Beat)
        .filter(Beat.script_id == script.id)
        .order_by(Beat.beat_number)
        .all()
    )

    beat_structure = [
        {
            "beat": b.beat_number,
            "type": b.beat_type,
            "duration_seconds": b.duration_seconds,
            "camera": b.camera or "",
            "visual_style": b.visual_cue or "",
        }
        for b in beats
    ]

    template = ScriptTemplate(
        id=new_id(),
        name=req.name,
        description=req.description,
        angle=script.angle,
        hook_type=script.hook_type,
        platform=script.platform or "youtube_shorts",
        duration=script.duration or "30s",
        cta_goal=script.cta_goal,
        beat_structure=json.dumps(beat_structure),
        source_script_id=script.id,
    )
    db.add(template)
    db.commit()

    return {"id": template.id, "name": template.name}


@router.get("/templates")
def list_templates(db: Session = Depends(get_db)):
    tpls = db.query(ScriptTemplate).order_by(desc(ScriptTemplate.created_at)).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "angle": t.angle,
            "hook_type": t.hook_type,
            "platform": t.platform,
            "duration": t.duration,
            "cta_goal": t.cta_goal,
            "beat_structure": json.loads(t.beat_structure) if t.beat_structure else [],
            "source_script_id": t.source_script_id,
            "created_at": str(t.created_at),
        }
        for t in tpls
    ]


@router.delete("/templates/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db)):
    tpl = db.query(ScriptTemplate).filter(ScriptTemplate.id == template_id).first()
    if not tpl:
        return {"error": "Template not found"}
    db.delete(tpl)
    db.commit()
    return {"deleted": template_id}
