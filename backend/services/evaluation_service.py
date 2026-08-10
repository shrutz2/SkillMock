"""Step 6: Answer evaluation with a concrete specificity rubric.

Returns (specificity_score, feedback_text, improvement_text). Scoring counts
objective signals instead of asking the model for a vague 0-1 rating, and the
improvement is constrained to a concrete, answer-appropriate addition (#3).
"""
import json
import re

from llm.client import client
from services import security_service


def evaluate_answer(question, answer, source_chunk):
    # The candidate's answer is free text typed by the user - a direct prompt
    # injection vector, so it is sanitized and delimited before use.
    safe_answer, _ = security_service.sanitize_untrusted(answer, max_len=4000)
    safe_chunk, _ = security_service.prepare_for_llm(source_chunk)

    prompt = f"""Evaluate how SPECIFIC and grounded this interview answer is.

Question: {question}

{security_service.wrap_untrusted(safe_chunk, label="RESUME_CONTEXT")}

{security_service.wrap_untrusted(safe_answer, label="CANDIDATE_ANSWER")}

Count how many of these signals the ANSWER contains:
  (a) a concrete number, metric, or measurable outcome
  (b) a specific technology, technique, or mechanism named
  (c) reasoning for a decision - why this over alternatives, or a real tradeoff
  (d) concrete detail about what was actually done (not generic filler)

Score strictly by signal count:
  3-4 signals -> 0.8-1.0
  2 signals   -> 0.5-0.7
  1 signal    -> 0.2-0.4
  0 signals   -> 0.0-0.1

Give ONE concrete improvement: a specific number, technology, or tradeoff the
answer should have included. Do NOT suggest vague things like "add more detail",
"explain challenges", or "give more context".

Return ONLY valid JSON:
{{"score": <float 0-1>, "signals_found": ["..."], "reason": "<one line>", "improve": "<one line>"}}
"""
    raw = client.generate(prompt) or ""
    data = _extract_json(raw)
    if isinstance(data, dict) and "score" in data:
        score = _clamp01(data.get("score"), 0.3)
        reason = str(data.get("reason") or "").strip() or "Scored on the specificity rubric."
        improve = str(data.get("improve") or "").strip()
        return score, reason, improve

    # Fallback: line-based parse if the model didn't return clean JSON.
    score = _parse_score(raw)
    reason = _parse_field(raw, "reason") or raw.strip().split("\n")[-1].strip()
    improve = _parse_field(raw, "improve") or ""
    return score, reason, improve


def _extract_json(text):
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass
    return None


def _clamp01(v, default=0.0):
    try:
        return max(0.0, min(1.0, float(v)))
    except Exception:
        return default


def _parse_score(text):
    match = re.search(r"score\s*[:=]?\s*([01](?:\.\d+)?|0?\.\d+)", text, re.I)
    if match:
        try:
            return max(0.0, min(1.0, float(match.group(1))))
        except ValueError:
            pass
    match = re.search(r"\b(0?\.\d+|1(?:\.0+)?)\b", text)
    return float(match.group(1)) if match else 0.5


def _parse_field(text, label):
    match = re.search(rf"{label}\s*[:=]\s*(.+)", text, re.I)
    if match:
        return match.group(1).strip().strip('",').split("\n")[0].strip()
    return None
