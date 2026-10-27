"""Measure retrieval quality: does the top-k actually contain the answer?

Run from the backend dir:  python eval_retrieval.py

No LLM calls and no database - embeddings run locally, so this is free and
repeatable. It compares the two chunk granularities on the same resume and
the same queries.

A query is labelled with a distinctive snippet of the text that answers it,
not with a chunk index, so the same labels stay valid when chunking changes.
A retrieved chunk counts as a hit when it contains that snippet. That is
deliberately fair to coarse chunking - a whole section trivially contains
more snippets - which is exactly why precision is reported alongside recall:
returning three of seven sections hands the model 43% of the document, and
recall bought that way is not worth much.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services import chunking_service, embedding_service
from vector_store import faiss_index

FIXTURE = os.path.join("tests", "fixtures", "resume_long.txt")

# (question an interviewer might ask, snippet that answers it)
GOLDEN = [
    ("How did you improve checkout performance?", "1.8s to 420ms"),
    ("Tell me about a time you reduced database load.", "read load 62%"),
    ("What caching have you worked with?", "Redis write-through cache"),
    ("Describe a reliability problem you fixed.", "duplicate refunds"),
    ("Have you used idempotency keys?", "idempotency keys"),
    ("What do you know about message queues?", "Kafka consumer"),
    ("Tell me about scheduled or background jobs.", "Celery beat"),
    ("What monitoring have you set up?", "Prometheus and Grafana"),
    ("How do you track latency in production?", "latency percentiles"),
    ("Describe your experience with analytics databases.", "ClickHouse schema"),
    ("Have you done data partitioning?", "monthly partitions"),
    ("Tell me about a pipeline you automated.", "60 CSV feeds"),
    ("What orchestration tools have you used?", "Airflow"),
    ("How do you handle bad input data?", "Pydantic"),
    ("What is your approach to testing?", "84 unit and integration tests"),
    ("What test coverage have you achieved?", "44% to 81%"),
    ("Tell me about a search or ranking system.", "semantic search service"),
    ("Have you worked with vector search?", "FAISS IVF index"),
    ("Describe a rate limiter you built.", "500 requests/minute"),
    ("What infrastructure as code have you used?", "Terraform module"),
    ("How do you prevent SQL injection?", "unparameterised SQL"),
    ("What languages do you write day to day?", "Go, SQL, TypeScript"),
    ("What cloud certifications do you hold?", "Solutions Architect"),
    ("Where did you study?", "Anna University"),
]


def evaluate(chunks, queries, k):
    """Return recall@k and MRR for one set of chunks."""
    embeddings = embedding_service.embed_chunks(chunks)
    sid = f"eval-{len(chunks)}"
    faiss_index.build_index(sid, embeddings)

    hits, reciprocal = 0, 0.0
    misses = []
    for question, snippet in queries:
        ids = faiss_index.search(sid, embedding_service.embed_query(question), k=k)
        rank = next((i + 1 for i, vid in enumerate(ids)
                     if snippet.lower() in chunks[vid].lower()), None)
        if rank:
            hits += 1
            reciprocal += 1 / rank
        else:
            misses.append((question, snippet))
    n = len(queries)
    return hits / n, reciprocal / n, misses


def main():
    text = open(FIXTURE, encoding="utf-8").read()
    print(f"resume: {FIXTURE}")
    print(f"queries: {len(GOLDEN)}   embedding backend: {embedding_service.backend_name()}\n")

    print(f"{'granularity':<14}{'chunks':>8}{'k':>4}{'recall@k':>11}{'MRR':>8}"
          f"{'% of doc returned':>20}")
    print("-" * 65)

    results = {}
    for granularity in ("section", "bullet"):
        chunks = chunking_service.chunk_resume(text, granularity=granularity)
        for k in (3, 5):
            recall, mrr, misses = evaluate(chunks, GOLDEN, k)
            share = min(k, len(chunks)) / len(chunks)
            print(f"{granularity:<14}{len(chunks):>8}{k:>4}{recall:>10.0%}{mrr:>8.2f}"
                  f"{share:>19.0%}")
            results[(granularity, k)] = (recall, mrr, misses, len(chunks))

    print()
    for granularity in ("section", "bullet"):
        _, _, misses, _ = results[(granularity, 3)]
        if misses:
            print(f"{granularity} misses at k=3:")
            for q, snip in misses:
                print(f"   {q}   (wanted: {snip!r})")
            print()


if __name__ == "__main__":
    main()
