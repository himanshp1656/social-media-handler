"""Unified AI client — supports Groq and Gemini backends."""

import json
import re
from groq import Groq
from app.config import settings


def _get_groq_client() -> Groq:
    return Groq(api_key=settings.GROQ_API_KEY)


def _call_groq(prompt: str, max_tokens: int = 8192, temperature: float = 0.9) -> str:
    client = _get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _call_gemini(prompt: str, max_tokens: int = 8192, temperature: float = 0.9) -> str:
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)

    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config=genai.GenerationConfig(
            temperature=temperature,
            top_p=0.95,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        ),
    )
    response = model.generate_content(prompt)
    return response.text


def generate(prompt: str, max_tokens: int = 8192, temperature: float = 0.9) -> str:
    """Call the configured AI provider and return raw text response."""
    provider = settings.AI_PROVIDER

    if provider == "groq":
        return _call_groq(prompt, max_tokens, temperature)
    elif provider == "gemini":
        return _call_gemini(prompt, max_tokens, temperature)
    else:
        raise ValueError(f"Unknown AI_PROVIDER: {provider}. Use 'groq' or 'gemini'.")


def generate_json(prompt: str, max_tokens: int = 8192, temperature: float = 0.9) -> any:
    """Call AI and parse the JSON response. Unwraps wrapper objects to find arrays."""
    text = generate(prompt, max_tokens, temperature)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try extracting from markdown code blocks
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            parsed = json.loads(match.group(1))
        else:
            raise ValueError(f"Failed to parse AI response as JSON: {text[:200]}")

    # Groq's json_object mode wraps arrays in an object like {"scripts": [...]}
    # If we got a dict with a single key whose value is a list, unwrap it
    if isinstance(parsed, dict) and len(parsed) == 1:
        only_value = next(iter(parsed.values()))
        if isinstance(only_value, list):
            return only_value

    return parsed
