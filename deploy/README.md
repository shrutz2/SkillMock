# Deployment

The app runs as a single service: Flask serves the built React app, so there is
one URL and no CORS setup.

Embeddings run on onnxruntime (about 50 MB) instead of torch (about 1.5 GB),
which is what makes this fit on a free instance.

## Render (recommended)

1. Push this repo to GitHub.
2. In Render: **New -> Blueprint**, point it at the repo. It reads
   [`render.yaml`](../render.yaml).
3. Set `GROQ_API_KEY` when prompted (marked `sync: false`, so it is never
   committed). Skip it to run with the offline mock provider.
4. Deploy. First build takes a few minutes, mostly the npm build.

Live at `https://<service-name>.onrender.com`.

Notes:

- The free plan sleeps after 15 minutes of inactivity, so the first request
  after a pause takes a few seconds to wake.
- `SQLITE_PATH` points at `/tmp`, which resets on restart. That is fine for a
  demo; for persistence set `DB_BACKEND=mysql` and the `MYSQL_*` variables.

## Docker (anywhere)

```bash
docker build -t skillmock .
docker run -p 7860:7860 -e GROQ_API_KEY=your_key skillmock
```

Then open http://localhost:7860.

## Hugging Face Spaces

Spaces needs a `README.md` with a YAML config header, which we do not want in
the GitHub README. [`push_to_space.sh`](push_to_space.sh) builds a temporary
commit with [`space_README.md`](space_README.md) swapped in and pushes that:

```bash
./deploy/push_to_space.sh <hf-username> <space-name>
```

Set `GROQ_API_KEY` in the Space's settings under Variables and secrets.

## Environment variables

| Variable | Default | Notes |
|----------|---------|-------|
| `GROQ_API_KEY` | empty | Falls back to the mock provider when unset |
| `LLM_PROVIDER` | `mock` | `groq`, `gemini`, or `mock` |
| `EMBEDDING_BACKEND` | `onnx` | `torch` needs `requirements-torch.txt` |
| `DB_BACKEND` | `sqlite` | `mysql` for persistence |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | Not needed when Flask serves the frontend |
| `QUESTIONS_PER_SESSION` | `10` | |
