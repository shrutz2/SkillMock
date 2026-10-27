"""Calibration test for the specificity rubric (Fix 3).

Run from the backend dir:  python calibrate.py
Checks that clearly-strong bullets score >= 0.7 and clearly-weak bullets < 0.3.
"""
import time

from services import analysis_service as A

# Free-tier LLM APIs rate-limit bursts; pace the calls so the run reflects real
# model scoring instead of falling back to the heuristic.
DELAY_S = 2.5

# Hand-labelled by one annotator. Deliberately spread across engineering,
# data, and non-technical resumes - an earlier version was all backend SWE
# bullets, which only proved the scorer worked on one kind of writing.
STRONG = [
    "Built a payment service in Python handling 2,000 req/s, cut p99 latency 40% with a Redis write-through cache",
    "Trained a Bidirectional LSTM reaching 83% accuracy on 12k labeled samples",
    "Reduced dashboard load time from 8s to under 1s by streaming 50k events/min through Kafka",
    "Implemented a Redis INCR rate limiter capping each API key at 60 req/min across 6 services",
    "Migrated a monolith to 6 microservices, cutting deploy time from 40min to 7min",
    "Rebuilt a nightly Spark pipeline, cutting runtime from 6 hours to 48 minutes over 2.4 TB daily",
    "Modelled 38 dbt tables with incremental materialisation, reducing Snowflake spend 41%",
    "Reduced warehouse pick time 27% by redesigning the slotting policy across 3 regional hubs",
    "Negotiated contracts with 14 vendors, lowering annual procurement spend by 1.8 crore",
    "Grew organic traffic 140% in 18 months by launching a content programme across 6 verticals",
    "Cut cost per acquisition from 420 to 190 rupees by running A/B tests on 25 landing pages",
    "Wrote 84 pytest tests, raising branch coverage from 44% to 81% on the ingestion package",
]
WEAK = [
    "Worked on backend development",
    "Collaborated with the team on various projects",
    "Responsible for maintaining the codebase",
    "Helped improve the application",
    "Involved in the software development lifecycle",
    "Participated in daily standups and sprint planning",
    "Assisted senior developers with assigned tasks",
    "Gained hands-on experience with modern technologies",
    "Contributed to improving overall team productivity",
    "Handled multiple responsibilities in a fast-paced environment",
    "Supported the business in achieving its objectives",
    "Engaged with stakeholders to understand requirements",
]
BORDER = [
    "Built a REST API using Flask",
    "Used Redis for caching",
    "Developed a login system with authentication",
    "Integrated a payment gateway",
    "Created a dashboard for analytics",
    "Deployed the application on AWS using Docker",
    "Automated report generation with Python scripts",
    "Designed the database schema in PostgreSQL",
    "Implemented unit tests for the payment module",
    "Managed the social media calendar for the brand",
    "Led a team of interns on an internal tool",
    "Analysed customer churn using SQL queries",
]


def run(label, bullets):
    print(f"\n=== {label} ===")
    scores = []
    for b in bullets:
        s, sig = A.score_bullet(b)
        scores.append(s)
        print("  %.2f  %-24s  %s" % (s, str(sig)[:24], b[:52]))
        time.sleep(DELAY_S)
    return scores


if __name__ == "__main__":
    st = run("STRONG (expect >= 0.7)", STRONG)
    wk = run("WEAK (expect < 0.3)", WEAK)
    bd = run("BORDERLINE (expect 0.3-0.7)", BORDER)
    print("\n--- CALIBRATION RESULT ---")
    print("labelled examples: %d  (%d strong, %d weak, %d borderline)"
          % (len(st) + len(wk) + len(bd), len(st), len(wk), len(bd)))
    print("strong >= 0.7: %d/%d   (min %.2f, avg %.2f)"
          % (sum(x >= 0.7 for x in st), len(st), min(st), sum(st) / len(st)))
    print("weak   <  0.3: %d/%d   (max %.2f, avg %.2f)"
          % (sum(x < 0.3 for x in wk), len(wk), max(wk), sum(wk) / len(wk)))
    print("borderline avg: %.2f" % (sum(bd) / len(bd)))
    ok = all(x >= 0.7 for x in st) and all(x < 0.3 for x in wk)
    print("\nPASS" if ok else "\nNEEDS TUNING")
