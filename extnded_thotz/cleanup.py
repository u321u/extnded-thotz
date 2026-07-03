"""Rule-based cleanup of raw transcripts: fillers, voice commands, spacing, caps.

Deterministic tier that always runs; the optional LLM polish tier
(llm_cleanup.py) runs after this when enabled.
"""

import re

_FILLER_RE = re.compile(r"(^|\s)(?:um+|uh+|uhm+|erm+|hmm+|mmm+)[,.]?(?=\s|$)", re.IGNORECASE)

_COMMANDS = [
    (re.compile(r"[,.;\s]*\bnew\s+paragraph\b[,.;\s]*", re.IGNORECASE), "\n\n"),
    (re.compile(r"[,.;\s]*\bnew\s+line\b[,.;\s]*", re.IGNORECASE), "\n"),
]


def apply_voice_commands(text: str) -> str:
    for pattern, replacement in _COMMANDS:
        text = pattern.sub(replacement, text)
    return text


def remove_fillers(text: str) -> str:
    return _FILLER_RE.sub(r"\1", text)


def normalize_spacing(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([,;:])(?=[A-Za-z])", r"\1 ", text)
    text = re.sub(r"([.!?])(?=[A-Z])", r"\1 ", text)
    return text


def capitalize_sentences(text: str) -> str:
    return re.sub(
        r"(^|[.!?][\"')\]]?\s+|\n\s*)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )


def clean_transcript(text, *, remove_fillers_enabled=True, voice_commands_enabled=True) -> str:
    if not text:
        return ""
    out = text.strip()
    if voice_commands_enabled:
        out = apply_voice_commands(out)
    if remove_fillers_enabled:
        out = remove_fillers(out)
    out = normalize_spacing(out).strip()  # strip before caps: removed leading fillers leave a space that would block the ^ anchor
    out = capitalize_sentences(out)
    return out.strip()
