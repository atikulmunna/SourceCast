# SourceCast

**Live demo:** https://source-cast.vercel.app/

SourceCast is an evidence-first research workspace for long-form audio and
video. It turns podcasts, talks, interviews, lectures, and direct audio sources
into timestamped transcripts, searchable evidence, and source-grounded answers.

Instead of producing loose summaries, SourceCast keeps every answer attached to
retrieved transcript passages so researchers can inspect the supporting context
and jump back to the original timestamp.

## What It Does

- Ingests supported media URLs through a background worker.
- Transcribes audio with timestamped segments.
- Chunks transcripts and indexes them in Qdrant.
- Lets users ask source-scoped or workspace-scoped questions.
- Returns answers with evidence cards, confidence labels, and timestamp links.
- Supports private accounts, knowledge spaces, saved chats, comparisons,
  saved insights, and Markdown research briefs.

## MVP Status

The core research loop is live:

```text
source URL -> transcript -> chunks -> embeddings -> retrieval -> cited answer
```

Verified on the deployed backend with:

- Source preview
- Background ingestion
- Hosted transcription
- Transcript browsing
- Vector indexing
- Ask-with-evidence
- Evidence cleanup after test workspace deletion

## Current Limitations

- Render cold starts can make the first backend request slow.
- YouTube ingestion from hosted servers is unreliable without residential
  proxies or a configured yt-dlp cookies file because YouTube often blocks
  cloud IP addresses.
- Podcast RSS feeds, TED pages, and direct audio URLs are the recommended demo
  sources today.

## Architecture

```text
Next.js frontend on Vercel
        |
        | HTTPS + authenticated requests
        v
FastAPI backend on Render
        |
        +-- PostgreSQL / Supabase: app data
        +-- Redis / Upstash: ingestion queue
        +-- ARQ worker: background processing
        +-- Groq Whisper: hosted transcription
        +-- Hash embeddings for MVP hosting
        +-- Qdrant Cloud: vector retrieval
```

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, TanStack Query, Zustand |
| Backend | FastAPI, Python, SQLAlchemy async, Alembic |
| Authentication | JWT access tokens and rotating HttpOnly refresh cookies |
| Database | PostgreSQL |
| Queue | Redis and ARQ |
| Transcription | Groq Whisper in production, faster-whisper available locally |
| Embeddings | Hash embeddings for the hosted MVP, sentence-transformers available locally |
| Vector database | Qdrant |
| Deployment | Vercel frontend, Render backend and worker |

## Product Workflow

1. Create an account.
2. Create a knowledge space.
3. Add a podcast, TED page, or direct audio source.
4. Track ingestion progress while the worker downloads, transcribes, chunks,
   embeds, and indexes the source.
5. Browse the timestamped transcript.
6. Ask questions and inspect cited evidence cards.
7. Compare sources, save insights, and generate research briefs.

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker Desktop
- FFmpeg

### Start Infrastructure

```powershell
docker compose up -d
```

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env -Force
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Start the worker in another terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python worker.py
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open:

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/api/docs

## Environment Notes

Local development can run without hosted LLM generation by keeping:

```env
LLM_PROVIDER=extractive
```

For the hosted MVP, configure the backend web service and worker with:

```env
TRANSCRIPTION_PROVIDER=groq
GROQ_API_KEY=your_groq_key
EMBEDDING_PROVIDER=hash
REDIS_URL=rediss://...
QDRANT_URL=https://your-qdrant-cluster.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_key
```

For production setup details, see [docs/DEPLOYMENT_ENV.md](docs/DEPLOYMENT_ENV.md).

## Verification

Run the full local quality gate:

```powershell
.\check_quality.ps1
```

This runs backend tests, Python compilation, frontend tests, lint, and a
production frontend build.

Run infrastructure-backed integration checks when Docker services are available:

```powershell
.\check_integration.ps1
```

Run a local runtime smoke check when the app is running:

```powershell
.\check_runtime.ps1
```

## Repository Structure

```text
backend/        FastAPI API, worker, services, models, migrations, tests
frontend/       Next.js app, components, client state, frontend tests
docs/           Deployment notes, acceptance checklist, demo runbook
docker-compose.yml
check_quality.ps1
check_integration.ps1
check_runtime.ps1
```

## Privacy Model

SourceCast is designed for private research workflows. User data is scoped by
account, retrieval filters enforce user ownership, and deleting a source removes
its transcript records and vector points.
