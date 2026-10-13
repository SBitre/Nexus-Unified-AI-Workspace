"""
Application logic tier — AI model client.

The application layer's connection to the external AI model shown in the
architecture diagram. Two jobs: turn a question into a structured intent,
and write the summary sentence shown above the results.

Provider-agnostic by design. Gemini and Groq are both reachable over HTTP
with a JSON body, so switching between them is a change to _call_model and
nothing else. The rest of the application tier calls parse_intent and
summarise without knowing which provider answered, or whether a model was
reached at all.

When no API key is configured — the default for this release — both
functions fall back to the deterministic rules in intent.py and a template
summary. The system therefore runs with no credentials and no network,
which keeps the tier boundaries testable. Every result reports whether it
came from the model or the fallback, and that flag is stored in the
request history.
"""

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date

from ..data_access.plugins.base import ServiceKind
from . import intent as rules

# Configuration is read from the environment so no credential is committed.
PROVIDER = os.environ.get("NEXUS_AI_PROVIDER", "none").lower()
API_KEY = os.environ.get("NEXUS_AI_API_KEY", "")
MODEL = os.environ.get("NEXUS_AI_MODEL", "gemini-flash-lite")
TIMEOUT_SECONDS = 8

_ENDPOINTS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
}

_INTENT_PROMPT = """You classify workspace questions. Reply with JSON only, no prose.

Schema:
{{"label": str, "kinds": [str], "days_ahead": int}}

"kinds" may contain any of: mail, calendar, notes, chat. Use an empty list
to mean every service. "days_ahead" is how many days forward the question
covers: 0 for today, 7 for this week.

Question: {question}"""


@dataclass
class ParsedIntent:
    """An intent plus a note of what produced it."""

    intent: rules.Intent
    parsed_by: str  # "model" or "rules"


def is_configured() -> bool:
    """Whether a model provider and key are available."""
    return PROVIDER in _ENDPOINTS and bool(API_KEY)


def _call_model(prompt: str) -> str:
    """Send one prompt and return the model's text. Raises on failure."""
    if PROVIDER == "gemini":
        url = _ENDPOINTS["gemini"].format(model=MODEL) + f"?key={API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        headers = {"Content-Type": "application/json"}
    else:  # groq, OpenAI-compatible
        url = _ENDPOINTS["groq"]
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        }

    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = json.loads(response.read().decode("utf-8"))

    if PROVIDER == "gemini":
        return body["candidates"][0]["content"]["parts"][0]["text"]
    return body["choices"][0]["message"]["content"]


def _strip_fences(text: str) -> str:
    """Remove markdown code fences a model may wrap JSON in."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def parse_intent(question: str, today: date | None = None) -> ParsedIntent:
    """Classify a question, by model where available and by rules otherwise.

    Any failure — no key, a network error, a malformed reply — falls back
    to the rule-based parser rather than failing the request. An assistant
    that answers by simpler means is better than one that errors.
    """
    if not is_configured():
        return ParsedIntent(rules.parse(question, today=today), "rules")

    try:
        raw = _call_model(_INTENT_PROMPT.format(question=question))
        data = json.loads(_strip_fences(raw))

        kinds = {
            ServiceKind(kind)
            for kind in data.get("kinds", [])
            if kind in {k.value for k in ServiceKind}
        }
        window = rules.window_for(int(data.get("days_ahead", 7)), today=today)
        label = str(data.get("label", "model_intent"))[:60]

        return ParsedIntent(
            rules.Intent(label, kinds, window[0], window[1]), "model"
        )
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
        return ParsedIntent(rules.parse(question, today=today), "rules")
