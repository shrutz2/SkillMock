# SkillMock AI

Resume-grounded mock interviewer. Upload a resume, get technical questions built
from the actual claims in it, answer them, and see whether each answer sounds
specific and defensible or vague.

Most mock-interview tools ask generic questions ("tell me about a time you solved
a problem"). This one reads your resume first, so the questions are about the
projects you actually built.

## Status

Work in progress. Backend and frontend are functional locally.

## Stack

- **Frontend:** React (Create React App), plain CSS
- **Backend:** Flask
- **Embeddings:** sentence-transformers (`all-MiniLM-L6-v2`), runs locally
- **Vector search:** FAISS
- **LLM:** Groq / Gemini free tier (swappable)
- **Database:** MySQL

## How it works

1. Resume PDF is parsed and split into sections (Experience, Projects, Skills)
2. Each section is embedded and indexed in FAISS
3. Relevant sections are retrieved and used as context for question generation
4. Answers are scored for specificity against the section the question came from

## Planned

- ATS-style resume report (parsing checks, keyword match against a job description)
- Role-level calibration (Fresher / Junior / SDE-1)
- Answer improvement suggestions

## Setup

Backend:

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Frontend:

```bash
cd frontend
npm install
npm start
```

Copy `.env.example` to `.env` and fill in your database credentials and API key.
The `.env` file is gitignored and should never be committed.
