import React, { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { generateQuestions, evaluateAnswer } from "../services/api";
import Typewriter from "../components/Typewriter";
import { useCountUp } from "../hooks/useCountUp";

export default function InterviewPage({ session, setSession }) {
  const navigate = useNavigate();
  const [questions, setQuestions] = useState(session?.questions || null);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const startedRef = useRef(false);

  const loadQuestions = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await generateQuestions(session.session_id, session.role_level);
      setQuestions(data.questions);
      setSession((s) => ({ ...s, questions: data.questions }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [session, setSession]);

  useEffect(() => {
    if (!session) {
      navigate("/");
      return;
    }
    if (!questions && !startedRef.current) {
      startedRef.current = true;
      loadQuestions();
    }
  }, []); // run once on mount

  if (!session) return null;

  if (loading && !questions) {
    return (
      <section className="page page--narrow center-col fade-in">
        <div className="spinner" />
        <p className="muted">Reading your resume and generating questions...</p>
      </section>
    );
  }

  if (error && !questions) {
    return (
      <section className="page page--narrow fade-in">
        <p className="alert">{error}</p>
        <button className="btn" onClick={loadQuestions}>Try again</button>
      </section>
    );
  }

  if (!questions || questions.length === 0) return null;

  const total = questions.length;
  const current = questions[index];
  const isLast = index === total - 1;

  async function submit() {
    if (!answer.trim() || loading) return;
    setLoading(true);
    setError("");
    try {
      const res = await evaluateAnswer(current.id, answer.trim());
      setFeedback(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function next() {
    if (isLast) {
      navigate("/results");
      return;
    }
    setIndex((i) => i + 1);
    setAnswer("");
    setFeedback(null);
    setError("");
  }

  return (
    <section className="page fade-in">
      <div className="stage-wrap stage-wrap--flow">
        <div className="stage-aura" aria-hidden="true" />
        <div className="glass-stage glass-stage--flow">
      <div className="interview-head">
        <p className="eyebrow">Step Two | Interview</p>
        <span className="counter">Question {index + 1} of {total}</span>
      </div>

      <div className="progress-track" aria-hidden="true">
        <div className="progress-fill" style={{ width: `${((index + (feedback ? 1 : 0)) / total) * 100}%` }} />
      </div>

      <article className="question-card">
        <div className="question-label">Interviewer</div>
        <p className="question-text">
          <Typewriter text={current.question_text} />
        </p>
      </article>

      <label className="field-label" htmlFor="answer">Your answer</label>
      <textarea
        id="answer"
        className="answer-input"
        rows={7}
        placeholder="Answer as you would in a real interview - be specific: name the tech, the numbers, the tradeoffs..."
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        disabled={!!feedback}
      />

      {error && <p className="alert">{error}</p>}

      {feedback ? (
        <FeedbackCard feedback={feedback} />
      ) : (
        <button className="btn btn--primary btn--block" onClick={submit} disabled={!answer.trim() || loading}>
          {loading ? "Evaluating..." : "Submit answer"}
        </button>
      )}

      {feedback && (
        <button className="btn btn--primary btn--block" onClick={next}>
          {isLast ? "See results" : "Next question"}
        </button>
      )}
        </div>
      </div>
    </section>
  );
}

function FeedbackCard({ feedback }) {
  const score = feedback.specificity_score ?? 0;
  const pct = Math.round(score * 100);
  const tone = score >= 0.66 ? "good" : score >= 0.4 ? "mid" : "low";
  const label = score >= 0.66 ? "Specific & grounded" : score >= 0.4 ? "Partly specific" : "Too vague";
  const shown = useCountUp(pct, { duration: 900 });
  const [w, setW] = useState(0);

  useEffect(() => {
    const id = setTimeout(() => setW(pct), 50);
    return () => clearTimeout(id);
  }, [pct]);

  return (
    <div className={`feedback feedback--${tone} fade-in`}>
      <div className="feedback-top">
        <span className="feedback-label">{label}</span>
        <span className="feedback-score">{shown}<span>/100</span></span>
      </div>
      <div className="meter"><div className={`meter-fill meter-fill--${tone}`} style={{ width: `${w}%` }} /></div>
      <p className="feedback-text">{feedback.feedback_text}</p>
      {feedback.improvement_text && (
        <p className="feedback-improve">
          <span className="fb-tag">To improve</span>{feedback.improvement_text}
        </p>
      )}
    </div>
  );
}
