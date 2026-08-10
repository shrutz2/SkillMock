"""Calibration test for the specificity rubric (Fix 3).

Run from the backend dir:  python calibrate.py
Checks that clearly-strong bullets score >= 0.7 and clearly-weak bullets < 0.3.
"""
import time

from services import analysis_service as A

# Free-tier LLM APIs rate-limit bursts; pace the calls so the run reflects real
# model scoring instead of falling back to the heuristic.
DELAY_S = 2.5

STRONG = [
    "Built a payment service in Python handling 2,000 req/s, cut p99 latency 40% with a Redis write-through cache",
    "Trained a Bidirectional LSTM reaching 83% accuracy on 12k labeled samples",
    "Reduced dashboard load time from 8s to under 1s by streaming 50k events/min through Kafka",
    "Implemented a Redis INCR rate limiter capping each API key at 60 req/min across 6 services",
    "Migrated a monolith to 6 microservices, cutting deploy time from 40min to 7min",
]
WEAK = [
    "Worked on backend development",
    "Collaborated with the team on various projects",
    "Responsible for maintaining the codebase",
    "Helped improve the application",
    "Involved in the software development lifecycle",
]
BORDER = [
    "Built a REST API using Flask",
    "Used Redis for caching",
    "Developed a login system with authentication",
    "Integrated a payment gateway",
    "Created a dashboard for analytics",
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
    print("strong >= 0.7:", sum(x >= 0.7 for x in st), "/5   (min %.2f)" % min(st))
    print("weak   <  0.3:", sum(x < 0.3 for x in wk), "/5   (max %.2f)" % max(wk))
    print("borderline avg: %.2f" % (sum(bd) / len(bd)))
    ok = all(x >= 0.7 for x in st) and all(x < 0.3 for x in wk)
    print("\nPASS" if ok else "\nNEEDS TUNING")
