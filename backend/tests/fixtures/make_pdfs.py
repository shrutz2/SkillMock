"""Generate PDF fixtures that exercise the PDF-only parser paths.

Three structural failures only show up on a real PDF, never on a text
fixture: fonts that do not map to a standard face, text that exists only
inside an image, and a genuine two-column layout. Run this to rebuild them.

    python tests/fixtures/make_pdfs.py
"""
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = A4

BODY = [
    ("Experience", True),
    ("Finlytics | Backend Engineer | Mar 2022 - Present | Hyderabad", False),
    ("- Cut checkout p99 latency from 1.8s to 420ms with a Kafka consumer", False),
    ("- Reduced PostgreSQL read load 62% using a Redis write-through cache", False),
    ("- Wrote 84 tests with pytest, raising branch coverage from 44% to 81%", False),
    ("Projects", True),
    ("- Built a rate limiter capping each API key at 500 requests/min in Go", False),
    ("- Engineered semantic search over 120,000 pages with FAISS, under 50ms", False),
    ("Skills", True),
    ("Python, Go, SQL, Redis, Kafka, Docker, PostgreSQL, AWS, Terraform", False),
    ("Education", True),
    ("B.E. Computer Science | Anna University | 2022 | CGPA 8.9/10", False),
]


def _nonstandard_font():
    """A real font installed on the machine that is NOT on the parser's
    standard list, so the font check actually has something to fail on."""
    win = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for fname, label in (("candara.ttf", "Candara"), ("corbel.ttf", "Corbel"),
                         ("constan.ttf", "Constantia"), ("comic.ttf", "ComicSansMS")):
        path = os.path.join(win, fname)
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(label, path))
            return label
    return None


def make_text_pdf(path, font="Helvetica", heading_font=None):
    c = canvas.Canvas(path, pagesize=A4)
    heading_font = heading_font or font
    y = H - 2.5 * cm
    c.setFont(heading_font, 15)
    c.drawString(2.2 * cm, y, "Rohit Nair")
    y -= 0.55 * cm
    c.setFont(font, 9.5)
    c.drawString(2.2 * cm, y, "rohit.nair@example.com | +91 90000 11223 | github.com/rohitnair")
    y -= 0.9 * cm
    for line, is_heading in BODY:
        c.setFont(heading_font if is_heading else font, 12 if is_heading else 9.5)
        c.drawString(2.2 * cm, y, line)
        y -= 0.75 * cm if is_heading else 0.52 * cm
    c.save()
    return path


def make_two_column_pdf(path):
    """Two independent columns placed side by side, the layout an ATS
    scrambles because the text runs down one column then the other."""
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(2.0 * cm, H - 2.3 * cm, "Meera Krishnan")

    left = ["SKILLS", "Content Strategy", "SEO, SEM, GA4", "Copywriting",
            "Adobe Suite", "", "CONTACT", "meera.k@example.com",
            "+91 99887 66554", "linkedin.com/in/meerak"]
    right = ["PROFESSIONAL EXPERIENCE",
             "Grew organic traffic 140% over eighteen months",
             "Launched a content programme across six verticals",
             "Managed an editorial calendar of 40 pieces monthly",
             "Cut cost per acquisition from 420 to 190 rupees",
             "Ran A/B tests on 25 landing pages with growth",
             "Built a reporting dashboard reviewed weekly",
             "Trained four junior writers on house style",
             "Owned the quarterly content roadmap end to end",
             "Reduced agency spend by 30% bringing work in-house"]

    y = H - 3.4 * cm
    for ln in left:
        c.setFont("Helvetica", 9.5)
        c.drawString(2.0 * cm, y, ln)
        y -= 0.56 * cm
    y = H - 3.4 * cm
    for ln in right:
        c.setFont("Helvetica", 9.5)
        c.drawString(8.6 * cm, y, ln)
        y -= 0.56 * cm
    c.save()
    return path


def make_scanned_pdf(path):
    """Text rendered into an image and embedded, with no text layer -
    what a photographed or scanned resume looks like to a parser."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)
    d.text((90, 80), "Rohit Nair", fill="black")
    d.text((90, 115), "rohit.nair@example.com | +91 90000 11223", fill="black")
    y = 175
    for line, is_heading in BODY:
        d.text((90, y), line, fill="black")
        y += 48 if is_heading else 34
    tmp = os.path.join(HERE, "_scan.png")
    img.save(tmp)

    c = canvas.Canvas(path, pagesize=A4)
    c.drawImage(tmp, 0, 0, width=W, height=H)
    c.save()
    os.remove(tmp)
    return path


if __name__ == "__main__":
    out = []
    out.append(make_text_pdf(os.path.join(HERE, "pdf_standard.pdf")))
    font = _nonstandard_font()
    if font:
        out.append(make_text_pdf(os.path.join(HERE, "pdf_nonstandard_font.pdf"), font=font))
        print(f"  non-standard font used: {font}")
    else:
        print("  no non-standard font found on this machine - skipping that fixture")
    out.append(make_two_column_pdf(os.path.join(HERE, "pdf_two_column.pdf")))
    out.append(make_scanned_pdf(os.path.join(HERE, "pdf_scanned.pdf")))
    for p in out:
        print(f"  wrote {os.path.basename(p)}  ({os.path.getsize(p)/1024:.0f} KB)")
