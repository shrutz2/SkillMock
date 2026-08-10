-- MySQL schema for the AI Mock Interviewer (matches architecture doc).
-- Run: mysql -u root -p < db/schema.sql

CREATE DATABASE IF NOT EXISTS ai_mock_interviewer;
USE ai_mock_interviewer;

CREATE TABLE IF NOT EXISTS sessions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    resume_filename VARCHAR(255),
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS resume_chunks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id BIGINT,
    chunk_text TEXT,
    chunk_index INT,
    faiss_vector_id INT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS questions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id BIGINT,
    question_text TEXT,
    source_chunk_id BIGINT,
    created_at DATETIME,
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (source_chunk_id) REFERENCES resume_chunks(id)
);

CREATE TABLE IF NOT EXISTS answers (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    question_id BIGINT,
    answer_text TEXT,
    specificity_score FLOAT,
    feedback_text TEXT,
    created_at DATETIME,
    FOREIGN KEY (question_id) REFERENCES questions(id)
);
