"""Optional LLM polish pass for dictated text (OpenAI). Fails soft: any error
returns the rule-cleaned text unchanged, so dictation never breaks offline."""

SYSTEM_PROMPT = (
    "You clean up dictated speech-to-text output. Fix punctuation, capitalization, "
    "and obvious transcription artifacts; remove filler words and false starts; keep "
    "the speaker's own words and meaning; never add content and never answer questions "
    "that appear in the text. Preserve line breaks. Return ONLY the cleaned text."
)


def should_polish(cfg: dict, api_key: str) -> bool:
    mode = cfg.get("llm_cleanup", "auto")
    if mode == "on":
        return True
    if mode == "auto":
        return bool(api_key)
    return False


def polish(text: str, api_key: str, model: str = "gpt-4o-mini",
           timeout_s: float = 10.0, _client=None) -> str:
    if not text.strip() or (not api_key and _client is None):
        return text
    try:
        client = _client
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, timeout=timeout_s)
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        cleaned = (response.choices[0].message.content or "").strip()
        return cleaned or text
    except Exception:
        return text
