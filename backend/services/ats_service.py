"""ATS analysis, split into two separate scores.

1. PARSING SAFETY  - deterministic, JD-independent. Measures whether an ATS can
   correctly EXTRACT the resume's text and structure. Critical checks are
   weighted so a critical failure caps the score below 80.
2. JD MATCH        - the ONLY place a match percentage appears, because ATS
   keyword matching is inherently job-specific. Returns None without a JD;
   we never invent a number.

Content-quality signals (e.g. "are bullets quantified") intentionally live in the
claim-strength report, not here - this score is about parseability only.
"""
import re

from services import chunking_service

HARD_SKILLS = {
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "ruby", "php", "sql", "kotlin", "swift", "scala", "bash", "matlab",
    "react", "angular", "vue", "node.js", "node", "express", "flask", "django",
    "fastapi", "spring", "spring boot", "next.js", "redux", "html", "css",
    "tailwind", "bootstrap", "jquery",
    "pandas", "numpy", "tensorflow", "pytorch", "scikit-learn", "keras", "nlp",
    "opencv", "word2vec", "tf-idf", "lstm", "cnn", "transformer", "spacy",
    "machine learning", "deep learning",
    "mysql", "postgresql", "postgres", "mongodb", "redis", "sqlite", "oracle",
    "dynamodb", "cassandra", "elasticsearch", "firebase",
    "aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "git", "github",
    "gitlab", "ci/cd", "terraform", "linux", "nginx", "kafka", "rabbitmq",
    "rest", "rest api", "graphql", "microservices", "oop", "data structures",
    "algorithms", "system design", "agile", "scrum", "unit testing", "tdd",
    "junit", "mockito", "pytest", "selenium", "faiss", "rag", "llm", "api",
}
SOFT_SKILLS = {
    "leadership", "communication", "teamwork", "collaboration", "problem solving",
    "time management", "adaptability", "critical thinking", "mentoring",
    "ownership", "attention to detail", "analytical",
}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3,5}\)?[\s-]?)?\d{3}[\s-]?\d{3,4})")
_LINKEDIN = re.compile(r"linkedin\.com/[\w\-/]+", re.I)
_GITHUB = re.compile(r"github\.com/[\w\-/]+", re.I)


def _skill_present(skill, text):
    if any(ch in skill for ch in "+#./ "):
        return skill in text
    return re.search(rf"\b{re.escape(skill)}\b", text) is not None


def _find_skills(text, vocab):
    t = (text or "").lower()
    return sorted({s for s in vocab if _skill_present(s, t)})


def _extract_contact(text, sections):
    name = ""
    for ln in sections.get("contact", [])[:3]:
        s = ln.strip()
        if s and not _EMAIL.search(s) and not _LINKEDIN.search(s) \
                and not _GITHUB.search(s) and not _PHONE.search(s) and len(s.split()) <= 5:
            name = s
            break
    return {
        "name": name,
        "email": bool(_EMAIL.search(text)),
        "phone": bool(_PHONE.search(text)),
        "linkedin": bool(_LINKEDIN.search(text)),
        "github": bool(_GITHUB.search(text)),
    }


# ---------------------------------------------------------------------------
# 1. Parsing Safety Score (deterministic, no JD)
# ---------------------------------------------------------------------------
def parsing_safety_score(resume_text, sections=None, parse_meta=None):
    text = resume_text or ""
    sections = sections if sections is not None else chunking_service.classify_sections(text)
    meta = parse_meta or {}
    contact = _extract_contact(text, sections)
    words = len(text.split())
    present = {k for k, v in sections.items() if v and k != "contact"}

    checks = []

    def add(name, passed, weight, detail):
        # ``passed is None`` -> undeterminable; omit instead of assume a pass.
        if passed is None:
            return
        checks.append({"name": name, "passed": bool(passed), "weight": weight, "detail": detail})

    add("Machine-readable text", words >= 60, "critical",
        f"{words} words extracted" if words >= 60
        else "Almost no text extracted - likely a scanned/image PDF an ATS cannot read")

    multi = meta.get("multi_column")
    add("No tables/columns detected", (not multi) if multi is not None else None, "critical",
        "Single-column layout" if not multi else "Multi-column layout detected - ATS often scrambles column order")

    add("Standard section headers", len(present) >= 3, "critical",
        f"{len(present)} sections detected ({', '.join(sorted(present)) or 'none'})")

    add("Contact info parsed from body", contact["email"] or contact["phone"], "critical",
        "Contact details found in the document body"
        if (contact["email"] or contact["phone"])
        else "No email/phone found in body text - if it's in a header/footer, ATS may miss it")

    tii = meta.get("has_text_in_images")
    add("No text locked inside images", (not tii) if tii is not None else None, "critical",
        "No image-embedded text detected" if not tii
        else "Text appears to be inside an image - ATS cannot read it")

    fonts = meta.get("font_is_standard")
    add("Standard fonts used", fonts, "minor",
        "Standard, parser-safe fonts" if fonts else "Non-standard fonts may not map to text correctly")

    # --- Weighted score: a critical failure caps the score below 80 ---
    crit = [c for c in checks if c["weight"] == "critical"]
    minor = [c for c in checks if c["weight"] == "minor"]
    crit_pass = sum(1 for c in crit if c["passed"])
    if not crit:
        score = 0
    elif crit_pass < len(crit):
        score = int((crit_pass / len(crit)) * 80)
    else:
        minor_pass = sum(1 for c in minor if c["passed"])
        score = 80 + int((minor_pass / max(len(minor), 1)) * 20)

    return {
        "score": score,
        "label": "Parsing Safety Score",
        "checks": checks,
        "checks_passed": sum(1 for c in checks if c["passed"]),
        "checks_total": len(checks),
        "critical_failed": [c["name"] for c in crit if not c["passed"]],
        "contact": contact,
        "sections_found": sorted(present),
        "disclaimer": "This measures whether your resume can be read correctly by "
                      "ATS software. It does NOT measure keyword match - that "
                      "depends on the specific job you apply to.",
    }


# ---------------------------------------------------------------------------
# 2. JD Match (only with a job description - never faked)
# ---------------------------------------------------------------------------
def jd_match_score(resume_text, jd_text):
    if not jd_text or not jd_text.strip():
        return None  # explicitly no score without a JD

    required = _find_skills(jd_text, HARD_SKILLS)
    resume_skills = set(_find_skills(resume_text, HARD_SKILLS))
    matched = [s for s in required if s in resume_skills]
    missing = [s for s in required if s not in resume_skills]
    pct = int(round(100 * len(matched) / len(required))) if required else 0

    return {
        "score": pct,
        "label": "Job Description Match",
        "matched_keywords": matched,
        "missing_keywords": missing,
        "required_count": len(required),
        "disclaimer": "This score is specific to the job description provided. "
                      "It will differ for every job you apply to.",
    }


def ats_report(resume_text, jd_text=None, parse_meta=None):
    sections = chunking_service.classify_sections(resume_text or "")
    return {
        "parsing": parsing_safety_score(resume_text, sections, parse_meta),
        "jd_match": jd_match_score(resume_text, jd_text),
        "skills": {
            "hard": _find_skills(resume_text, HARD_SKILLS),
            "soft": _find_skills(resume_text, SOFT_SKILLS),
        },
    }
