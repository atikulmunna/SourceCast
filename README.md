# SourceCast

SourceCast is an evidence-first research workspace for podcasts, YouTube videos,
lectures, interviews, and other long-form audio or video sources. It turns media
into a private, searchable knowledge base with timestamped transcript evidence.

The current vertical slice supports secure accounts, knowledge spaces, source
preview and ingestion, background transcription, transcript chunking, vector
indexing, authenticated job streaming, transcript browsing, source-scoped
evidence retrieval, and cleanup when a source is deleted.

## Why SourceCast

Long-form media contains valuable ideas, but verifying a claim inside a
multi-hour recording is slow. SourceCast keeps research grounded by linking
retrieved evidence to the exact transcript timestamp and preserving source
attribution throughout the workflow.

## Implemented Workflow

1. Register or sign in.
2. Create a private knowledge space.
3. Preview and ingest a supported media URL.
4. Follow ingestion progress through authenticated Server-Sent Events.
5. Browse paginated timestamped transcript segments.
6. Ask a source-scoped question and inspect the strongest evidence cards.
7. Delete the source and clean up relational data, temporary audio, and vectors.

## Architecture

```text
Next.js frontend
      |
      | HTTP + authenticated SSE
      v
FastAPI backend
      |
      +-- PostgreSQL: users, spaces, sources, jobs, transcript segments, chunks
      +-- Redis + ARQ: asynchronous ingestion jobs
      +-- faster-whisper: timestamped transcription
      +-- sentence-transformers: local embeddings
      +-- Qdrant: tenant-filtered vector retrieval
```

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, TanStack Query, Zustand |
| Backend | FastAPI, Python, SQLAlchemy async, Alembic |
| Authentication | JWT access tokens and rotating HttpOnly refresh cookies |
| Database | PostgreSQL |
| Queue | Redis and ARQ |
| Transcription | faster-whisper |
| Embeddings | sentence-transformers |
| Vector database | Qdrant |

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker Desktop
- FFmpeg for audio extraction

### Start infrastructure

```powershell
docker compose up -d
```

### Start the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Start the worker in another terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python worker.py
```

### Start the frontend

```powershell
cd frontend
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. FastAPI documentation is available at
`http://localhost:8000/api/docs`.

## Verification

Run the fast quality gate before starting a new module:

```powershell
.\check_quality.ps1
```

Run the Docker-backed integration gate when PostgreSQL, Redis, and Qdrant are
available:

```powershell
.\check_integration.ps1
```

The current gates cover:

- Backend unit and service tests
- Worker success, failure, heartbeat, stale-job, and cleanup behavior
- Authenticated SSE event contracts
- Frontend SSE parsing
- Python compilation, frontend lint, and production build
- Real PostgreSQL persistence and cascading deletion
- Real Redis queue dispatch
- Real Qdrant tenant isolation and vector cleanup

## Current Status

| Area | Status |
|---|---|
| Secure authentication and session refresh | Implemented |
| Knowledge spaces | Implemented |
| Source preview and asynchronous ingestion | Implemented |
| Transcript storage and pagination | Implemented |
| Vector indexing and tenant-filtered retrieval | Implemented |
| SSE progress, stale detection, and retries | Implemented |
| Source cleanup | Implemented |
| Persisted evidence chat and answer streaming | Next |
| Comparison, saved insights, and research briefs | Planned |

## Privacy

SourceCast is designed for private research workflows. Full transcripts are not
published by default, retrieved evidence is excerpted, and source deletion
removes associated transcript records and vector points.

