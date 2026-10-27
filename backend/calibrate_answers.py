"""Calibration test for the ANSWER scorer (services/evaluation_service).

Run from the backend dir:  python calibrate_answers.py

The resume-bullet scorer had a calibration for months; this one did not, so
nothing measured whether an interview answer was scored sensibly. Checks that
detailed answers score >= 0.7 and filler scores < 0.3, and reports how many
scores actually reached the model rather than the heuristic fallback.
"""
import time

from llm.client import client
from services import evaluation_service as E

DELAY_S = 2.5

QUESTION = "Tell me how you improved performance in that project."
CONTEXT = ("Experience: Cut checkout p99 latency from 1.8s to 420ms by replacing "
           "synchronous fraud scoring with a Kafka consumer and an idempotent "
           "settlement worker.")

# Hand-labelled by one annotator. STRONG answers carry a number, a named
# technology, a reason for the choice, and concrete detail.
STRONG = [
    "Checkout p99 was 1.8 seconds because fraud scoring ran synchronously inside the "
    "request. I moved it onto a Kafka consumer so the response no longer waits for it, "
    "and made the settlement worker idempotent since retries could double-charge. "
    "That brought p99 to 420ms.",

    "I profiled the endpoint and found 70% of the time was a single N+1 query. I added "
    "a join and a Redis cache on the merchant config because that row changes maybe "
    "once a week, which cut database reads by 62%.",

    "We were re-embedding the same documents on every upload. I hashed the content and "
    "cached by that hash rather than by session id, so an identical file reuses the "
    "result and an edited one invalidates itself. It removed about a second per request.",

    "The nightly Spark job took 6 hours because it re-read the full 2.4 TB each run. I "
    "switched to incremental partitions by date so it only touches new data, which got "
    "it to 48 minutes.",
]

WEAK = [
    "I improved the performance of the application.",
    "We used caching and it made things faster.",
    "I worked on optimising the code with my team.",
    "Performance was a challenge but we handled it well.",
]

BORDER = [
    "I added a Redis cache in front of the database to reduce load.",
    "I moved the slow part to a background job so the request returned faster.",
    "We switched to a different query and it was about twice as fast.",
    "I used indexing on the table to speed up the lookups.",
]


def run(label, answers):
    print(f"\n=== {label} ===")
    scores = []
    for a in answers:
        score, reason, improve = E.evaluate_answer(QUESTION, a, CONTEXT)
        scores.append(score)
        print("  %.2f  %s" % (score, a[:68]))
        time.sleep(DELAY_S)
    return scores


if __name__ == "__main__":
    st = run("STRONG (expect >= 0.7)", STRONG)
    wk = run("WEAK (expect < 0.3)", WEAK)
    bd = run("BORDERLINE (expect 0.3-0.7)", BORDER)

    total = len(st) + len(wk) + len(bd)
    print("\n--- ANSWER CALIBRATION RESULT ---")
    print("labelled answers: %d  (%d strong, %d weak, %d borderline)"
          % (total, len(st), len(wk), len(bd)))
    print("scored by the model: %d/%d%s"
          % (total - client.fallbacks, total,
             "" if not client.fallbacks
             else "   <-- %d fell back, averages are NOT pure model output"
                  % client.fallbacks))
    print("strong >= 0.7: %d/%d   (min %.2f, avg %.2f)"
          % (sum(x >= 0.7 for x in st), len(st), min(st), sum(st) / len(st)))
    print("weak   <  0.3: %d/%d   (max %.2f, avg %.2f)"
          % (sum(x < 0.3 for x in wk), len(wk), max(wk), sum(wk) / len(wk)))
    print("borderline avg: %.2f" % (sum(bd) / len(bd)))

    ok = all(x >= 0.7 for x in st) and all(x < 0.3 for x in wk)
    print("\nPASS" if ok else "\nNEEDS TUNING")
