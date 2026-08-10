import React, { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { uploadResume } from "../services/api";

export default function UploadPage({ setSession }) {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);
  const navigate = useNavigate();

  function pickFile(f) {
    setError("");
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setError("Please choose a PDF file.");
      return;
    }
    setFile(f);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files?.[0]);
  }

  async function onSubmit() {
    if (!file || loading) return;
    setLoading(true);
    setError("");
    try {
      const data = await uploadResume(file);
      setSession({ ...data, questions: null });
      navigate("/report");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page fade-in">
      <div className="stage-wrap">
        <span className="stack stack--b" aria-hidden="true" />
        <span className="stack stack--a" aria-hidden="true" />
        <div className="stage-aura" aria-hidden="true" />
        <div className="glass-stage">
          <div className="stage-cols">
            <div className="hero">
              <p className="eyebrow">Resume-grounded practice</p>
              <h1 className="page-title">
                Interviews grounded in your&nbsp;<em>own</em> resume.
              </h1>
              <p className="page-subtitle">
                Upload your resume and receive technical questions drawn from
                your actual projects - then see whether each answer sounds
                specific and defensible, or vague and rehearsed.
              </p>
            </div>

            <div className="upload-panel">
              <div
                className={"dropzone" + (dragging ? " dropzone--active" : "") + (file ? " dropzone--filled" : "")}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                onClick={() => inputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept="application/pdf"
                  hidden
                  onChange={(e) => pickFile(e.target.files?.[0])}
                />
                <div className="dropzone-icon" aria-hidden="true">
                  {file ? "yes" : "↑"}
                </div>
                {file ? (
                  <>
                    <p className="dropzone-title">{file.name}</p>
                    <p className="dropzone-hint">{(file.size / 1024).toFixed(0)} KB | click to replace</p>
                  </>
                ) : (
                  <>
                    <p className="dropzone-title">Drop your resume PDF</p>
                    <p className="dropzone-hint">or click to browse</p>
                  </>
                )}
              </div>

              {error && <p className="alert">{error}</p>}

              <button className="btn btn--primary btn--block" onClick={onSubmit} disabled={!file || loading}>
                {loading ? "Analyzing resume..." : "Start interview"}
              </button>

              <p className="trust">✦ Private by design | one resume at a time</p>
            </div>
          </div>

          <ul className="feature-row">
            <li><strong>Parse</strong><span>PDF -> text</span></li>
            <li><strong>Embed</strong><span>local, free</span></li>
            <li><strong>Retrieve</strong><span>FAISS top-k</span></li>
            <li><strong>Question</strong><span>LLM-grounded</span></li>
          </ul>
        </div>
      </div>

      {/* White content section (matter on scroll) */}
      <div className="info-card">
        <p className="eyebrow">How it works</p>
        <h2 className="info-title">From resume to real questions</h2>
        <p className="info-lead">
          No generic "tell me about a time..." prompts. Every question is retrieved
          from the specific claims in your own resume, so you practice defending
          exactly what a real interviewer would probe.
        </p>

        <div className="info-steps">
          <div className="info-step">
            <span className="info-n">01</span>
            <h3>Parse &amp; chunk</h3>
            <p>Your PDF is read and split into coherent sections - Experience, Projects, Skills - so each claim stays intact.</p>
          </div>
          <div className="info-step">
            <span className="info-n">02</span>
            <h3>Embed &amp; retrieve</h3>
            <p>Sections are embedded locally with sentence-transformers and indexed in FAISS to surface your most substantive claims.</p>
          </div>
          <div className="info-step">
            <span className="info-n">03</span>
            <h3>Question &amp; score</h3>
            <p>An LLM writes a pointed question per claim, then rates how specific and defensible your answer sounds - not just whether it's correct.</p>
          </div>
        </div>
      </div>
    </section>
  );
}
