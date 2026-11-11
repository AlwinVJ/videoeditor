import json
import re
from typing import List, Dict, Any, Optional
from groq import Groq, AuthenticationError, APIConnectionError, RateLimitError, APIStatusError

from core.config import get_groq_api_key

DEFAULT_KEYWORD_MODEL = "openai/gpt-oss-20b"

SYSTEM_PROMPT = (
    "You are an expert video editor and visual director specializing in B-roll stock footage curation.\n"
    "Your task is to analyze the provided video transcript and generate 8 to 15 concise, high-relevance visual search keywords or phrases.\n"
    "Each keyword should represent concrete visual footage suitable for searching stock libraries (e.g. Pexels, Pixabay, Shutterstock).\n\n"
    "Guidelines:\n"
    "- Focus on concrete visual subjects, actions, settings, and objects (e.g., 'person typing on laptop', 'modern office meeting', 'city skyline at dusk', 'data analytics dashboard').\n"
    "- Avoid abstract words, generic filler, punctuation, or conversational commentary.\n"
    "- Output ONLY a valid JSON array of strings, for example: [\"keyword 1\", \"keyword 2\", \"keyword 3\"].\n"
    "- Do not include any introductory or concluding text."
)


def extract_text_from_transcript(transcript: Optional[List[Dict[str, Any]]]) -> str:
    """
    Extract and concatenate spoken text from a list of transcript segment dictionaries.

    Args:
        transcript: List of segment dictionaries with 'text' field.

    Returns:
        Combined transcript text string.
    """
    if not transcript:
        return ""

    text_parts = []
    for segment in transcript:
        if isinstance(segment, dict) and "text" in segment:
            text = str(segment["text"]).strip()
            if text:
                text_parts.append(text)

    return " ".join(text_parts).strip()


def parse_keywords_response(content: str) -> List[str]:
    """
    Parse the LLM completion response into a list of clean keyword strings.
    Handles valid JSON arrays, markdown code fences, and fallback list formatting.

    Args:
        content: Raw text returned by the LLM.

    Returns:
        Deduplicated list of cleaned keyword strings.
    """
    if not content or not content.strip():
        return []

    raw_items: List[str] = []

    # Attempt 1: Extract JSON array from text
    match = re.search(r"\[[\s\S]*?\]", content)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, str):
                        raw_items.append(item)
                    elif isinstance(item, dict) and "keyword" in item:
                        raw_items.append(str(item["keyword"]))
        except json.JSONDecodeError:
            pass

    # Attempt 2: Fallback to line-by-line / bullet point parsing
    if not raw_items:
        lines = content.strip().splitlines()
        for line in lines:
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("```"):
                continue
            # Strip markdown list markers and prefixes: "-", "*", "1.", "- 1.", etc.
            cleaned = re.sub(r"^[\s\-\*\•\d\.\)]+", "", cleaned).strip()
            cleaned = cleaned.strip("[]\",'")
            if cleaned:
                raw_items.append(cleaned)

    # Clean, trim, and deduplicate case-insensitively while preserving order
    seen = set()
    cleaned_keywords: List[str] = []
    for item in raw_items:
        kw = re.sub(r'["\'`]', "", item).strip()
        if not kw or len(kw) < 2:
            continue
        lower_kw = kw.lower()
        if lower_kw not in seen:
            seen.add(lower_kw)
            cleaned_keywords.append(kw)

    return cleaned_keywords


def generate_keywords_from_transcript(
    transcript: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    model: str = DEFAULT_KEYWORD_MODEL,
) -> List[str]:
    """
    Generate visual B-roll search keywords from a video transcript using Groq LLM.

    Args:
        transcript: List of segment dictionaries containing 'text'.
        api_key: Optional Groq API key override. If None, loaded from config.
        model: Groq chat model identifier (default: llama-3.3-70b-versatile).

    Returns:
        List of visual stock footage keyword phrases.

    Raises:
        ValueError: If transcript contains no spoken text.
        PermissionError: If Groq authentication fails.
        ConnectionError: If network connection fails.
        RuntimeError: If rate limit exceeded or API error occurs.
    """
    transcript_text = extract_text_from_transcript(transcript)
    if not transcript_text:
        raise ValueError("Transcript does not contain any spoken text to analyze.")

    resolved_key = api_key or get_groq_api_key()
    client = Groq(api_key=resolved_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Transcript:\n{transcript_text}"},
            ],
            temperature=0.3,
            max_tokens=600,
        )
    except AuthenticationError as e:
        raise PermissionError(
            "Groq authentication failed. Please check that your GROQ_API_KEY in .env or Streamlit Secrets is valid."
        ) from e
    except RateLimitError as e:
        raise RuntimeError(
            "Groq API rate limit exceeded. Please wait a moment before trying again."
        ) from e
    except APIConnectionError as e:
        raise ConnectionError(
            "Could not connect to Groq API. Please verify your internet connection."
        ) from e
    except APIStatusError as e:
        raise RuntimeError(
            f"Groq API error ({e.status_code}): {e.message}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Keyword generation failed: {str(e)}") from e

    choices = getattr(response, "choices", [])
    if not choices:
        return []

    message = getattr(choices[0], "message", None)
    if not message:
        return []

    content = getattr(message, "content", "") or ""
    return parse_keywords_response(content)
