"""Calibration test for the ANSWER scorer (services/evaluation_service).

Run from the backend dir:  python calibrate_answers.py

The resume-bullet scorer had a calibration for months; this one did not, so
nothing measured whether an interview answer was scored sensibly. Checks that
detailed answers score >= 0.7 and filler scores < 0.3, and reports how many
scores actually reached the model rather than the heuristic fallback.

Each case is its own (question, resume context, answer) triple. A single
fixed question would have forced every answer onto one topic, which only
tests the scorer on one kind of writing - the same mistake the bullet
calibration started with.
"""
import os
import time

# Deterministic scoring, so a reported average is reproducible by anyone
# re-running this. Must be set before Config is imported.
os.environ.setdefault("LLM_TEMPERATURE", "0")

from llm.client import client
from services import evaluation_service as E

DELAY_S = float(os.getenv("CALIBRATE_DELAY_S", "6"))

# Hand-labelled by one annotator, spread across backend, data, ML, security,
# frontend and non-engineering work.
STRONG = [
    ("Tell me how you improved performance in that project.",
     "Experience: Cut checkout p99 latency from 1.8s to 420ms with a Kafka consumer.",
     "Checkout p99 was 1.8 seconds because fraud scoring ran synchronously inside the "
     "request. I moved it onto a Kafka consumer so the response no longer waits for it, "
     "and made the settlement worker idempotent since retries could double-charge. That "
     "brought p99 to 420ms."),

    ("How did you reduce database load?",
     "Experience: Reduced PostgreSQL read load 62% with a Redis write-through cache.",
     "I profiled the endpoint and found 70% of the time was a single N+1 query. I added a "
     "join and a Redis cache on the merchant config because that row changes maybe once a "
     "week, which cut database reads by 62%."),

    ("Describe a caching decision you made.",
     "Projects: Cached resume reports keyed on content hash.",
     "We were re-embedding the same documents on every upload. I hashed the content and "
     "cached by that hash rather than by session id, so an identical file reuses the result "
     "and an edited one invalidates itself. It removed about a second per request."),

    ("Tell me about a slow pipeline you fixed.",
     "Experience: Rebuilt a nightly Spark pipeline, 6 hours to 48 minutes.",
     "The nightly Spark job took 6 hours because it re-read the full 2.4 TB each run. I "
     "switched to incremental partitions by date so it only touches new data, which got it "
     "to 48 minutes."),

    ("How did you handle bad input data?",
     "Experience: Added Pydantic schema validation at the ingestion boundary.",
     "Bad rows were corrupting reports silently because nothing validated them. I added "
     "Pydantic models at the ingestion boundary rather than checking downstream, since by "
     "then the bad data has already spread. It rejected 1,200 malformed rows in the first "
     "week."),

    ("Walk me through a concurrency bug you fixed.",
     "Projects: Fixed duplicate question generation under concurrent requests.",
     "Two identical requests arrived milliseconds apart and both passed the same check "
     "before either had written, so we generated twice. I added a lock around that section, "
     "but it still happened because the database connection kept a stale snapshot under "
     "REPEATABLE READ. Enabling autocommit gave each statement a fresh view, and after that "
     "concurrent requests returned one set of 5."),

    ("How did you secure the API?",
     "Projects: Per-session token authorization on a Flask REST API.",
     "Session ids were sequential integers, so incrementing one in the URL returned someone "
     "else's data. I issued a 256-bit random token at upload and required it on every "
     "request, comparing with constant-time equality because a normal comparison leaks how "
     "much of the token matched. Enumerating ids then returned 403 every time."),

    ("Tell me about a model you trained.",
     "Projects: Bidirectional LSTM for text classification.",
     "I trained a bidirectional LSTM on 12,000 labelled samples and got 83% accuracy. I "
     "chose bidirectional over a plain LSTM because the label often depends on words after "
     "the key phrase, and I used early stopping on validation loss since it started "
     "overfitting around epoch 12."),

    ("How did you cut cloud costs?",
     "Experience: Reduced Snowflake spend 41% with incremental dbt models.",
     "Every dbt model was rebuilding from scratch nightly. I moved 38 of them to incremental "
     "materialisation so they only process new rows, because the historical partitions never "
     "change. Snowflake credit spend dropped 41%."),

    ("Describe a frontend performance problem.",
     "Projects: React dashboard rendering large tables.",
     "The table re-rendered all 5,000 rows on every keystroke because the filter lived in "
     "parent state. I memoised the row component and moved the filter into a debounced local "
     "state, since the parent did not need it per character. Input lag went from visible to "
     "unnoticeable."),

    ("Tell me about a process you improved.",
     "Experience: Redesigned the slotting policy across 3 regional hubs.",
     "Pickers were walking the full warehouse because fast-moving items were stored by "
     "supplier rather than by frequency. I reordered slotting by pick frequency across 3 "
     "hubs, which cut average pick time 27%. We trialled it in one hub first so a bad layout "
     "would not affect all three."),

    ("How did you grow that channel?",
     "Experience: Grew organic traffic 140% in 18 months.",
     "Traffic was flat because we published around one piece a month with no topic strategy. "
     "I built a calendar around 6 verticals chosen by search volume versus our existing "
     "authority, rather than what we found interesting, and shipped 40 pieces a month. "
     "Organic traffic grew 140% over 18 months."),
]

WEAK = [
    ("Tell me how you improved performance.",
     "Experience: Backend engineer.",
     "I improved the performance of the application."),
    ("How did you use caching?",
     "Experience: Backend engineer.",
     "We used caching and it made things faster."),
    ("Describe your optimisation work.",
     "Experience: Backend engineer.",
     "I worked on optimising the code with my team."),
    ("Tell me about a challenge.",
     "Experience: Backend engineer.",
     "Performance was a challenge but we handled it well."),
    ("How did you test it?",
     "Experience: Backend engineer.",
     "We did proper testing before releasing it."),
    ("What was your role?",
     "Experience: Backend engineer.",
     "I was responsible for the backend part of the project."),
    ("How did you handle the deadline?",
     "Experience: Backend engineer.",
     "We managed our time well and delivered on schedule."),
    ("Tell me about working in a team.",
     "Experience: Backend engineer.",
     "I collaborated with everyone and we had good communication."),
    ("How did you debug it?",
     "Experience: Backend engineer.",
     "I debugged the issue and fixed it successfully."),
    ("What did you learn?",
     "Experience: Backend engineer.",
     "I learned a lot of new things and gained good experience."),
    ("How did you secure it?",
     "Experience: Backend engineer.",
     "We followed security best practices throughout."),
    ("Describe the architecture.",
     "Experience: Backend engineer.",
     "It was a standard architecture using modern technologies."),
]

BORDER = [
    ("How did you improve performance?",
     "Experience: Backend engineer.",
     "I added a Redis cache in front of the database to reduce load."),
    ("How did you make the request faster?",
     "Experience: Backend engineer.",
     "I moved the slow part to a background job so the request returned faster."),
    ("Tell me about a query you optimised.",
     "Experience: Backend engineer.",
     "We switched to a different query and it was about twice as fast."),
    ("How did you speed up lookups?",
     "Experience: Backend engineer.",
     "I used indexing on the table to speed up the lookups."),
    ("How did you deploy it?",
     "Experience: Backend engineer.",
     "I containerised the app with Docker and deployed it on AWS."),
    ("How did you test the payment flow?",
     "Experience: Backend engineer.",
     "I wrote unit tests for the payment module using pytest."),
    ("How did you handle authentication?",
     "Experience: Backend engineer.",
     "I used JWT tokens for authentication on the API."),
    ("Tell me about the data model.",
     "Experience: Data engineer.",
     "I designed the schema in PostgreSQL with foreign keys between the tables."),
    ("How did you monitor it?",
     "Experience: Backend engineer.",
     "We set up Grafana dashboards to watch the service."),
    ("How did you analyse churn?",
     "Experience: Analyst.",
     "I wrote SQL queries to look at which customers stopped using the product."),
    ("Tell me about leading the interns.",
     "Experience: Led a team of interns.",
     "I led a team of interns and we built an internal tool together."),
    ("How did you pick the vendors?",
     "Experience: Procurement.",
     "I compared a few vendors on price and picked the best one."),
]


def run(label, cases):
    print(f"\n=== {label} ===")
    scores = []
    for question, context, answer in cases:
        score, _reason, _improve = E.evaluate_answer(question, answer, context)
        scores.append(score)
        print("  %.2f  %s" % (score, answer[:68]))
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
