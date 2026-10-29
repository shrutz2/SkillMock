"""Resume analysis: weak-claim detection, company-group fit, and JD fit scoring.

Scoring uses a concrete SPECIFICITY RUBRIC (signal counting) instead of a vague
"rate 0-1" instruction, so the model judges against objective criteria instead
of its own bias toward "needs more detail". Each has a heuristic fallback.
"""
import json
import re

from llm.client import client
from services import chunking_service, security_service

# ---------------------------------------------------------------------------
# Specificity rubric (shared wording so scoring stays consistent)
# ---------------------------------------------------------------------------
_RUBRIC = """STEP 1 - Scan for these 4 signals independently. Check the ENTIRE
bullet text, including the middle and end of the sentence, not just the start:

1. NUMBER: any digit/metric anywhere (e.g. "60 requests/min", "31 tests",
   "12,000 requests", "50-connection", "83%"). Even a count like "31 tests"
   or a benchmark like "12,000 requests/min" counts as a number.
2. TECHNOLOGY: any named tool, framework, library, or protocol
   (e.g. "JUnit 5", "Mockito", "Redis", "AWS EC2")
3. ACTION: a concrete verb describing what was built/done
4. SCOPE: a stated scale or boundary (e.g. "single instance", "6 domains",
   "50 connections")

STEP 2 - Count how many signals you found in Step 1. Call this N.

STEP 3 - The score MUST equal the band for N. Do not override this with your
own judgment:
  N=4 -> 0.85-1.0
  N=3 -> 0.7-0.84
  N=2 -> 0.5-0.69
  N=1 -> 0.2-0.49
  N=0 -> 0.0-0.19"""

# Server-side enforcement of the band, keyed by signal count.
_BANDS = {0: (0.0, 0.19), 1: (0.2, 0.49), 2: (0.5, 0.69), 3: (0.7, 0.84), 4: (0.85, 1.0)}


def _enforce_band(score, count):
    """Clamp the score into the band implied by the signal count, so the model
    can't contradict its own Step-2 tally."""
    if count is None:
        return score
    try:
        n = max(0, min(4, int(count)))
    except (TypeError, ValueError):
        return score
    lo, hi = _BANDS[n]
    return round(min(max(score, lo), hi), 2)

_SUGGESTION_RULE = """For any bullet scoring below 0.5, give ONE improvement that
belongs ON A RESUME: a number/metric to add, a missing technology name, or
clearer scope. Do NOT suggest challenges faced, lessons learned, feedback
received, team dynamics, or anything that belongs in an interview answer."""


def _llm_json(prompt):
    raw = client.generate(prompt) or ""
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except Exception:
            pass
    return None


def _clamp01(v, default=0.0):
    try:
        return max(0.0, min(1.0, float(v)))
    except Exception:
        return default


_SIGNAL_LETTER = {"a": "number", "b": "technology", "c": "action", "d": "scope"}

# Verbs that say what was actually built or changed. Deliberately excludes
# "worked", "collaborated", "helped", "responsible for" and friends, which
# describe presence rather than contribution.
_CONCRETE_ACTION_RE = re.compile(
    r"\b(built|created|implemented|designed|developed|engineered|architected|"
    r"reduced|improved|optimi[sz]ed|scaled|migrated|deployed|automated|"
    r"integrated|trained|refactored|launch(?:ed|ing)|streamlined|eliminated|"
    r"cut|increased|decreased|rebuilt|modelled|modeled|wrote|added|"
    r"negotiated|led|mentored|chaired|organi[sz]ed|delivered|"
    # Non-engineering resumes carry the same weight in different verbs.
    r"grew|ran|conducted|oversaw|drove|established|introduced|raised|"
    r"boosted|generated|secured|managed|analy[sz]ed|consolidated)\b",
    re.I,
)

# Scope means a stated size or boundary, so it needs a count attached to
# something countable - "6 services", "across 42 stores", "a single instance".
# "various projects" and "the team" are not scope.
_SCOPE_EVIDENCE_RE = re.compile(
    # Up to two words may sit between the count and the thing counted -
    # "25 landing pages", "6 regional hubs" - so allow them, but no more,
    # or the number drifts far enough away to stop being that noun's count.
    r"\b\d[\d,.]*\s*(?:\+|k|m)?\s*(?:[a-z-]+\s+){0,2}"
    r"(?:users?|customers?|clients?|vendors?|students?|employees?|analysts?|"
    r"services?|microservices?|instances?|servers?|nodes?|clusters?|regions?|"
    r"stores?|teams?|domains?|endpoints?|apis?|tables?|records?|rows?|files?|"
    r"feeds?|jobs?|pipelines?|tests?|pages?|documents?|repos?|repositories?|"
    r"modules?|partitions?|connections?|attendees?|recruiters?|hubs?|"
    r"verticals?|writers?|stages?|environments?)\b"
    r"|\bacross\s+\d"
    r"|\bsingle[\s-](?:instance|node|server|region)\b",
    re.I,
)


# Verbs that describe presence rather than contribution. A blocklist works
# where an allowlist did not: naming the few weak verbs generalises, naming
# every strong one never will. An allowlist missed "Verified ... by matching"
# on an orbital-mechanics bullet, the third domain it had failed on.
_FILLER_VERBS = {
    "worked", "working", "helped", "helping", "assisted", "assisting",
    "participated", "participating", "collaborated", "collaborating",
    "contributed", "contributing", "supported", "supporting", "engaged",
    "engaging", "gained", "gaining", "involved", "learned", "learning",
    "maintaining", "utilized", "utilised", "using", "responsible",
    "handled", "handling", "ensured", "ensuring", "facilitated",
}
_VERB_SHAPE = re.compile(r"^([A-Za-z]+(?:ed|ing))\b")
_IRREGULAR_VERB = re.compile(
    r"^(built|wrote|led|ran|grew|cut|drove|made|set|took|began|chose|found|"
    r"kept|sent|won|rebuilt|oversaw|drew|held|brought)\b", re.I)


# A named tool shows itself in its shape as well as its name: an acronym
# (SGP4, API, ETL), a CamelCase product, or a capitalised word that is not
# simply starting the sentence. The name list cannot cover every field -
# it had never heard of SGP4 or Vallado.
_TECH_SHAPE = re.compile(r"(?<!^)(?<![.!?]\s)\b([A-Z][A-Za-z]*[0-9][A-Za-z0-9]*"
                         r"|[A-Z]{2,}[0-9]*"
                         r"|[A-Z][a-z]+[A-Z][A-Za-z]*"
                         r"|[A-Z][a-z]{2,})\b")
# Capitalised words that are not technologies.
_NOT_TECH = {"i", "the", "we", "my", "our", "monday", "tuesday", "wednesday",
             "thursday", "friday", "saturday", "sunday", "january", "february",
             "march", "april", "may", "june", "july", "august", "september",
             "october", "november", "december"}


def _tech_by_shape(bullet):
    for m in _TECH_SHAPE.finditer(bullet or ""):
        if m.group(1).lower() not in _NOT_TECH:
            return True
    return False


def verify_action_signal(bullet):
    """A resume bullet opens with what the person did, so judge the opening
    verb rather than hunting for any known verb anywhere in the line."""
    text = (bullet or "").strip()
    # The verb can also follow "by": "Verified accuracy by matching ...".
    for candidate in [text] + [p.strip() for p in re.split(r"\bby\b", text, flags=re.I)[1:]]:
        m = _VERB_SHAPE.match(candidate)
        if m and m.group(1).lower() not in _FILLER_VERBS:
            return True
        if _IRREGULAR_VERB.match(candidate):
            return True
    return False


# Words that, sitting between a count and a noun, mean the noun is not what
# was counted: "40% with Redis" is not scope.
_GAP_STOPWORDS = {"with", "using", "via", "from", "into", "and", "or", "the",
                  "a", "an", "of", "in", "on", "at", "to", "by", "for", "per"}
_COUNT_THEN_PLURAL = re.compile(
    r"\b\d[\d,.]*\s*(?:\+|k|m|%)?\s+((?:[a-z-]+\s+){0,2}[a-z]{3,}s)\b", re.I)


def verify_scope_signal(bullet):
    """Scope is a count attached to something countable. Match that shape -
    a number followed by a plural noun - instead of listing the nouns."""
    text = bullet or ""
    for m in _COUNT_THEN_PLURAL.finditer(text):
        words = m.group(1).lower().split()
        if any(w in _GAP_STOPWORDS for w in words[:-1]):
            continue
        return True
    return bool(_SCOPE_EVIDENCE_RE.search(text))


# Each signal the model claims is checked against the bullet itself. Technology
# is left to the model: a name list can never be complete, and a wrong one
# there costs a single signal rather than a whole band.
_VERIFIERS = {
    "number": lambda b: verify_number_signal(b),
    "action": verify_action_signal,
    "scope": verify_scope_signal,
    "technology": lambda b: bool(_TECH_RE.search(b or "")) or _tech_by_shape(b),
}


def _norm_signals(sigs, bullet=None):
    """Map the model's noisy signal labels (letters, prose, or raw quoted
    evidence like '31 unit tests') to the 4 canonical tags.

    When ``bullet`` is given, a claimed "number" signal is verified against a
    deterministic regex - the LLM's word alone is not trusted.
    """
    out = []
    for s in sigs or []:
        s = str(s).strip().lower()
        if not s:
            continue
        m = re.match(r"^\(?([abcd])\)?[\s:.)-]*$", s)
        if m:
            key = _SIGNAL_LETTER[m.group(1)]
        elif "number" in s or "metric" in s or "outcome" in s or "quantif" in s:
            key = "number"
        elif "tech" in s or "tool" in s or "framework" in s or "librar" in s:
            key = "technology"
        elif "scope" in s or "scale" in s or "boundary" in s:
            key = "scope"
        elif "action" in s or "verb" in s or "built" in s or "done" in s:
            key = "action"
        # Raw evidence quoted from the bullet -> classify by its content.
        elif _NUM_RE.search(s) and _SCOPE_RE.search(s):
            key = "scope"
        elif _NUM_RE.search(s):
            key = "number"
        elif _TECH_RE.search(s):
            key = "technology"
        elif _ACTION_RE.search(s):
            key = "action"
        else:
            continue  # unrecognised - drop instead of show noise
        # Verify the claim against the bullet. The model is generous with
        # ACTION and SCOPE on filler text - it reads "Collaborated" as an
        # action and "various projects" as scope, which scored
        # "Collaborated with the team on various projects" at 0.60.
        if bullet is not None and not _VERIFIERS.get(key, lambda _b: True)(bullet):
            continue
        if key not in out:
            out.append(key)
    return out


# ----------------------------------------------------------------------------
# Resume report: weak claims (#4) + company-group fit (#5) + suggested level
# ----------------------------------------------------------------------------
def resume_report(resume_text, candidate_name=None):
    # ATS-style: classify sections, then only score Experience/Projects bullets.
    # Parsing runs on the original text (kept local); anything sent to the LLM
    # is redacted and sanitized first.
    sections = chunking_service.classify_sections(resume_text)
    bullets = chunking_service.get_scorable_bullets(sections)
    if not bullets:  # header-less resume fallback
        bullets = chunking_service.extract_bullets(resume_text)
    # Keep the findings: a bullet that tried to manipulate the scorer must not
    # be credited for the evidence it planted in itself.
    sanitized = [security_service.sanitize_untrusted(b, max_len=400) for b in bullets[:12]]
    tainted = {b for b, found in sanitized if found}
    bullets = [b for b, _ in sanitized if b]

    if not bullets:
        return {
            "suggested_level": "Junior",
            "weak_claims": [],
            "company_fit": _company_fit_fallback(resume_text),
        }

    numbered = "\n".join(f"{i+1}. {b}" for i, b in enumerate(bullets))
    safe_resume, _audit = security_service.prepare_for_llm(
        resume_text[:3500], name=candidate_name
    )
    prompt = f"""You are an expert technical recruiter. Below are the achievement
bullets extracted from the candidate's EXPERIENCE and PROJECTS sections. Score
each one - do not add or invent bullets, score exactly these in order.

Bullets:
{numbered}

{_RUBRIC}

{_SUGGESTION_RULE}

Then, from the resume below, infer the interview level and company fit.
{security_service.wrap_untrusted(safe_resume)}

Return ONLY valid JSON (no markdown):
{{
  "suggested_level": "Fresher" | "Junior" | "SDE-1",
  "weak_claims": [
    {{"text": "<the bullet>", "signals_found": ["number"|"technology"|"action"|"scope"], "signal_count": <N>, "score": <float 0-1>, "note": "<one resume-appropriate improvement, or empty if score >= 0.5>"}}
  ],
  "company_fit": {{
    "summary": "<2 sentences: what companies this resume suits and why>",
    "groups": [{{"name": "Product companies" | "Startups" | "Service companies", "why": "<one line>"}}],
    "signals": ["<short signal e.g. 'System design: rate limiter'>"]
  }}
}}"""
    data = _llm_json(prompt) or {}
    llm_claims = data.get("weak_claims") if isinstance(data.get("weak_claims"), list) else []

    # We own the bullet list; take the LLM's score by position, fill gaps
    # heuristically. Guarantees one scored claim per extracted bullet.
    claims = []
    for i, b in enumerate(bullets):
        lc = llm_claims[i] if i < len(llm_claims) and isinstance(llm_claims[i], dict) else {}
        score_h, sig_h = _score_bullet_heuristic(b)
        if b in tainted:
            score, signals = _BANDS[0][1], []
            note = ("This line contains text aimed at the scoring system rather "
                    "than describing your work, so it was not scored.")
        elif "score" in lc:
            signals = _norm_signals(lc.get("signals_found") or lc.get("signals"), bullet=b) or sig_h
            # Use the verified count only. Falling back to the model's own
            # signal_count here undid the verification: a bullet whose every
            # claimed signal failed its check still took the model's tally and
            # landed a band or two too high.
            count = len(signals)
            # Band-enforce against the model's own tally, then floor with the
            # heuristic so objective signals can never be under-scored.
            score = max(_enforce_band(_clamp01(lc.get("score"), 0.3), count), score_h)
            note = str(lc.get("note") or "").strip()
        else:
            score, signals = score_h, sig_h
            note = "Add a number/metric, name the specific technology, or state the scope."
        verdict = "specific" if score >= 0.5 else "weak"
        claims.append({
            "text": b[:170],
            "score": round(score, 2),
            "verdict": verdict,
            "signals": signals[:4],
            "note": "" if verdict == "specific" else note,
        })

    company_fit = data.get("company_fit") if isinstance(data.get("company_fit"), dict) else None
    return {
        "suggested_level": data.get("suggested_level") or "Junior",
        "weak_claims": claims,
        "company_fit": company_fit or _company_fit_fallback(resume_text),
    }


_TECH_RE = re.compile(
    r"\b(python|java|javascript|typescript|react|angular|vue|flask|django|fastapi|"
    r"node|express|spring(?:\s*boot)?|mysql|postgres(?:ql)?|mongodb|sqlite|"
    r"redis|kafka|rabbitmq|docker|kubernetes|jenkins|aws|ec2|s3|lambda|gcp|azure|"
    r"firebase|faiss|rag|llm|rest|graphql|grpc|oauth|jwt|"
    r"junit|mockito|pytest|jest|selenium|cypress|"
    r"lstm|cnn|transformer|bert|word2vec|tf-idf|tensorflow|pytorch|scikit-learn|"
    r"pandas|numpy|opencv|spacy|sql|nginx|celery|websocket|git(?:hub|lab)?|linux|"
    r"stable\s*diffusion|terraform|elasticsearch|microservices?|monolith|"
    r"hikaricp|kotlin|swift|golang|\.net|hibernate|kibana|grafana|prometheus)\b", re.I)
# Any digit counts as a number signal (matches the rubric: "31 tests", "12,000 requests/min").
_NUM_RE = re.compile(r"\d")

# --- Deterministic verification of a claimed "number" signal -----------------
# Digits that are NOT achievement metrics: years, dates, phone numbers, and
# version numbers attached to a tool name ("JUnit 5" is a technology signal).
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_PHONE_LIKE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_VERSION = re.compile(r"\b[a-z][\w.+#-]*\s*v?\d+(\.\d+)*\b", re.I)
# Genuine metrics: percentages, units, magnitudes, counts of things, ranges.
_GENUINE_NUM = re.compile(
    r"(\d[\d,.]*\s*%"                                    # 85%
    r"|\d[\d,.]*\s*[km]?\s*(req|rps|qps|tps|ms|sec|s\b|min|hrs?|gb|mb|kb|x\b)"  # 2,000 req/s, 40ms
    r"|\d[\d,.]*\s*[km]\b"                               # 50k
    r"|\d[\d,.]*\s*\+"                                   # 2,500+
    r"|\d[\d,.]*\s*(?:[a-z]+\s+){0,2}[a-z]{3,}s\b"       # 31 tests, 12k labeled samples
    r"|\b\d+\s*-\s*[a-z]+"                               # 50-connection
    r"|\d[\d,.]{2,}"                                     # 12,000
    r")", re.I)


def verify_number_signal(text):
    """Return True only if the bullet contains a *genuine* metric.

    Safety net over the LLM: it may label a year, phone number, or a tool's
    version number as a "number" signal. This deterministic check rejects those
    so a bullet can't be inflated by a digit that isn't an achievement metric.
    """
    if not text:
        return False
    stripped = _PHONE_LIKE.sub(" ", text)
    for m in _GENUINE_NUM.finditer(stripped):
        token = m.group(0)
        # Reject if this match is only a year, or only a tool version.
        if _YEAR.fullmatch(token.strip(" ,.")):
            continue
        start = max(0, m.start() - 24)
        context = stripped[start:m.end()]
        if _VERSION.search(context) and not re.search(r"%|req|rps|ms|\+|,\d{3}", token, re.I):
            # e.g. "JUnit 5" -> technology, not a metric
            if not re.search(r"\d[\d,.]*\s*(?:[a-z]+\s+){0,2}[a-z]{3,}s\b", token, re.I):
                continue
        return True
    return False
_ACTION_RE = re.compile(
    r"\b(built|created|implemented|designed|developed|engineered|reduced|improved|"
    r"optimi[sz]ed|scaled|migrated|deployed|automated|led|integrated|trained|"
    r"validated|architected|launched|analy[sz]ed|streamlined|refactored|wrote|"
    r"delivered|achieved|increased|decreased|processed|handled|configured|tested)\b",
    re.I)
_SCOPE_RE = re.compile(
    r"(\b(across|handling|per\s*(second|min(ute)?|hour|day)|concurrent|throughput|"
    r"single\s+instance|up\s+to|scale[sd]?\s+to)\b"
    # a count followed by a plural noun == a stated scale (e.g. "6 services",
    # "12k labeled samples", "50k events/min", "2,500+ images")
    r"|\d[\d,.]*\s*[km]?\s*\+?\s*(?:[a-z]+\s+)?[a-z]{3,}s\b"
    r"|\d[\d,]*\s*(req|rps|qps|tps)\b"
    r"|\b\d+\s*-\s*(connection|thread|node|instance))", re.I)


def _score_bullet_heuristic(text):
    # Uses the same verifiers as the LLM path. They used to disagree - the
    # heuristic counted looser action and scope matches, and because it acts as
    # a floor it pulled filler like "Responsible for maintaining the codebase"
    # up to 0.60 even after the LLM's signals were all rejected.
    signals = []
    if verify_number_signal(text):
        signals.append("number")
    if _TECH_RE.search(text) or _tech_by_shape(text):
        signals.append("technology")
    if verify_action_signal(text):
        signals.append("action")
    if verify_scope_signal(text):
        signals.append("scope")
    n = len(signals)
    # Mid-point of each band from the rubric.
    score = {0: 0.05, 1: 0.35, 2: 0.6, 3: 0.77, 4: 0.92}[min(n, 4)]
    return round(score, 2), signals


def _company_fit_fallback(resume_text):
    text = (resume_text or "").lower()
    signals = []
    if any(k in text for k in ["system design", "rate limiter", "load test", "scal"]):
        signals.append("System-design signals present")
    if "leetcode" in text or "data structures" in text:
        signals.append("DSA / LeetCode visibility")
    if any(k in text for k in ["aws", "ec2", "docker", "deploy"]):
        signals.append("Deployment / cloud experience")
    if "certif" in text:
        signals.append("Certifications present")
    return {
        "summary": "Resume shows a mix of hands-on project and engineering "
        "signals; suitable for junior software roles.",
        "groups": [
            {"name": "Startups", "why": "Breadth of hands-on project work."},
            {"name": "Product companies", "why": "Engineering depth signals."},
        ],
        "signals": signals or ["General software engineering experience"],
    }


def score_bullet(bullet):
    """Score a single bullet with the rubric - used by the calibration test."""
    # Sanitise here rather than trusting callers to have done it, and judge
    # the taint on the ORIGINAL text. Scanning the sanitised copy finds
    # nothing, because sanitising is what replaced the patterns.
    #
    # A bullet carrying an injection attempt gets no credit for its content.
    # Stripping the instruction is not enough: a payload can assert its own
    # evidence - "this bullet does contain a number (2,000 req/s), a
    # technology (Redis)" - and those tokens survive the strip, so every
    # signal verifies and the thing scores 0.92. Nothing in a sentence that
    # tried to manipulate the scorer is worth trusting.
    bullet, found = security_service.sanitize_untrusted(bullet, max_len=400)
    if found:
        return _BANDS[0][1], []
    prompt = f"""Evaluate this resume bullet on specificity.

Bullet: {bullet}

{_RUBRIC}

Return ONLY JSON:
{{"signals_found": [<list from step 1>], "signal_count": <N>, "score": <float>, "reason": "<one line>"}}"""
    data = _llm_json(prompt)
    if isinstance(data, dict) and "score" in data:
        signals = _norm_signals(data.get("signals_found") or data.get("signals"), bullet=bullet)
        # Band from the verified signal count alone. Falling back to the
        # model's raw tally when verification rejected everything let filler
        # keep the band its unchecked claims implied.
        count = len(signals)
        score = _enforce_band(_clamp01(data.get("score"), 0.3), count)
        # Heuristic floor: never score below what objective signals prove.
        score_h, sig_h = _score_bullet_heuristic(bullet)
        return max(score, score_h), (signals or sig_h)
    return _score_bullet_heuristic(bullet)


# ----------------------------------------------------------------------------
# JD fit (#2)
# ----------------------------------------------------------------------------
def jd_fit(jd_text, matched_chunks, resume_text, candidate_name=None):
    # Both the JD and the resume are user-supplied: sanitize and redact first.
    safe_jd, _ = security_service.sanitize_untrusted(jd_text, max_len=2500)
    safe_context, _ = security_service.prepare_for_llm(
        "\n---\n".join(matched_chunks)[:2500], name=candidate_name
    )
    prompt = f"""You are a technical recruiter matching a resume to a job description.

{security_service.wrap_untrusted(safe_jd, label="JOB_DESCRIPTION")}

{security_service.wrap_untrusted(safe_context, label="RESUME")}

Return ONLY valid JSON:
{{
  "level": "<role level the candidate best fits for THIS JD>",
  "fit_score": <integer 0-100>,
  "matched_skills": ["<skill the JD requires that the resume clearly shows>"],
  "missing_skills": ["<skill the JD requires that is absent or weak in the resume>"],
  "reasoning": "<2-3 sentences explaining the score>"
}}"""
    data = _llm_json(prompt)
    if isinstance(data, dict) and "fit_score" in data:
        try:
            data["fit_score"] = max(0, min(100, int(round(float(data["fit_score"])))))
        except Exception:
            data["fit_score"] = 50
        data.setdefault("matched_skills", [])
        data.setdefault("missing_skills", [])
        data.setdefault("level", "Junior")
        data.setdefault("reasoning", "")
        return data
    return _fallback_fit(jd_text, resume_text)


def _tokens(text):
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]{1,}", (text or "").lower()))


def _fallback_fit(jd_text, resume_text):
    jd = _tokens(jd_text)
    res = _tokens(resume_text)
    vocab = {
        "python", "java", "javascript", "react", "flask", "django", "node",
        "mysql", "postgres", "redis", "kafka", "docker", "kubernetes", "aws",
        "faiss", "rag", "llm", "rest", "api", "sql", "git", "linux", "ml",
        "tensorflow", "pytorch", "spring", "microservices", "graphql",
    }
    jd_skills = jd & vocab
    matched = sorted(jd_skills & res)
    missing = sorted(jd_skills - res)
    denom = len(jd_skills) or 1
    score = round(100 * len(matched) / denom)
    return {
        "level": "Junior" if score >= 50 else "Fresher",
        "fit_score": score,
        "matched_skills": matched,
        "missing_skills": missing,
        "reasoning": f"{len(matched)} of {denom} JD skills detected in the resume "
        "(keyword-based estimate).",
    }
