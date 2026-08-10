import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getSummary } from "../services/api";
import { useCountUp } from "../hooks/useCountUp";

export default function ResultsPage({ session }) {
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!session) {
      navigate("/");
      return;
    }
    getSummary(session.session_id)
      .then(setSummary)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []); // run once on mount

  if (!session) return null;

  if (loading) {
    return (
      <section className="page page--narrow center-col fade-in">
        <div className="spinner" />
        <p className="muted">Building your summary...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="page page--narrow fade-in">
        <p className="alert">{error}</p>
      </section>
    );
  }

  const avg = summary.average_score;
  const avgPct = avg != null ? Math.round(avg * 100) : null;
  const answered = summary.answered;

  return (
    <section className="page fade-in">
      <div className="stage-wrap stage-wrap--flow">
        <div className="stage-aura" aria-hidden="true" />
        <div className="glass-stage glass-stage--flow">
          <p className="eyebrow">Step Three | Results</p>
          <h1 className="page-title results-title">Session summary</h1>
          <p className="page-subtitle">{summary.resume_filename}</p>

          <ScoreHero avgPct={avgPct} answered={answered} total={summary.total_questions} />

          <div className="results-list">
            {summary.items.map((item, i) => (
              <ResultRow key={item.question_id} item={item} n={i + 1} />
            ))}
          </div>

          <button className="btn btn--primary btn--block" onClick={() => navigate("/")}>
            Start a new session
          </button>
        </div>
      </div>
    </section>
  );
}

function ScoreHero({ avgPct, answered, total }) {
  const shown = useCountUp(avgPct ?? 0, { duration: 1200 });
  const display = avgPct == null ? "-" : shown;

  return (
    <div className="score-hero">
      <div className="score-ring" style={{ "--pct": avgPct == null ? 0 : shown }}>
        <div className="score-ring-inner">
          <span className="score-big">{display}</span>
          <span className="score-unit">avg / 100</span>
        </div>
      </div>
      <div className="score-meta">
        <p><strong>{answered}</strong> of {total} answered</p>
        <p className="muted">
          {avgPct == null
            ? "No answers scored yet."
            : avgPct >= 66
            ? "Strong - your answers were specific and defensible."
            : avgPct >= 40
            ? "Decent - tighten the vague answers with concrete detail."
            : "Work needed - add numbers, tools, and tradeoffs to your answers."}
        </p>
      </div>
    </div>
  );
}

function ResultRow({ item, n }) {
  const score = item.specificity_score;
  const pct = score != null ? Math.round(score * 100) : null;
  const tone = score == null ? "empty" : score >= 0.66 ? "good" : score >= 0.4 ? "mid" : "low";

  return (
    <details className="result-row reveal" style={{ animationDelay: `${n * 70}ms` }} open={n === 1}>
      <summary>
        <span className="result-n">Q{n}</span>
        <span className="result-q">{item.question_text}</span>
        <span className={`pill pill--${tone}`}>{pct != null ? `${pct}` : "-"}</span>
      </summary>
      <div className="result-body">
        {item.answer_text ? (
          <>
            <p className="result-answer">{item.answer_text}</p>
            <p className="result-feedback"><span className="fb-tag">Feedback</span>{item.feedback_text}</p>
          </>
        ) : (
          <p className="muted">Not answered.</p>
        )}
      </div>
    </details>
  );
}
