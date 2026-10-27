"""Step 1: Resume upload & parsing (PDF -> text) plus PDF-level ATS diagnostics.

Text is cleaned of extraction artifacts (leading line numbers, stray control
chars) before anything downstream sees it, so the LLM never scores noise.
"""
import re

import PyPDF2

# Fonts ATS parsers handle reliably.
# The PDF base-14 faces. A viewer knows these without an embedded program, so
# they need no ToUnicode map to extract correctly.
_BASE_14 = (
    "helvetica", "arial", "times", "courier", "symbol", "zapfdingbats",
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
_SAFE_ENCODINGS = ("/WinAnsiEncoding", "/MacRomanEncoding", "/StandardEncoding")


def _fonts_are_standard(reader):
    """Whether every font can be mapped back to characters.

    An earlier version policed the typeface NAME against a list. That was
    measuring the wrong thing twice over: it failed LaTeX and modern UI fonts
    whose text extracts perfectly, and it passed documents where one unused
    standard font sat alongside the real one.

    A non-standard typeface is not a parsing problem - an embedded TTF reads
    fine. What actually breaks extraction is an embedded font with no
    ToUnicode map and no standard encoding, where glyphs cannot be resolved
    back to characters and the text comes out as mojibake. Check for that.
    """
    fonts = []
    try:
        for page in reader.pages:
            res = page.get("/Resources")
            if not res:
                continue
            fd = res.get_object().get("/Font")
            if not fd:
                continue
            for ref in fd.get_object().values():
                fonts.append(ref.get_object())
    except Exception:
        return None  # can't tell -> omit the check instead of fake it
    if not fonts:
        return None

    for f in fonts:
        base = str(f.get("/BaseFont") or "")
        norm = (re.sub(r"^/?[A-Z]{6}\+", "", base)
                .replace("/", "").replace("-", "").replace(" ", "").lower())
        if any(std in norm for std in _BASE_14):
            continue  # a built-in face; the viewer already knows its encoding
        if f.get("/ToUnicode") is not None:
            continue  # embedded, but carries a glyph-to-character map
        if str(f.get("/Encoding") or "") in _SAFE_ENCODINGS:
            continue
        return False
    return True


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


def _columns_from_layout(reader):
    """Detect a two-column layout from where text actually sits on the page.

    The text-gap test cannot see this case at all: PyPDF2 emits one column
    then the other, so the extracted string has no wide gaps even though the
    page clearly has two columns. Reading the x position of each text run
    finds it - a two-column page has two tight clusters of left edges with a
    real gutter between them, each carrying a substantial share of the lines.

    Returns None when positions are unavailable, so the check is omitted
    rather than guessed.
    """
    xs = []
    try:
        for page in reader.pages:
            width = float(page.mediabox.width) or 595.0

            def visitor(txt, cm, tm, font_dict, font_size, _xs=xs, _w=width):
                if txt and txt.strip():
                    _xs.append(tm[4] / _w)  # left edge as a fraction of width

            page.extract_text(visitor_text=visitor)
    except Exception:
        return None
    if len(xs) < 10:
        return None

    # Split at the widest gap between left edges rather than a fixed position:
    # the gutter sits wherever the design put it, and a hardcoded midpoint
    # misses a narrow left rail entirely.
    uniq = sorted(set(round(x, 3) for x in xs))
    if len(uniq) < 2:
        return False
    # Split at the midpoint of the gap, not at its lower edge - the edge came
    # from a rounded value, so the unrounded positions all fall on one side.
    gaps = [(uniq[i + 1] - uniq[i], (uniq[i] + uniq[i + 1]) / 2)
            for i in range(len(uniq) - 1)]
    gutter, split = max(gaps)
    if gutter < 0.08:
        return False  # indentation, not a column break

    left = [x for x in xs if x <= split]
    right = [x for x in xs if x > split]
    # Both sides must carry a real share of the page; a right-aligned date on
    # a handful of lines is not a column.
    return min(len(left), len(right)) / len(xs) >= 0.25


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
        # Layout positions are the reliable signal; the text-gap heuristic is
        # only a fallback for when they cannot be read.
        by_layout = _columns_from_layout(reader)
        if by_layout is not None:
            meta["multi_column"] = by_layout
        has_img = _has_images(reader)
        meta["has_images"] = has_img
        # An image-heavy page with almost no extractable text == text locked in
        # an image, which ATS cannot read.
        if has_img is not None:
            meta["has_text_in_images"] = bool(has_img and meta["word_count"] < 120)
    except Exception:
        pass
    return meta
