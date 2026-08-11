"""Generate the sample resume used in the demo.

Fictional candidate - written to exercise every part of the pipeline: clear
section headers, a mix of strong and weak bullets, and a skills line.
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = "docs/sample_resume.pdf"

styles = getSampleStyleSheet()
name = ParagraphStyle("name", parent=styles["Title"], fontSize=20, spaceAfter=2)
contact = ParagraphStyle("contact", parent=styles["Normal"], fontSize=9.5,
                         textColor="#444444", spaceAfter=10)
head = ParagraphStyle("head", parent=styles["Heading2"], fontSize=12,
                      spaceBefore=12, spaceAfter=4, textColor="#1a1a1a")
body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9.5, leading=13.5)

story = [
    Paragraph("Aarav Mehta", name),
    Paragraph("aarav.mehta@example.com | +91 98200 41725 | "
              "linkedin.com/in/aarav-mehta | github.com/aaravmehta", contact),

    Paragraph("Skills", head),
    Paragraph("Languages: Python, Java, JavaScript, SQL<br/>"
              "Frameworks: Flask, React, Spring Boot<br/>"
              "Tools: Docker, Redis, MySQL, Git, AWS EC2", body),

    Paragraph("Experience", head),
    Paragraph("<b>Nexthop Systems</b> | Backend Engineering Intern | "
              "Jan 2025 - Jun 2025 | Pune", body),
    Paragraph("- Built a payment reconciliation service in Python handling 2,000 "
              "requests/second, cutting p99 latency 40% with a Redis write-through cache.", body),
    Paragraph("- Wrote 46 unit tests with JUnit 5 and Mockito, raising branch "
              "coverage from 51% to 88% across the billing module.", body),
    Paragraph("- Worked on backend development and helped the team with various tasks.", body),

    Paragraph("Projects", head),
    Paragraph("- Engineered a semantic document search tool using sentence-transformer "
              "embeddings and a FAISS index, returning top-5 matches across 12,000 "
              "documents in under 40ms.", body),
    Paragraph("- Built a rate limiter capping each API key at 60 requests/min using "
              "Redis INCR with a sliding window, benchmarked at 12,000 requests/min "
              "on a single instance.", body),
    Paragraph("- Created a dashboard for analytics.", body),

    Paragraph("Education", head),
    Paragraph("B.Tech, Computer Science | 2026 | CGPA 8.6/10", body),
]

SimpleDocTemplate(OUT, pagesize=letter, topMargin=0.6 * inch,
                  bottomMargin=0.6 * inch).build(story)
print("wrote", OUT)
