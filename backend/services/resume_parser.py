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
    return all(any(std in n for std in _STANDARD_FONTS) for n in norm)


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


def _looks_multi_column(text):
    """Two-column layouts leave wide internal gaps on many lines."""
    lines = [ln for ln in (text or "").splitlines() if len(ln.strip()) > 25]
    if len(lines) < 8:
        return False
    gapped = sum(1 for ln in lines if re.search(r"\S {5,}\S", ln))
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
