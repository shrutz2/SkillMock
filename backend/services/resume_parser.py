"""Step 1: Resume upload & parsing (PDF -> text) plus PDF-level ATS diagnostics.

Text is cleaned of extraction artifacts (leading line numbers, stray control
chars) before anything downstream sees it, so the LLM never scores noise.
"""
import re

import PyPDF2

# Fonts ATS parsers handle reliably.
_STANDARD_FONTS = (
    "arial", "helvetica", "times", "timesnewroman", "calibri", "cambria",
    "georgia", "garamond", "verdana", "tahoma", "trebuchet", "courier",
    "bookantiqua", "palatino", "lato", "roboto", "opensans", "segoeui",
    # LaTeX defaults - extremely common on engineering resumes.
    "latinmodern", "lmroman", "lmsans", "cmr", "computermodern", "charter",
    # Widely used UI/Google fonts that extract cleanly.
    "inter", "montserrat", "poppins", "sourcesans", "sourceserif", "notosans",
    "nunito", "raleway", "merriweather", "ptsans", "ptserif", "firasans",
    "ibmplexsans", "ibmplexserif", "worksans", "rubik", "karla", "mulish",
    "dejavu", "liberation", "nimbus", "jostpoppins", "publicsans",
)

# "  12  Built a service..." / "12\tBuilt..." / "12 | Built..."
_LINE_NO = re.compile("^\\s{0,6}\\d{1,3}\\s*[\\t|.)]?\\s{1,}(?=[A-Za-z•●▪‣◦→\\-])")
_PAGE_MARK = re.compile(r"^\s*(page\s*\d+\s*(of\s*\d+)?|\-\s*\d+\s*\-)\s*$", re.I)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def strip_extraction_artifacts(text):
    """Remove PDF-extraction noise: leading line numbers, page markers, control
    characters, and runaway blank lines."""
    if not text:
        return ""
    text = _CTRL.sub(" ", text)
    text = text.replace(" ", " ").replace("﻿", "")

    out = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if _PAGE_MARK.match(line):
            continue
        line = _LINE_NO.sub("", line)
        # collapse runs of spaces but keep column gaps detectable elsewhere
        out.append(re.sub(r"[ \t]{4,}", "   ", line))

    cleaned = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def extract_text(pdf_file):
    """Extract cleaned text from a PDF file object or path."""
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += (page.extract_text() or "") + "\n"
    return strip_extraction_artifacts(text)


# ---------------------------------------------------------------------------
# PDF-level diagnostics (used by the Parsing Safety score)
# ---------------------------------------------------------------------------
def _fonts_are_standard(reader):
    names = []
    try:
        for page in reader.pages:
            res = page.get("/Resources")
            if not res:
                continue
            fonts = res.get_object().get("/Font")
            if not fonts:
                continue
            for ref in fonts.get_object().values():
                base = ref.get_object().get("/BaseFont")
                if base:
                    names.append(str(base))
    except Exception:
        return None  # can't tell -> omit the check instead of fake it
    if not names:
        return None
    norm = [re.sub(r"^/?[A-Z]{6}\+", "", n).replace("/", "").replace("-", "").replace(" ", "").lower()
            for n in names]
    # Requiring EVERY font to be on the list failed any resume built in LaTeX
    # (Latin Modern) or with a modern UI font, even though its text extracted
    # perfectly. Judge the body instead: if most fonts are parser-safe, the
    # document is parser-safe.
    known = sum(1 for n in norm if any(std in n for std in _STANDARD_FONTS))
    return (known / len(norm)) >= 0.5


def _has_images(reader):
    try:
        for page in reader.pages:
            res = page.get("/Resources")
            if not res:
                continue
            xobj = res.get_object().get("/XObject")
            if not xobj:
                continue
            for ref in xobj.get_object().values():
                if ref.get_object().get("/Subtype") == "/Image":
                    return True
        return False
    except Exception:
        return None


_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_MONTH_WORD = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b", re.I
)
_TENURE_WORD = re.compile(r"\b(?:present|current|ongoing|remote|hybrid|on-?site)\b", re.I)


def _is_right_aligned_tail(s):
    """True when the text after a wide gap is a when/where, not a second column.

    The standard single-column resume right-aligns a date range, a year, or a
    city against the role on the left - "Backend Engineer     Aug 2023 - Present".
    A real second column instead carries prose or a skills list there.

    A regex over date formats turned out to be the wrong tool: it kept missing
    common shapes like "Jan 2025 - Jun 2025 | Pune". Two cheap properties
    separate the cases reliably - a tail is SHORT, and it mentions a date.
    """
    if len(s) > 44 or len(s.split()) > 7:
        return False
    return bool(_YEAR.search(s) or _MONTH_WORD.search(s) or _TENURE_WORD.search(s))


def _looks_multi_column(text):
    """Detect a genuine two-column layout.

    The naive test - "a wide gap on many lines" - fires on the most common
    resume format there is, where the role sits left and the date or city is
    right-aligned with spaces. That is single-column text and an ATS reads it
    fine, so counting it as a column failure penalises good resumes.

    A real second column instead leaves substantive text on BOTH sides of the
    gap, line after line. So a gap only counts when the right-hand side is long
    enough to be prose and does not look like a right-aligned date or place.
    """
    lines = [ln.rstrip() for ln in (text or "").splitlines() if len(ln.strip()) > 25]
    if len(lines) < 8:
        return False

    gapped = 0
    for ln in lines:
        # extract_text() collapses runs of 4+ spaces down to exactly 3, so the
        # threshold has to be 3 here. At 5 this check could never fire on real
        # extracted text and the column test was silently dead.
        m = re.search(r"\S {3,}(\S.*)$", ln)
        if not m:
            continue
        left = ln[:m.start(1)].strip()
        right = m.group(1).strip()
        # Both sides must carry real content, and the right side must not be
        # the usual right-aligned date / location tail.
        if len(left) < 15 or len(right) < 24:
            continue
        if _is_right_aligned_tail(right):
            continue
        gapped += 1

    return gapped / len(lines) > 0.35


def analyze_pdf(pdf_file, text):
    """Return ATS-relevant structural facts about the PDF.

    Values may be ``None`` meaning "could not determine" - callers omit those
    checks instead of assuming a pass.
    """
    meta = {
        "font_is_standard": None,
        "has_images": None,
        "has_text_in_images": None,
        "multi_column": _looks_multi_column(text),
        "word_count": len((text or "").split()),
    }
    try:
        pdf_file.seek(0)
        reader = PyPDF2.PdfReader(pdf_file)
        meta["font_is_standard"] = _fonts_are_standard(reader)
        has_img = _has_images(reader)
        meta["has_images"] = has_img
        # An image-heavy page with almost no extractable text == text locked in
        # an image, which ATS cannot read.
        if has_img is not None:
            meta["has_text_in_images"] = bool(has_img and meta["word_count"] < 120)
    except Exception:
        pass
    return meta
