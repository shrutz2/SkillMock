"""Step 2: Chunking.

Split the resume into meaningful chunks by section (Experience, Projects,
Skills, ...) instead of arbitrary character counts, so each chunk is a coherent
unit. Falls back to paragraph-based chunking when no clear section headers are
found, which guards against the "empty chunks" edge case noted in the build plan.
"""
import re

# Common resume section headers used as split anchors.
_SECTION_HEADERS = re.compile(
    r"(?im)^\s*("
    r"experience|work experience|professional experience|employment|"
    r"projects?|personal projects?|academic projects?|"
    r"skills?|technical skills?|"
    r"education|"
    r"certifications?|achievements?|awards?|"
    r"publications?|summary|objective|profile|"
    r"leadership|activities|interests"
    r")\s*:?\s*$"
)

_MIN_CHUNK_LEN = 40
# Below this, bullet chunking has not found enough to retrieve over and we fall
# back to section chunks rather than indexing two or three fragments.
_MIN_BULLET_CHUNKS = 6


def chunk_resume(text, granularity=None):
    """Return a list of coherent, non-trivial chunks.

    ``granularity`` picks the retrieval unit:

    * ``"section"`` - one chunk per detected section. Yields ~5-8 chunks for a
      typical resume, which means a top-3 search returns most of the document
      and is barely selective.
    * ``"bullet"`` - one chunk per accomplishment bullet, each prefixed with its
      section name so the section context survives. Yields ~20-40 chunks, so
      top-3 actually discriminates.

    Defaults to ``Config.CHUNK_GRANULARITY``. Falls back to section chunks when
    too few bullets are found (sparse or unusually formatted resumes).
    """
    if not text or not text.strip():
        return []

    if granularity is None:
        try:
            from config import Config
            granularity = Config.CHUNK_GRANULARITY
        except Exception:
            granularity = "bullet"

    if granularity == "bullet":
        bullets = chunk_bullets(text)
        if len(bullets) >= _MIN_BULLET_CHUNKS:
            return bullets
        # Not enough bullets to retrieve over - fall through to sections.

    lines = text.splitlines()
    chunks = []
    current = []

    for line in lines:
        if _SECTION_HEADERS.match(line.strip()):
            _flush(current, chunks)
            current = [line.strip()]
        else:
            current.append(line)
    _flush(current, chunks)

    # Fallback: no section headers detected -> split on blank-line paragraphs.
    if len(chunks) <= 1:
        chunks = [
            p.strip()
            for p in re.split(r"\n\s*\n", text)
            if len(p.strip()) >= _MIN_CHUNK_LEN
        ]

    # Final guard: never return nothing for a non-empty resume.
    if not chunks:
        chunks = [text.strip()]

    return chunks


def _flush(buffer, chunks):
    joined = "\n".join(buffer).strip()
    if len(joined) >= _MIN_CHUNK_LEN:
        chunks.append(joined)


# ---------------------------------------------------------------------------
# ATS-style bullet extraction (for resume claim scoring)
# ---------------------------------------------------------------------------
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+?\d[\d\s\-()]{7,}\d)")
_URL = re.compile(r"(https?://|www\.|linkedin\.com|github\.com|\S+\.com/\S*)", re.I)
_DATE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"january|february|march|april|june|july|august|september|october|"
    r"november|december|20\d{2}|19\d{2})\b",
    re.I,
)
# Leading bullet glyphs used in resumes (unicode escapes keep this ASCII-safe).
_BULLET_MARK = re.compile(
    "^\\s*[•●▪‣◦→*\\-–—›·]+\\s*"
)
_ACTION = re.compile(
    r"\b(built|created|implemented|designed|developed|engineered|reduced|improved|"
    r"optimi[sz]ed|scaled|migrated|deployed|automated|led|integrated|trained|"
    r"validated|architected|launched|analy[sz]ed|streamlined|refactored|managed|"
    r"delivered|achieved|increased|decreased|processed|handled)\b",
    re.I,
)
_NUM = re.compile(r"\d")


def _is_noise(s):
    """Contact lines, URLs, and company/date header lines are not bullets."""
    if _EMAIL.search(s) or _URL.search(s):
        return True
    if _PHONE.search(s) and len(s) < 70:
        return True
    if _SECTION_HEADERS.match(s):
        return True
    # Company / date header: short line containing a date, without an action verb.
    if len(s) < 70 and _DATE.search(s) and not _ACTION.search(s):
        return True
    return False


def _title_caseish(s):
    """Most words capitalized -> a company/title/location header, not a bullet."""
    words = [w for w in s.split() if w[:1].isalpha()]
    if len(words) < 2:
        return False
    caps = sum(1 for w in words if w[:1].isupper())
    return caps / len(words) > 0.6


def _is_continuation(prev, cur):
    """A wrapped line: starts lowercase, or the previous line didn't close and
    the current line isn't itself a header/title/date line."""
    if not cur or _is_noise(cur) or _BULLET_MARK.match(cur):
        return False
    if _DATE.search(cur) and len(cur) < 70:  # a date/header line, not a wrap
        return False
    starts_lower = cur[:1].islower()
    prev_open = not prev.rstrip().endswith((".", ":", ";", "!", "?"))
    return starts_lower or (prev_open and not _title_caseish(cur))


def extract_bullets(text):
    """Extract clean, real resume bullets - joining wrapped lines and dropping
    contact info, section headers, company/date lines, and title fragments."""
    if not text:
        return []

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # 1. Merge line-broken (wrapped) bullets.
    merged = []
    for s in lines:
        if _BULLET_MARK.match(s):
            merged.append(_BULLET_MARK.sub("", s).strip())
        elif merged and _is_continuation(merged[-1], s):
            merged[-1] = (merged[-1] + " " + s).strip()
        else:
            merged.append(s)

    # 2. Keep only lines that look like real accomplishment bullets.
    bullets = []
    for s in merged:
        s = _BULLET_MARK.sub("", s).strip()
        if _is_noise(s) or len(s) < 35 or _title_caseish(s):
            continue
        has_action = bool(_ACTION.search(s))
        has_metric = bool(_NUM.search(s))
        if has_action or (has_metric and len(s) >= 50):
            bullets.append(s)

    return bullets


# ---------------------------------------------------------------------------
# Section classifier (ATS-style): label lines by resume section, then only
# achievement-score the Experience/Projects sections.
# ---------------------------------------------------------------------------
_SECTION_MAP = [
    ("skills", re.compile(r"(?i)^(technical\s+skills?|core\s+skills?|skills?|tech(nical)?\s+stack)\s*:?\s*$")),
    ("experience", re.compile(r"(?i)^(work\s+experience|professional\s+experience|experience|employment|internships?|work\s+history)\s*:?\s*$")),
    ("projects", re.compile(r"(?i)^(projects?|personal\s+projects?|academic\s+projects?|selected\s+projects?)\s*:?\s*$")),
    ("education", re.compile(r"(?i)^education\s*:?\s*$")),
    ("certifications", re.compile(r"(?i)^(certifications?|achievements?|awards?|honou?rs?|accomplishments?)\s*:?\s*$")),
    ("summary", re.compile(r"(?i)^(summary|objective|profile|about\s*me?)\s*:?\s*$")),
    # Non-engineering resumes lead with these. Unrecognised, a header is not a
    # boundary at all, so everything under it is absorbed into the section
    # above - an MBA's "Positions of Responsibility" bullets were being indexed
    # and scored as work experience.
    ("leadership", re.compile(
        r"(?i)^(leadership|positions?\s+of\s+responsibility|por|"
        r"extra[\s-]?curriculars?|co[\s-]?curriculars?|activities|"
        r"volunteer(ing)?|community\s+(service|involvement))\s*:?\s*$")),
    ("publications", re.compile(r"(?i)^(publications?|research|papers?|patents?)\s*:?\s*$")),
    ("interests", re.compile(r"(?i)^(interests?|hobbies|languages?|coursework)\s*:?\s*$")),
]

# Sections whose bullets are indexed for retrieval and scored for claim
# strength. Leadership belongs here: for a non-engineering candidate that is
# where the substance lives, and those bullets carry numbers, actions and
# scope just as experience bullets do.
SCORABLE_SECTIONS = ("experience", "projects", "leadership")


def _match_header(line):
    s = line.strip()
    if len(s) > 40:  # section headers are short
        return None
    for name, pat in _SECTION_MAP:
        if pat.match(s):
            return name
    return None


def classify_sections(text):
    """Split a resume into labeled sections. Lines before the first header land
    in ``contact`` (name / phone / email / links)."""
    sections = {}
    current = "contact"
    for raw in (text or "").splitlines():
        if not raw.strip():
            continue
        header = _match_header(raw)
        if header:
            current = header
            continue
        sections.setdefault(current, []).append(raw.rstrip())
    return sections


def chunk_bullets(text):
    """One chunk per bullet, prefixed with its section name.

    The prefix matters: an embedded bullet on its own loses the fact that it
    came from Experience rather than Projects, and that distinction changes
    what a good interview question about it looks like.

    Skills and Education carry no bullets but are still worth retrieving, so
    they are kept whole as single chunks.
    """
    sections = classify_sections(text)
    chunks = []

    for name in SCORABLE_SECTIONS:
        lines = sections.get(name, [])
        if not lines:
            continue
        for bullet in extract_bullets("\n".join(lines)):
            chunks.append(f"{name.capitalize()}: {bullet}")

    # Keep the non-bullet sections as whole chunks so they stay retrievable.
    for name in ("skills", "summary", "certifications", "education",
                 "publications", "interests"):
        lines = sections.get(name, [])
        joined = " ".join(ln.strip() for ln in lines).strip()
        if len(joined) >= _MIN_CHUNK_LEN:
            chunks.append(f"{name.capitalize()}: {joined}")

    return chunks


def get_scorable_bullets(sections):
    """Only Experience/Projects bullets are achievement-scored - never Skills,
    Contact, or Education (matches how real ATS parsers work)."""
    lines = []
    for name in SCORABLE_SECTIONS:
        lines.extend(sections.get(name, []))
    if not lines:
        return []
    return extract_bullets("\n".join(lines))
