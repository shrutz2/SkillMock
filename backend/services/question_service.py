"""Step 5: Question generation (LLM call), grounded in a retrieved chunk and
calibrated to the target role level (#1)."""
from llm.client import client
from services import security_service

# Per-level guidance woven into the prompt.
_LEVEL_GUIDANCE = {
    "Fresher": (
        "The candidate is a FRESHER. Ask a fundamentals-level question that checks "
        "they genuinely understand the basics of what they built - core concepts, "
        "why a tool was used. Avoid deep system-design or scaling tradeoffs."
    ),
    "Junior": (
        "The candidate is a JUNIOR / SDE-0 to SDE-1. Ask about a specific technical "
        "decision and its immediate tradeoff - why one approach over another, a "
        "concrete number, or a bug they hit."
    ),
    "SDE-1": (
        "The candidate is at SDE-1 level. Ask a question that pushes into design "
        "tradeoffs, scaling, failure modes, or how the choice would change under "
        "more load - while staying grounded in what they actually built."
    ),
}


def generate_question(chunk_text, role_level=None, avoid=None):
    guidance = _LEVEL_GUIDANCE.get(role_level, _LEVEL_GUIDANCE["Junior"])
    safe_chunk, _ = security_service.prepare_for_llm(chunk_text)

    avoid_clause = ""
    if avoid:
        joined = "\n".join("- " + a for a in avoid[-8:])
        avoid_clause = (
            "\nThese questions have already been asked. Ask about a DIFFERENT "
            "detail, angle, or tradeoff - do not repeat or paraphrase them:\n"
            f"{joined}\n"
        )

    prompt = f"""
{guidance}
{avoid_clause}
Based on this resume excerpt, generate ONE specific technical interview
question that tests whether the candidate deeply understands what they
built. Avoid generic questions -- anchor it to a specific technical decision,
number, or tradeoff mentioned in the text. Return only the question.

{security_service.wrap_untrusted(safe_chunk, label="RESUME_EXCERPT")}

Question:
"""
    return _clean(client.generate(prompt))


def _clean(text):
    """Strip common LLM preambles and wrapping quotes so only the question shows."""
    q = (text or "").strip()
    # Drop a leading "Here's a question:" style preamble line.
    if "\n" in q:
        first, rest = q.split("\n", 1)
        if first.rstrip().endswith(":") and "?" not in first:
            q = rest.strip()
    return q.strip().strip('"').strip("'").strip()
