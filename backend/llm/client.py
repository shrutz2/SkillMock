"""Swappable LLM client.

The RAG logic does not depend on which LLM is called, so the provider is a
single configurable component (architecture: "a swappable component"). Supports:

  * groq   - OpenAI-compatible chat completions (free tier)
  * gemini - Google Generative Language REST API (free tier)
  * mock   - deterministic offline responses so the app runs with no API key

Provider is chosen by Config.LLM_PROVIDER, with automatic fallback to mock when
the selected provider has no API key configured.
"""
import json
import re

import requests

from config import Config

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class LLMClient:
    def __init__(self):
        self.provider = Config.LLM_PROVIDER
        # Fall back to mock if a real provider is selected without a key.
        if self.provider == "groq" and not Config.GROQ_API_KEY:
            self.provider = "mock"
        if self.provider == "gemini" and not Config.GEMINI_API_KEY:
            self.provider = "mock"

    def generate(self, prompt):
        try:
            if self.provider == "groq":
                return self._groq(prompt)
            if self.provider == "gemini":
                return self._gemini(prompt)
        except Exception as exc:  # network / quota / parse errors -> graceful mock
            print(f"[llm] provider '{self.provider}' failed ({exc}); using mock.")
        return self._mock(prompt)

    # --- Providers ----------------------------------------------------------
    def _groq(self, prompt):
        resp = requests.post(
            _GROQ_URL,
            headers={
                "Authorization": f"Bearer {Config.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": Config.GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def _gemini(self, prompt):
        url = _GEMINI_URL.format(model=Config.GEMINI_MODEL)
        resp = requests.post(
            url,
            params={"key": Config.GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    # --- Offline fallback ---------------------------------------------------
    def _mock(self, prompt):
        """Deterministic, prompt-aware stand-in for a real LLM."""
        if "<CANDIDATE_ANSWER_DATA>" in prompt:
            answer = _extract_block(
                prompt, "<CANDIDATE_ANSWER_DATA>", end="</CANDIDATE_ANSWER_DATA>"
            )
            score = _heuristic_specificity(answer)
            reason = (
                "Answer includes concrete detail and reasoning."
                if score >= 0.6
                else "Answer is fairly generic."
            )
            improve = (
                "Solid - a metric or tradeoff would make it even stronger."
                if score >= 0.6
                else "Add a concrete number, name the specific technology, or state a tradeoff."
            )
            return json.dumps(
                {"score": score, "signals_found": [], "reason": reason, "improve": improve}
            )

        # Question generation
        excerpt = _extract_block(
            prompt, "<RESUME_EXCERPT_DATA>", end="</RESUME_EXCERPT_DATA>"
        )
        topic = _guess_topic(excerpt)
        return (
            f"You mentioned {topic}. Walk me through one specific technical "
            f"decision you made there - what were the alternatives, and why did "
            f"you choose this approach?"
        )


# ----------------------------------------------------------------------------
# Mock helpers
# ----------------------------------------------------------------------------
def _extract_block(prompt, label, end=None):
    idx = prompt.find(label)
    if idx == -1:
        return prompt.strip()[:400]
    rest = prompt[idx + len(label):]
    if end:
        e = rest.find(end)
        if e != -1:
            rest = rest[:e]
    return rest.strip()[:600]


def _guess_topic(excerpt):
    excerpt = (excerpt or "").strip()
    lines = [ln.strip() for ln in excerpt.splitlines() if ln.strip()]
    # Prefer a substantive line over a short section header (e.g. "Skills").
    for ln in lines:
        if len(ln) > 24:
            return ln[:90]
    return lines[0][:90] if lines else "this project"


def _heuristic_specificity(answer):
    answer = (answer or "").strip()
    if not answer:
        return 0.0
    score = 0.3
    if re.search(r"\d", answer):            # contains numbers / metrics
        score += 0.25
    if len(answer.split()) > 40:            # substantive length
        score += 0.2
    if re.search(
        r"\b(because|therefore|tradeoff|trade-off|instead|chose|decided|latency|"
        r"throughput|optimiz|scaled|reduced|improved)\b",
        answer,
        re.I,
    ):
        score += 0.25
    return round(min(score, 1.0), 2)


# module-level singleton
client = LLMClient()
