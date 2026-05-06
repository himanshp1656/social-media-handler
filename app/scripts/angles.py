from enum import Enum


class Angle(str, Enum):
    FEAR = "fear"
    OPPORTUNITY = "opportunity"
    MYTH_BUSTING = "myth_busting"
    NEWS_BASED = "news_based"
    CONTRARIAN = "contrarian"


ANGLE_PROMPTS: dict[Angle, str] = {
    Angle.FEAR: (
        'Write from a FEAR angle. Make the viewer feel they are losing money, missing out, '
        'or making a dangerous mistake by not acting. Use loss aversion psychology. '
        'Example tone: "You are losing money in FD because..."'
    ),
    Angle.OPPORTUNITY: (
        'Write from an OPPORTUNITY angle. Highlight a time-sensitive or unusually favorable situation. '
        'Create urgency and excitement. '
        'Example tone: "FD rates are the highest in 10 years — here is how to lock them in"'
    ),
    Angle.MYTH_BUSTING: (
        'Write from a MYTH-BUSTING angle. Challenge a common belief with surprising facts. '
        'Create cognitive dissonance that demands resolution. '
        'Example tone: "FDs are not safe anymore? Here is what banks won\'t tell you"'
    ),
    Angle.NEWS_BASED: (
        'Write from a NEWS-BASED angle. Anchor the script to a recent event, policy change, or announcement. '
        'Make the viewer feel they need to know this NOW. '
        'Example tone: "RBI just changed this about FDs — here is what it means for your money"'
    ),
    Angle.CONTRARIAN: (
        'Write from a CONTRARIAN angle. Take an unexpected or controversial position that goes against '
        'mainstream advice. Provoke thought and debate. '
        'Example tone: "Why smart investors are secretly moving money OUT of FDs"'
    ),
}
