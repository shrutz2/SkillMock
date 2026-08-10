import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getReport } from "../services/api";

const LEVELS = ["Fresher", "Junior", "SDE-1"];

export default function ReportPage({ session, setSession }) {
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [jd, setJd] = useState("");
  const [jdLoading, setJdLoading] = useState(false);
  const [level, setLevel] = useState("Junior");

  const load = useCallback(async (jobDescription) => {
    const data = await getReport(session.session_id, jobDescription);
    setReport(data);
    if (data.suggested_level && LEVELS.includes(data.suggested_level)) {
      setLevel(data.suggested_level);
    }
    return data;
  }, [session]);

  useEffect(() => {
    if (!session) {
      navigate("/");
      return;
    }
    load("").catch((e) => setError(e.message)).finally(() => setLoading(false));
    // eslint-disable-next-line
  }, []);

  async function checkFit() {
    if (!jd.trim() || jdLoading) return;
    setJdLoading(true);
    setError("");
    try {
      await load(jd.trim());
    } catch (e) {
      setError(e.message);
    } finally {
      setJdLoading(false);
    }
  }

  function startInterview() {
    setSession((s) => ({ ...s, role_level: level, questions: null }));
    navigate("/interview");
  }

  if (!session) return null;
  if (loading) {
    return (
      <section className="page page--narrow center-col fade-in">
        <div className="spinner" />
        <p className="muted">Reading your resume...</p>
      </section>
    );
  }

  const cf = report?.company_fit || {};
  const rf = report?.role_fit;

  return (
    <section className="page fade-in">
      <div className="stage-wrap stage-wrap--flow">
        <div className="stage-aura" aria-hidden="true" />
        <div className="glass-stage glass-stage--flow">
          <p className="eyebrow">Step Two | Resume report</p>
          <h1 className="page-title results-title">Before you start</h1>
          <p className="page-subtitle">
            A quick read of your resume - what's strong, what's vague, and where
            it fits - so you know what to sharpen before the interview.
          </p>

          {error && <p className="alert">{error}</p>}

          {/* Parsing Safety - deterministic, always shown, JD-independent */}
          {report.ats?.parsing && <ParsingSafety p={report.ats.parsing} skills={report.ats.skills} />}

          {/* Weak-claim detector (#4) */}
          <div className="rep-block">
            <h2 className="rep-h">Claim strength</h2>
            <ul className="claims">
              {(report.weak_claims || []).map((c, i) => (
                <li key={i} className={`claim claim--${c.verdict}`}>
                  <span className="claim-tag">
                    {c.verdict === "specific" ? "Specific" : "Weak"}
                    {typeof c.score === "number" && (
                      <span className="claim-score">{Math.round(c.score * 100)}</span>
                    )}
                  </span>
                  <div className="claim-body">
                    <p className="claim-text">{c.text}</p>
                    {c.signals && c.signals.length > 0 && (
                      <div className="claim-signals">
                        {c.signals.map((s, k) => (
                          <span key={k} className="sig">{s}</span>
                        ))}
                      </div>
                    )}
                    {c.verdict === "weak" && c.note && <p className="claim-note">{c.note}</p>}
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {/* Company-group fit (#5) */}
          <div className="rep-block">
            <h2 className="rep-h">Where your resume fits</h2>
            <p className="rep-summary">{cf.summary}</p>
            <div className="chips">
              {(cf.groups || []).map((g, i) => (
                <span key={i} className="chip chip--group" title={g.why}>{g.name}</span>
              ))}
            </div>
            <div className="chips">
              {(cf.signals || []).map((s, i) => (
                <span key={i} className="chip">{s}</span>
              ))}
            </div>
          </div>

          {/* Resume-to-Role fit (#2) */}
          <div className="rep-block">
            <h2 className="rep-h">Match against a job description</h2>
            <textarea
              className="answer-input"
              rows={4}
              placeholder="Paste a job description to see your ATS keyword coverage, fit score, and gaps..."
              value={jd}
              onChange={(e) => setJd(e.target.value)}
            />
            <button className="btn btn--block" onClick={checkFit} disabled={!jd.trim() || jdLoading}>
              {jdLoading ? "Scoring fit..." : "Check fit"}
            </button>

            {report.ats?.jd_match ? (
              <div className="kw fade-in">
                <div className="kw-head">
                  <span>{report.ats.jd_match.label}</span>
                  <strong>{report.ats.jd_match.score}%</strong>
                </div>
                <div className="meter">
                  <div className="meter-fill meter-fill--good" style={{ width: `${report.ats.jd_match.score}%` }} />
                </div>
                <div className="fit-cols">
                  <div>
                    <h3 className="fit-h fit-h--good">Matched ({report.ats.jd_match.matched_keywords.length})</h3>
                    <div className="chips">
                      {report.ats.jd_match.matched_keywords.map((s, i) => <span key={i} className="chip chip--good">{s}</span>)}
                    </div>
                  </div>
                  <div>
                    <h3 className="fit-h fit-h--miss">Missing ({report.ats.jd_match.missing_keywords.length})</h3>
                    <div className="chips">
                      {report.ats.jd_match.missing_keywords.map((s, i) => <span key={i} className="chip chip--miss">{s}</span>)}
                    </div>
                  </div>
                </div>
                <p className="disclaimer">{report.ats.jd_match.disclaimer}</p>
              </div>
            ) : (
              <p className="empty-note">
                Paste a job description above to see your keyword match score -
                match is job-specific, so there's no score without one.
              </p>
            )}

            {rf && (
              <div className="fit fade-in">
                <div className="fit-top">
                  <div className="fit-ring" style={{ "--pct": rf.fit_score }}>
                    <div className="fit-ring-inner">
                      <span className="score-big">{rf.fit_score}</span>
                      <span className="score-unit">fit / 100</span>
                    </div>
                  </div>
                  <div className="fit-meta">
                    <p><strong>Best fit:</strong> {rf.level}</p>
                    <p className="rep-summary">{rf.reasoning}</p>
                  </div>
                </div>
                <div className="fit-cols">
                  <div>
                    <h3 className="fit-h fit-h--good">Matched</h3>
                    <div className="chips">
                      {(rf.matched_skills || []).map((s, i) => <span key={i} className="chip chip--good">{s}</span>)}
                    </div>
                  </div>
                  <div>
                    <h3 className="fit-h fit-h--miss">Missing</h3>
                    <div className="chips">
                      {(rf.missing_skills || []).map((s, i) => <span key={i} className="chip chip--miss">{s}</span>)}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Role calibration (#1) */}
          <div className="rep-block">
            <h2 className="rep-h">Interview level</h2>
            <p className="rep-summary">
              Questions are calibrated to this level.
              {report.suggested_level && ` Suggested for your resume: ${report.suggested_level}.`}
            </p>
            <div className="level-picker">
              {LEVELS.map((l) => (
                <button
                  key={l}
                  className={"level-opt" + (level === l ? " level-opt--on" : "")}
                  onClick={() => setLevel(l)}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>

          <button className="btn btn--primary btn--block" onClick={startInterview}>
            Start {level} interview ->
          </button>
        </div>
      </div>
    </section>
  );
}

function ParsingSafety({ p, skills }) {
  const score = p.score ?? 0;
  const tone = score >= 80 ? "good" : score >= 50 ? "mid" : "low";
  return (
    <div className="rep-block ats">
      <h2 className="rep-h">{p.label}</h2>
      <div className="ats-top">
        <div className={`fit-ring fit-ring--${tone}`} style={{ "--pct": score }}>
          <div className="fit-ring-inner">
            <span className="score-big">{score}</span>
            <span className="score-unit">parsing / 100</span>
          </div>
        </div>
        <div className="ats-meta">
          <p><strong>{p.checks_passed}/{p.checks_total}</strong> checks passed</p>
          <p className="rep-summary">
            {p.contact?.name ? `Parsed as ${p.contact.name}. ` : ""}
            Sections detected: {(p.sections_found || []).join(", ") || "none"}.
          </p>
          {p.critical_failed?.length > 0 && (
            <p className="crit-note">Critical: {p.critical_failed.join(" | ")}</p>
          )}
        </div>
      </div>

      <div className="ats-checks">
        {(p.checks || []).map((c) => (
          <div key={c.name} className={`ats-check ats-check--${c.passed ? "pass" : (c.weight === "critical" ? "fail" : "warn")}`}>
            <span className="ats-ic">{c.passed ? "yes" : (c.weight === "critical" ? "✕" : "!")}</span>
            <span className="ats-label">
              {c.name}
              {c.weight === "critical" && <em className="crit-tag">critical</em>}
            </span>
            <span className="ats-detail">{c.detail}</span>
          </div>
        ))}
      </div>

      <p className="disclaimer">{p.disclaimer}</p>

      {skills?.hard?.length > 0 && (
        <div className="ats-skills">
          <h3 className="fit-h">Skills detected</h3>
          <div className="chips">
            {skills.hard.map((s, i) => <span key={i} className="chip">{s}</span>)}
            {(skills.soft || []).map((s, i) => <span key={`s${i}`} className="chip chip--soft">{s}</span>)}
          </div>
        </div>
      )}
    </div>
  );
}
