import React, { useState } from "react";
import { Routes, Route, Link, useLocation } from "react-router-dom";
import UploadPage from "./pages/UploadPage";
import ReportPage from "./pages/ReportPage";
import InterviewPage from "./pages/InterviewPage";
import ResultsPage from "./pages/ResultsPage";

const STEPS = [
  { path: "/", label: "Upload" },
  { path: "/report", label: "Report" },
  { path: "/interview", label: "Interview" },
  { path: "/results", label: "Results" },
];

export default function App() {
  // Session shared across pages (resume upload result + generated questions).
  const [session, setSession] = useState(null);
  const location = useLocation();

  const activeIndex = STEPS.findIndex((s) => s.path === location.pathname);

  return (
    <div className="app">
      <div className="corner-checks" aria-hidden="true" />
      <div className="corner-checks corner-checks--bl" aria-hidden="true" />
      <header className="site-header">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">◆</span>
          <span>SkillMock AI</span>
        </Link>
        <nav className="stepper" aria-label="Progress">
          {STEPS.map((step, i) => (
            <span
              key={step.path}
              className={
                "step" +
                (i === activeIndex ? " step--active" : "") +
                (i < activeIndex ? " step--done" : "")
              }
            >
              <span className="step-dot">{String(i + 1).padStart(2, "0")}</span>
              <span className="step-label">{step.label}</span>
            </span>
          ))}
        </nav>
      </header>

      <main className="content">
        <Routes>
          <Route path="/" element={<UploadPage setSession={setSession} />} />
          <Route
            path="/report"
            element={<ReportPage session={session} setSession={setSession} />}
          />
          <Route
            path="/interview"
            element={<InterviewPage session={session} setSession={setSession} />}
          />
          <Route
            path="/results"
            element={<ResultsPage session={session} />}
          />
        </Routes>
      </main>

      <footer className="site-footer">
        <div className="foot-grid">
          <div className="foot-brand">
            <span className="brand-mark" aria-hidden="true">◆</span>
            <span className="foot-name">SkillMock AI</span>
            <p className="foot-tag">
              Resume-grounded interview practice. Targeted questions from your
              own projects, scored on how specific and defensible they sound.
            </p>
          </div>
          <div className="foot-col">
            <h4>Pipeline</h4>
            <ul>
              <li>Parse &amp; chunk</li>
              <li>Embed (local)</li>
              <li>Retrieve | FAISS</li>
              <li>Question &amp; score</li>
            </ul>
          </div>
          <div className="foot-col">
            <h4>Built with</h4>
            <ul>
              <li>Flask</li>
              <li>sentence-transformers</li>
              <li>FAISS</li>
              <li>React</li>
            </ul>
          </div>
          <div className="foot-col">
            <h4>Private by design</h4>
            <ul>
              <li>One resume at a time</li>
              <li>Embeddings run locally</li>
              <li>No account needed</li>
            </ul>
          </div>
        </div>
        <div className="foot-base">
          <span>© 2026 AI Mock Interviewer</span>
          <span>Resume-grounded RAG</span>
        </div>
      </footer>
    </div>
  );
}
