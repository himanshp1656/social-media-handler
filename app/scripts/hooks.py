from enum import Enum


class HookType(str, Enum):
    CURIOSITY = "curiosity"
    EMOTIONAL = "emotional"
    RELIABILITY = "reliability"


HOOK_PROMPTS: dict[HookType, str] = {
    HookType.CURIOSITY: (
        "Create a CURIOSITY hook. Use open loops, surprising statistics, or counterintuitive claims "
        "that make the viewer NEED to keep watching. Examples:\n"
        '- "99% of people don\'t know this about FDs..."\n'
        '- "I found a loophole in how banks calculate FD interest..."\n'
        '- "What happens to your FD if the bank goes bankrupt?"'
    ),
    HookType.EMOTIONAL: (
        "Create an EMOTIONAL TRIGGER hook. Tap into strong feelings — fear of loss, excitement, "
        "anger at being deceived, or pride in being smart. Examples:\n"
        '- "Your FD is silently eating your money and you don\'t even know it"\n'
        '- "Banks are making crores from YOUR money — here\'s the math"\n'
        '- "I lost 2 lakhs because I didn\'t know this FD rule"'
    ),
    HookType.RELIABILITY: (
        "Create a RELIABILITY hook. Lead with data, expert credentials, or verifiable facts "
        "that build instant trust. Examples:\n"
        '- "RBI data shows FD holders lost 3.2% to inflation last year"\n'
        '- "As a CA with 15 years in banking, here\'s what I tell my clients about FDs"\n'
        '- "According to the latest SBI annual report..."'
    ),
}
