from enum import Enum


class CTAGoal(str, Enum):
    AWARENESS = "awareness"
    CONVERSION = "conversion"
    RETENTION = "retention"


CTA_MAPPINGS: dict[CTAGoal, dict] = {
    CTAGoal.AWARENESS: {
        "examples": [
            "Follow for daily finance tips that actually make sense",
            "Share this with someone who has an FD — they need to see this",
            "Subscribe — I break down complex finance in 60 seconds",
        ],
        "when": "Use for new audience, educational content, or myth-busting angles. Goal is reach and follower growth.",
    },
    CTAGoal.CONVERSION: {
        "examples": [
            "Link in bio — I've listed the top 5 FDs with the highest rates right now",
            "Comment 'FD' and I'll send you my FD comparison spreadsheet",
            "Check the pinned comment for the full rate comparison table",
        ],
        "when": "Use for opportunity or news-based angles where viewer is ready to act. Goal is driving a specific action.",
    },
    CTAGoal.RETENTION: {
        "examples": [
            "Turn on notifications — I'm dropping a video on RBI's next rate decision tomorrow",
            "Part 2 drops Friday — the tax trick that saves 30% on FD returns",
            "Join the community tab — I post rate alerts there first",
        ],
        "when": "Use for series content, fear angles, or when building anticipation. Goal is repeat viewership.",
    },
}


def get_cta_prompt(goal: CTAGoal) -> str:
    mapping = CTA_MAPPINGS[goal]
    examples = "\n".join(f'- "{e}"' for e in mapping["examples"])
    return (
        f"CTA Goal: {goal.value.upper()}\n"
        f"When to use: {mapping['when']}\n"
        f"Example CTAs:\n{examples}\n\n"
        "Write a CTA that fits this goal naturally within the script's context. "
        "Don't be generic — make it specific to the topic."
    )
