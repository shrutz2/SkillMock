"""POST /api/resume/upload - parse, chunk, embed, index, persist."""
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from models import resume_chunk as chunk_model
from models import session as session_model
from config import Config
from services import chunking_service, embedding_service, resume_parser, security_service
from services.rate_limit import rate_limit
from vector_store import faiss_index

resume_bp = Blueprint("resume", __name__)


@resume_bp.route("/api/resume/upload", methods=["POST"])
@rate_limit(limit=5, window_seconds=300, scope="upload")
def upload_resume():
    if "resume" not in request.files:
        return jsonify({"error": "No file part named 'resume'"}), 400

    file = request.files["resume"]
    if not file or file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    # Verify the bytes, not just the name.
    ok, err, warnings = security_service.validate_pdf(file, Config.MAX_UPLOAD_MB * 1024 * 1024)
    if not ok:
        return jsonify({"error": err}), 400
    if warnings:
        print(f"[upload] {secure_filename(file.filename)}: {'; '.join(warnings)}")

    # 1. Parse
    text = resume_parser.extract_text(file)
    if not text.strip():
        return jsonify({"error": "Could not extract text from this PDF"}), 422

    # 2. Chunk
    chunks = chunking_service.chunk_resume(text)
    if not chunks:
        return jsonify({"error": "Resume produced no usable content"}), 422

    # 3. Embed
    embeddings = embedding_service.embed_chunks(chunks)

    # 4. Persist session (with PDF-level ATS diagnostics) + build FAISS index
    parse_meta = resume_parser.analyze_pdf(file, text)
    token = session_model.new_token()
    session_id = session_model.create(
        secure_filename(file.filename), parse_meta=parse_meta, session_token=token
    )
    faiss_index.build_index(session_id, embeddings)

    # 5. Persist chunks (faiss_vector_id == chunk index in the flat index)
    for i, chunk_text in enumerate(chunks):
        chunk_model.create(session_id, chunk_text, i, i)

    return jsonify(
        {
            "session_id": session_id,
            "session_token": token,
            "filename": secure_filename(file.filename),
            "num_chunks": len(chunks),
        }
    ), 201
