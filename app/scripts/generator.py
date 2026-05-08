import json
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.config import settings
from app.models import ContentBrief, Script, Beat, ScriptTemplate, ScriptVersion, TrendSuggestion, new_id
from app.scripts.angles import Angle, ANGLE_PROMPTS
from app.scripts.hooks import HookType, HOOK_PROMPTS
from app.scripts.cta import CTAGoal, CTA_MAPPINGS, get_cta_prompt


# Beat structure per duration
DURATION_BEATS = {
    "15s": ["hook", "problem", "cta"],
    "30s": ["hook", "problem", "insight", "cta"],
    "60s": ["hook", "problem", "insight", "proof", "cta"],
}

PLATFORM_CONTEXT = {
    "instagram_reels": {
        "name": "Instagram Reels",
        "text_style": "Bold, centered, 3-5 words max. Emoji OK. Instagram native feel.",
        "cta_style": "Focus on Follow + Share. Use 'Follow for part 2' or 'Share with someone who needs this'.",
        "tone": "Fast, punchy, meme-aware. Gen-Z friendly but financially sharp.",
        "hashtag_count": "5-10 trending hashtags",
    },
    "youtube_shorts": {
        "name": "YouTube Shorts",
        "text_style": "Clean, minimal, lower-third text. No emoji in text overlays.",
        "cta_style": "Focus on Subscribe + Comment. Use 'Subscribe for daily finance' or 'Comment your FD amount'.",
        "tone": "Slightly more detailed than Reels. Can be more educational.",
        "hashtag_count": "3-5 keyword-driven hashtags",
    },
}


def _get_feedback_context(db: Session) -> dict:
    top = (
        db.query(Script)
        .filter(Script.score > 0)
        .order_by(desc(Script.score))
        .limit(3)
        .all()
    )
    worst = (
        db.query(Script)
        .filter(Script.score > 0)
        .order_by(Script.score)
        .limit(3)
        .all()
    )
    return {
        "top": [
            {"angle": s.angle, "hook_type": s.hook_type, "title": s.title, "score": s.score}
            for s in top
        ],
        "worst": [
            {"angle": s.angle, "hook_type": s.hook_type, "title": s.title, "score": s.score}
            for s in worst
        ],
    }


def _build_feedback_section(feedback: dict) -> str:
    section = ""
    if feedback["top"]:
        top_lines = "\n".join(
            f'- [{s["angle"]}/{s["hook_type"]}] "{s["title"]}" (score: {s["score"]})'
            for s in feedback["top"]
        )
        section += f"\nPAST TOP PERFORMERS (replicate these patterns):\n{top_lines}\n"

    if feedback["worst"]:
        worst_lines = "\n".join(
            f'- [{s["angle"]}/{s["hook_type"]}] "{s["title"]}" (score: {s["score"]})'
            for s in feedback["worst"]
        )
        section += f"\nWORST PERFORMERS (avoid these patterns):\n{worst_lines}\n"
    return section


INDIAN_CONTEXT = """
INDIAN CONTEXT (MUST follow):
- Currency: Always use rupees (Rs/₹), lakh (1,00,000), crore (1,00,00,000) — never dollars/millions
- Banks: Reference SBI, HDFC, ICICI, Kotak, Axis, PNB, Bank of Baroda
- Regulators: RBI for banking, SEBI for markets, IRDAI for insurance
- Tax: Section 80C, TDS on FD above ₹40,000, new vs old tax regime, HRA, 80D
- Investment: PPF, NPS, ELSS, SGB (Sovereign Gold Bond), EPF, Sukanya Samriddhi
- Insurance: LIC, term plan vs endowment, health insurance cashless
- Real estate: EMI, RERA, stamp duty, registration charges
- Seasonal: Budget (Feb), tax filing (July), Diwali spending (Oct-Nov), new financial year (April)
- Cultural: Joint family finances, gold as investment, parents' retirement planning, marriage expenses
"""

HINGLISH_RULES = """
LANGUAGE: HINGLISH (Hindi-English mix)
- Write voiceover in natural Hinglish — the way Indian creators actually talk on Reels/Shorts
- Mix Hindi and English naturally: "Yaar, tumhara FD ka paisa inflation kha raha hai"
- Use Hindi for emotional impact: "Suno", "Dekho", "Paise doob rahe hain", "Samjho"
- Use English for technical terms: FD, interest rate, inflation, returns, portfolio
- On-screen text can be English (for readability)
- Tone: Like talking to a friend at a chai stall, not a bank manager
- Examples: "Bhai, 7% interest mil raha hai but inflation 6.5% hai — matlab real return sirf 0.5%"
"""


def _build_prompt(
    brief: str,
    platform: str,
    duration: str,
    language: str,
    feedback: dict,
    trend_keywords: list[str] | None = None,
) -> str:
    """Build prompt for 5 beat-based short-form scripts (one per angle)."""
    feedback_section = _build_feedback_section(feedback)
    plat = PLATFORM_CONTEXT[platform]
    beat_types = DURATION_BEATS[duration]

    trends_section = ""
    if trend_keywords:
        trends_section = f"\nCURRENT TRENDING KEYWORDS: {', '.join(trend_keywords)}\nIncorporate these naturally if relevant.\n"

    if language == "hinglish":
        language_section = HINGLISH_RULES
        voice_lang = "natural Hinglish (Hindi-English mix)"
    else:
        language_section = "\nLANGUAGE: ENGLISH ONLY\n- All voiceover MUST be in English. Do NOT use Hindi, Hinglish, or any regional language.\n- Even if the brief is in another language, write all scripts strictly in English.\n- On-screen text must also be in English.\n"
        voice_lang = "English only (no Hindi or Hinglish)"

    angle_instructions = "\n".join(
        f"### {a.value.upper()}\n{ANGLE_PROMPTS[a]}" for a in Angle
    )
    hook_guidelines = "\n".join(
        f"### {h.value.upper()}\n{HOOK_PROMPTS[h]}" for h in HookType
    )
    cta_guidelines = "\n".join(
        f"### {g.value.upper()}\n{get_cta_prompt(g)}" for g in CTAGoal
    )

    beat_spec = "\n".join(
        f"  Beat {i+1} — type: \"{bt}\""
        for i, bt in enumerate(beat_types)
    )

    return f"""You are an expert viral content scriptwriter for {plat['name']}. You write short-form video scripts (Reels/Shorts) that hook viewers in the first second and deliver value in under {duration}.

CONTENT BRIEF: {brief}
PLATFORM: {plat['name']}
DURATION: {duration}
{feedback_section}
{trends_section}
{INDIAN_CONTEXT}
{language_section}

Generate exactly 5 scripts, one for each ANGLE. Each script is a sequence of timed BEATS.

BEAT STRUCTURE (each script must have exactly {len(beat_types)} beats in this order):
{beat_spec}

For each script, return a JSON object with:
- angle: One of: fear, opportunity, myth_busting, news_based, contrarian
- hook_type: One of: curiosity, emotional, reliability (pick best for the angle)
- title: Short title (under 60 chars, power words, {plat['name']} optimized)
- cta_goal: One of: awareness, conversion, retention
- thumbnail_suggestion: Text overlay + expression for thumbnail
- predicted_performance: low, medium, or high
- hashtags: Array of {plat['hashtag_count']} relevant hashtags
- beats: Array of exactly {len(beat_types)} beat objects, each with:
  - beat: beat number (1, 2, 3...)
  - type: "{'" | "'.join(beat_types)}" (in order)
  - timestamp: "M:SS-M:SS" format, beats must be consecutive and total {duration}
  - duration_seconds: integer seconds for this beat
  - voiceover: Exactly what the creator says in {voice_lang}, use lakh/crore/rupees
  - on_screen_text: {plat['text_style']}
  - visual_cue: What appears on screen (graphics, animations, B-roll descriptions)
  - camera: Camera direction (tight shot, medium, B-roll, zoom, etc.)

ANGLE INSTRUCTIONS:
{angle_instructions}

HOOK GUIDELINES (for the hook beat):
{hook_guidelines}

CTA MAPPING (for the cta beat):
{cta_guidelines}

PLATFORM RULES for {plat['name']}:
- Text style: {plat['text_style']}
- CTA style: {plat['cta_style']}
- Tone: {plat['tone']}

IMPORTANT RULES:
- Each script gets a DIFFERENT angle (use all 5: fear, opportunity, myth_busting, news_based, contrarian)
- Pick the hook type that works best for each angle
- Voiceover should sound like a real Indian creator talking — not a textbook
- On-screen text should be punchy, 3-5 words max per beat
- Timestamps must be consecutive and add up to exactly {duration}
- CTA goal should match the viewer's journey stage

Respond ONLY with a valid JSON array of 5 objects. No markdown, no explanation."""


def _build_template_prompt(
    brief: str,
    template: dict,
    platform: str,
    duration: str,
    language: str,
    feedback: dict,
) -> str:
    """Build prompt that constrains generation to a template's structure."""
    feedback_section = _build_feedback_section(feedback)
    plat = PLATFORM_CONTEXT[platform]
    if language == "hinglish":
        language_section = HINGLISH_RULES
        voice_lang = "natural Hinglish (Hindi-English mix)"
    else:
        language_section = "\nLANGUAGE: ENGLISH ONLY\n- All voiceover MUST be in English. Do NOT use Hindi, Hinglish, or any regional language.\n- Even if the brief is in another language, write all scripts strictly in English.\n- On-screen text must also be in English.\n"
        voice_lang = "English only (no Hindi or Hinglish)"

    beats = template["beat_structure"]
    beat_spec = "\n".join(
        f'  Beat {b["beat"]} — type: "{b["type"]}", duration: {b["duration_seconds"]}s, camera style: {b.get("camera", "any")}'
        for b in beats
    )

    return f"""You are an expert viral content scriptwriter for {plat['name']}.

CONTENT BRIEF: {brief}
PLATFORM: {plat['name']}
DURATION: {duration}
{feedback_section}
{INDIAN_CONTEXT}
{language_section}

You are generating scripts using a PROVEN TEMPLATE structure. This template has performed well before — follow it closely.

TEMPLATE CONSTRAINTS:
- Angle: {template["angle"]}
- Hook type: {template["hook_type"]}
- CTA goal: {template["cta_goal"]}

EXACT BEAT STRUCTURE (follow this timing and beat order exactly):
{beat_spec}

Generate exactly 5 VARIATIONS of scripts using this template. All 5 must use:
- angle: "{template["angle"]}"
- hook_type: "{template["hook_type"]}"
- cta_goal: "{template["cta_goal"]}"

But each variation should have a DIFFERENT creative take on the brief — different hooks, different examples, different voiceover.

For each script, return a JSON object with:
- angle: "{template["angle"]}"
- hook_type: "{template["hook_type"]}"
- title: Short title (under 60 chars, power words, {plat['name']} optimized) — DIFFERENT for each variation
- cta_goal: "{template["cta_goal"]}"
- thumbnail_suggestion: Text overlay + expression for thumbnail
- predicted_performance: low, medium, or high
- hashtags: Array of {plat['hashtag_count']} relevant hashtags
- beats: Array of exactly {len(beats)} beat objects, each with:
  - beat: beat number (1, 2, 3...)
  - type: must match template beat types exactly
  - timestamp: "M:SS-M:SS" format, must match template durations
  - duration_seconds: must match template durations exactly
  - voiceover: Exactly what the creator says in {voice_lang}, use lakh/crore/rupees
  - on_screen_text: {plat['text_style']}
  - visual_cue: What appears on screen (graphics, animations, B-roll descriptions)
  - camera: Camera direction (follow template camera styles where provided)

PLATFORM RULES for {plat['name']}:
- Text style: {plat['text_style']}
- CTA style: {plat['cta_style']}
- Tone: {plat['tone']}

IMPORTANT:
- All 5 scripts MUST use the same angle, hook_type, and cta_goal from the template
- Each script must have a UNIQUE creative approach — different hooks, examples, numbers, stories
- Beat timings must match the template exactly
- Voiceover should sound like a real Indian creator talking

Respond ONLY with a valid JSON array of 5 objects. No markdown, no explanation."""


def generate_scripts(
    db: Session,
    brief: str,
    platform: str = "youtube_shorts",
    duration: str = "30s",
    language: str = "english",
    trend_keywords: list[str] | None = None,
    template_id: str | None = None,
    suggestion_id: str | None = None,
    created_by: str | None = None,
    team_id: str | None = None,
) -> dict:
    # Load template if provided
    template_data = None
    if template_id:
        tpl = db.query(ScriptTemplate).filter(ScriptTemplate.id == template_id).first()
        if tpl:
            template_data = {
                "angle": tpl.angle,
                "hook_type": tpl.hook_type,
                "cta_goal": tpl.cta_goal,
                "platform": tpl.platform,
                "duration": tpl.duration,
                "beat_structure": json.loads(tpl.beat_structure) if tpl.beat_structure else [],
            }
            # Override platform/duration from template
            platform = template_data["platform"]
            duration = template_data["duration"]

    from app.ai_client import generate_json
    feedback = _get_feedback_context(db)
    if template_data:
        prompt = _build_template_prompt(brief, template_data, platform, duration, language, feedback)
    else:
        prompt = _build_prompt(brief, platform, duration, language, feedback, trend_keywords)
    scripts_data = generate_json(prompt)

    if not isinstance(scripts_data, list) or len(scripts_data) != 5:
        raise ValueError(
            f"Expected 5 scripts, got "
            f"{len(scripts_data) if isinstance(scripts_data, list) else 'non-list'}"
        )

    # Save brief
    brief_id = new_id()
    topic = " ".join(brief.split()[:5])
    db_brief = ContentBrief(id=brief_id, topic=topic, raw_brief=brief, suggestion_id=suggestion_id, created_by=created_by, team_id=team_id)
    db.add(db_brief)

    # Mark trend suggestion as "used" if linked
    if suggestion_id:
        trend = db.query(TrendSuggestion).filter(TrendSuggestion.id == suggestion_id).first()
        if trend:
            trend.status = "used"

    # Save scripts and beats
    for s in scripts_data:
        script_id = new_id()

        # Build body from voiceover for backward compat
        body = "\n".join(b.get("voiceover", "") for b in s.get("beats", []))

        # Get hook text from first beat
        hook_text = ""
        beats = s.get("beats", [])
        if beats:
            hook_text = beats[0].get("voiceover", "")

        # Get CTA text from last beat
        cta_text = ""
        if beats:
            cta_text = beats[-1].get("voiceover", "")

        script = Script(
            id=script_id,
            brief_id=brief_id,
            template_id=template_id,
            created_by=created_by,
            team_id=team_id,
            angle=s["angle"],
            hook_type=s["hook_type"],
            platform=platform,
            duration=duration,
            title=s["title"],
            hook=hook_text,
            body=body,
            cta=cta_text,
            cta_goal=s["cta_goal"],
            hashtags=json.dumps(s.get("hashtags", [])),
            thumbnail_suggestion=s.get("thumbnail_suggestion", ""),
            predicted_performance=s.get("predicted_performance", "medium"),
        )
        db.add(script)
        s["id"] = script_id

        # Save beats
        for b in beats:
            beat = Beat(
                id=new_id(),
                script_id=script_id,
                beat_number=b["beat"],
                beat_type=b["type"],
                timestamp=b["timestamp"],
                duration_seconds=b["duration_seconds"],
                voiceover=b["voiceover"],
                on_screen_text=b.get("on_screen_text", ""),
                visual_cue=b.get("visual_cue", ""),
                camera=b.get("camera", ""),
            )
            db.add(beat)

    db.commit()

    return {
        "brief_id": brief_id,
        "topic": topic,
        "scripts": scripts_data,
    }


def _snapshot_script(db: Session, script, change_type: str):
    """Save a version snapshot of a script before destructive changes."""
    beats = (
        db.query(Beat)
        .filter(Beat.script_id == script.id)
        .order_by(Beat.beat_number)
        .all()
    )
    beats_data = [
        {
            "beat": b.beat_number, "type": b.beat_type, "timestamp": b.timestamp,
            "duration_seconds": b.duration_seconds, "voiceover": b.voiceover,
            "on_screen_text": b.on_screen_text, "visual_cue": b.visual_cue, "camera": b.camera,
        }
        for b in beats
    ]
    version_count = db.query(ScriptVersion).filter(ScriptVersion.script_id == script.id).count()
    version = ScriptVersion(
        id=new_id(),
        script_id=script.id,
        version_number=version_count + 1,
        change_type=change_type,
        title=script.title,
        angle=script.angle,
        hook_type=script.hook_type,
        cta_goal=script.cta_goal,
        hashtags=script.hashtags,
        thumbnail_suggestion=script.thumbnail_suggestion,
        predicted_performance=script.predicted_performance,
        beats_snapshot=json.dumps(beats_data),
    )
    db.add(version)


def regenerate_single_script(
    db: Session,
    script: "Script",
    brief_text: str,
) -> dict:
    """Regenerate a single script keeping its angle, platform, and duration."""
    from app.ai_client import generate_json

    # Snapshot current version before overwriting
    _snapshot_script(db, script, "regenerated")

    feedback = _get_feedback_context(db)
    plat = PLATFORM_CONTEXT.get(script.platform, PLATFORM_CONTEXT["youtube_shorts"])
    beat_types = DURATION_BEATS.get(script.duration, DURATION_BEATS["30s"])
    feedback_section = _build_feedback_section(feedback)

    language_section = "\nLANGUAGE: ENGLISH ONLY\n- All voiceover MUST be in English.\n- On-screen text must also be in English.\n"
    voice_lang = "English only"

    beat_spec = "\n".join(
        f'  Beat {i+1} — type: "{bt}"'
        for i, bt in enumerate(beat_types)
    )

    prompt = f"""You are an expert viral content scriptwriter for {plat['name']}.

CONTENT BRIEF: {brief_text}
PLATFORM: {plat['name']}
DURATION: {script.duration}
{feedback_section}
{INDIAN_CONTEXT}
{language_section}

Generate exactly 1 script using the angle: {script.angle}. Pick the best hook_type for this angle.

BEAT STRUCTURE (exactly {len(beat_types)} beats):
{beat_spec}

Return a JSON object with:
- angle: "{script.angle}"
- hook_type: One of: curiosity, emotional, reliability
- title: Short title (under 60 chars)
- cta_goal: One of: awareness, conversion, retention
- thumbnail_suggestion: Text overlay + expression
- predicted_performance: low, medium, or high
- hashtags: Array of {plat['hashtag_count']} hashtags
- beats: Array of exactly {len(beat_types)} beat objects with: beat, type, timestamp, duration_seconds, voiceover, on_screen_text, visual_cue, camera

Respond ONLY with a valid JSON object (not an array). No markdown."""

    script_data = generate_json(prompt)

    # If wrapped in a list, take the first
    if isinstance(script_data, list):
        script_data = script_data[0]

    # Delete old beats
    db.query(Beat).filter(Beat.script_id == script.id).delete()

    # Update script fields
    beats = script_data.get("beats", [])
    body = "\n".join(b.get("voiceover", "") for b in beats)

    script.hook_type = script_data.get("hook_type", script.hook_type)
    script.title = script_data["title"]
    script.hook = beats[0].get("voiceover", "") if beats else ""
    script.body = body
    script.cta = beats[-1].get("voiceover", "") if beats else ""
    script.cta_goal = script_data.get("cta_goal", script.cta_goal)
    script.hashtags = json.dumps(script_data.get("hashtags", []))
    script.thumbnail_suggestion = script_data.get("thumbnail_suggestion", "")
    script.predicted_performance = script_data.get("predicted_performance", "medium")

    # Save new beats
    for b in beats:
        beat = Beat(
            id=new_id(),
            script_id=script.id,
            beat_number=b["beat"],
            beat_type=b["type"],
            timestamp=b["timestamp"],
            duration_seconds=b["duration_seconds"],
            voiceover=b["voiceover"],
            on_screen_text=b.get("on_screen_text", ""),
            visual_cue=b.get("visual_cue", ""),
            camera=b.get("camera", ""),
        )
        db.add(beat)

    db.commit()
    return script_data
