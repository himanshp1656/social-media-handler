# Content Engine v2 — Roadmap

## Vision
A content engine that turns one brief ("why FDs are back") into 5+ short-form video scripts tailored for Instagram Reels / YouTube Shorts — with hooks, beats, on-screen text, timestamps, visual cues, CTA, and a storyboard preview. Indian-specific framing.

---

## What We Already Have (Reusable)
- FastAPI + SQLAlchemy + SQLite setup
- Groq AI integration (Llama 3.3 70B)
- YouTube OAuth + video linking + analytics fetch
- Feedback loop (analytics -> scores -> AI learns)
- Trends + news suggestion engine
- Dark theme UI with Jinja2 templates
- Mock mode for testing

## What Changes
- Script format: long-form text blocks -> timestamped beat-by-beat short-form
- Output: structured beats with visual cues, on-screen text, camera directions
- New: platform selector (Instagram Reels vs YouTube Shorts)
- New: duration presets (15s / 30s / 60s)
- New: storyboard preview (visual timeline in UI)
- New: Indian context layer (Hinglish, RBI, lakh/crore, festivals)



---

## New Script Structure

Each script = a sequence of **beats** (timed segments):

```json
{
  "platform": "instagram_reels",
  "duration": "30s",
  "angle": "fear",
  "hook_type": "curiosity",
  "title": "Your FD is Losing Money",
  "beats": [
    {
      "beat": 1,
      "type": "hook",
      "timestamp": "0:00-0:03",
      "duration_seconds": 3,
      "voiceover": "You're losing money in your FD right now and you don't even know it.",
      "on_screen_text": "YOUR FD IS LOSING MONEY",
      "visual_cue": "Close-up face, shocked expression, red background flash",
      "camera": "tight face shot, slight zoom in"
    },
    {
      "beat": 2,
      "type": "problem",
      "timestamp": "0:03-0:10",
      "duration_seconds": 7,
      "voiceover": "Banks give you 7% but inflation is 6.5%. After tax, you're making 0.3%.",
      "on_screen_text": "7% FD - 6.5% Inflation = 0.3%",
      "visual_cue": "Calculation appearing on screen, numbers in red",
      "camera": "medium shot, talking to camera"
    },
    {
      "beat": 3,
      "type": "insight",
      "timestamp": "0:10-0:22",
      "duration_seconds": 12,
      "voiceover": "Your 10 lakh FD from 2 years ago is worth only 9.3 lakhs in real terms.",
      "on_screen_text": "10L -> 9.3L (real value)",
      "visual_cue": "Split screen: nominal vs real value, money shrinking",
      "camera": "B-roll of bank, then back to face"
    },
    {
      "beat": 4,
      "type": "cta",
      "timestamp": "0:22-0:30",
      "duration_seconds": 8,
      "voiceover": "Follow for part 2 — I'll show you what to do instead.",
      "on_screen_text": "FOLLOW FOR PART 2",
      "visual_cue": "Point at follow button, text pops up",
      "camera": "medium shot, direct eye contact"
    }
  ],
  "cta_goal": "retention",
  "thumbnail_suggestion": "Shocked face, red text: YOUR FD IS LOSING MONEY",
  "hashtags": ["#fd", "#fixeddeposit", "#money", "#finance", "#investing"],
  "predicted_performance": "high"
}
```

---

## Beat Types

| Beat | Purpose | Typical Duration |
|------|---------|-----------------|
| **hook** | Stop the scroll. First 1-3 seconds. | 1-3s |
| **problem** | Set up the tension/conflict. | 3-7s |
| **insight** | The "aha" moment — data, story, or reveal. | 5-15s |
| **proof** | Evidence — numbers, screenshot, example. | 3-8s |
| **cta** | Call to action — follow, share, comment. | 3-8s |
| **twist** | (optional) Surprise ending or cliffhanger. | 2-5s |

### Duration Presets
- **15s**: hook + problem + cta (3 beats)
- **30s**: hook + problem + insight + cta (4 beats)
- **60s**: hook + problem + insight + proof + cta (5 beats)

---

## Platform Differences

| | Instagram Reels | YouTube Shorts |
|---|---|---|
| Max duration | 90s | 60s |
| Text style | Bold, centered, 3-5 words max | Can be longer, lower third |
| CTA style | "Follow + Share" | "Subscribe + Comment" |
| Hashtags | 5-10, trend-driven | 3-5, keyword-driven |
| Tone | Fast, punchy, meme-aware | Slightly more detailed |
| On-screen text | Instagram font style, emoji OK | Clean, minimal |

---

## Phases

### Phase 1: Core Script Engine Rework
**Goal:** Brief + platform + duration -> 5 beat-based scripts

- [x] Add `Beat` model in database (linked to Script)
- [x] Update `Script` model — add `platform`, `duration`, `hashtags` fields
- [x] New prompt engineering — beat-by-beat with timestamps, voiceover, on-screen text, visual cues, camera
- [x] Platform-aware prompts (Reels vs Shorts tone/CTA differences)
- [x] Duration presets (15s/30s/60s) control beat count
- [x] Update Generate UI — add platform dropdown + duration selector
- [x] Update brief detail page — show scripts as beat timelines

### Phase 2: Storyboard Preview
**Goal:** Visual timeline UI showing each beat

- [x] Storyboard component — horizontal/vertical timeline per script
- [x] Each beat = a card with timestamp, voiceover, on-screen text, visual cue, camera
- [x] Color-coded by beat type (hook=red, problem=orange, insight=blue, proof=green, cta=purple)
- [x] Expandable/collapsible beats
- [x] "Copy Script" button (voiceover only — for teleprompter)
- [x] "Copy Beat" for individual segments
- [x] Export as JSON

### Phase 3: Indian Context Layer
**Goal:** Scripts feel native to Indian audience

- [x] Indian examples baked into prompts (SBI, HDFC, RBI, lakh/crore, rupees)
- [x] Hinglish toggle — Hindi-English mix scripts
- [x] Festival/event awareness (budget season, tax filing, Diwali spending)
- [x] Regional references (metro vs tier-2 framing)

### Phase 4: Feedback Loop v2
**Goal:** Beat-level performance optimization

- [ ] Track which beat types drive retention
- [x] Score at angle + hook + platform + duration level
- [x] AI uses past performance in prompts
- [ ] A/B comparison view — same brief, different scripts side by side

### Phase 5: Polish
- [x] Export scripts as text file
- [x] Teleprompter mode (large font, auto-scroll)
- [x] Batch generate (multiple briefs)
- [x] Template system (save winning structures as reusable)
- [x] Inline script & beat editing
- [x] Single-script regeneration (keep angle, re-roll content)
- [x] Trend-to-generate flow (suggestions auto-marked as used)
- [ ] Share script links with editors

---

## Database Changes

```
Script (updated):
  + platform: String        # instagram_reels | youtube_shorts
  + duration: String         # 15s | 30s | 60s
  + hashtags: Text           # JSON array as string

Beat (new table):
  id: String (PK)
  script_id: String (FK -> scripts.id)
  beat_number: Integer
  beat_type: String          # hook | problem | insight | proof | cta | twist
  timestamp: String          # "0:00-0:03"
  duration_seconds: Integer
  voiceover: Text
  on_screen_text: Text
  visual_cue: Text
  camera: Text
```

---

## Start With
Phase 1 — rework the script engine to generate beat-based short-form scripts with timestamps and visual cues. Everything else builds on this.
