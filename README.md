# SourceCast

<p align="center">
  <a href="docs/DEMO_ACCESS_REQUEST.md">
    <img alt="Request SourceCast demo access" src="https://img.shields.io/badge/Request%20Demo%20Access-SourceCast-007AFF?style=for-the-badge">
  </a>
  <a href="docs/DEMO_RUNBOOK.md">
    <img alt="Demo runbook" src="https://img.shields.io/badge/Demo-Runbook-111111?style=for-the-badge">
  </a>
  <a href="deploy/aws/README.md">
    <img alt="AWS deployment" src="https://img.shields.io/badge/Deploy-AWS%20EC2-FF9900?style=for-the-badge">
  </a>
</p>

<p align="center">
  <strong>Evidence-grounded research for long-form audio and video.</strong>
</p>

SourceCast turns podcasts, talks, interviews, lectures, and direct audio sources
into timestamped transcripts, searchable evidence, and citation-backed answers.
It is built for research workflows where the answer is only useful if the user
can inspect the supporting passage and return to the source.

![SourceCast ingestion and evidence workflow](docs/assets/sourcecast-demo.gif)

## Highlights

- Ingest media URLs through an asynchronous worker pipeline.
- Generate timestamped transcripts and source-level transcript views.
- Chunk, embed, and index source text in Qdrant for retrieval.
- Ask source-scoped or workspace-scoped questions.
- Return answers with cited evidence cards, confidence labels, and timestamp
  links, or say plainly that the sources do not answer the question.
- Run every model call (answers, transcription, embeddings) through one
  OpenRouter key, with each model chosen on a small evaluation set.
- Manage private accounts, knowledge spaces, saved chats, comparisons, saved
  insights, and Markdown research briefs.
- Run production as a single AWS EC2 Docker Compose deployment with Caddy,
  FastAPI, Next.js, and a background worker.

## Live Demo

The hosted demo runs on AWS EC2 on demand. To keep AWS costs low, SourceCast does
not use an Elastic IP, so raw `sslip.io` demo links may change after the server
is stopped and restarted.

<p>
  <a href="docs/DEMO_ACCESS_REQUEST.md">
    <img alt="Request demo access" src="https://img.shields.io/badge/Request%20Current%20Demo%20Link-Contact%20Author-007AFF?style=for-the-badge">
  </a>
</p>

If an old demo link does not load, the server is likely stopped or AWS has
assigned a new public IP. Contact the author for the current link and demo
credentials.

Recommended demo sources:

- TED talks
- Podcast pages or RSS audio links
- Direct `.mp3` URLs

YouTube support is implemented with captions-first ingestion and optional
cookies/proxy settings, but hosted YouTube extraction can still be unreliable
because YouTube frequently blocks cloud IP addresses.

## Core Workflow

```text
source URL
  -> metadata preview
  -> background ingestion job
  -> transcript segments
  -> chunks
  -> embeddings
  -> Qdrant index
  -> retrieval
  -> cited answer
```

The deployed MVP has been smoke-tested for:

- Signup and login
- Knowledge space creation
- Source preview
- Background ingestion
- Hosted transcription
- Transcript browsing
- Vector indexing
- Ask-with-evidence
- Workspace cleanup

## Architecture

```text
AWS EC2
  |
  +-- Caddy reverse proxy
        |
        +-- Next.js frontend
        +-- FastAPI backend
        +-- ARQ worker
        |
        +-- Neon Postgres: app data
        +-- Upstash Redis: ingestion queue
        +-- Qdrant Cloud: vector retrieval
        +-- OpenRouter: answers, transcription, embeddings
```

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, TanStack Query, Zustand |
| Backend | FastAPI, Python, SQLAlchemy async, Alembic |
| Auth | JWT access tokens and rotating HttpOnly refresh cookies |
| Worker | ARQ background jobs |
| Database | PostgreSQL |
| Queue | Redis |
| Answers | OpenRouter Auto Router, low cost tier, limited to two measured models |
| Transcription | OpenRouter `whisper-large-v3-turbo`, audio split into 10-minute chunks with ffmpeg |
| Embeddings | OpenRouter `voyage-4-lite` (1024 dimensions) |
| Retrieval | Qdrant |
| Deployment | AWS EC2, Docker Compose, Caddy, Let's Encrypt |

## Deployment

Production runs from `deploy/aws` on one small EC2 instance:

- `backend`: FastAPI API
- `worker`: ingestion worker
- `frontend`: Next.js standalone server
- `caddy`: HTTPS reverse proxy

The frontend and backend share one origin. Browser requests use `/api/v1/...`,
and Caddy routes `/api/*` to the backend.

Start here:

- [AWS EC2 Runbook](deploy/aws/README.md)
- [Environment Guide](docs/DEPLOYMENT_ENV.md)
- [Demo Runbook](docs/DEMO_RUNBOOK.md)

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

Put an OpenRouter key in `backend/.env` (`OPENROUTER_API_KEY=...`). Answers,
transcription and embeddings all need it; the tests do not. Use a separate key
with a low credit limit for local work.

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

## Environment

For the hosted MVP, configure the backend and worker with:

```env
ENVIRONMENT=production
DEBUG=false
OPENROUTER_API_KEY=your_openrouter_key
DATABASE_URL=postgresql://...-pooler...neon.tech/sourcecast?sslmode=require
DIRECT_URL=postgresql://...neon.tech/sourcecast?sslmode=require
REDIS_URL=rediss://...
QDRANT_URL=https://your-qdrant-cluster.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_key
```

For AWS same-origin hosting, keep:

```env
NEXT_PUBLIC_API_URL=
```

This makes the frontend call `/api/v1/...` on the same HTTPS origin instead of
calling a separate backend URL. The [Environment Guide](docs/DEPLOYMENT_ENV.md)
lists every setting and the model defaults.

## Evaluation

`backend/evals` measures retrieval and answers on three public talks (an hour
on large language models, half an hour on economics, twenty minutes on
education) with 25 questions tied to a timestamp and 5 the talks cannot answer.
It spends credits, so it runs by hand:

```powershell
cd backend
python -m evals.run_eval --chat settings
```

With the current defaults, all 25 answerable questions get an answer citing the
right moment, all 5 unanswerable ones are refused, and an answer costs about
$0.0004. The transcripts are cached locally and not committed.

## Verification

Run the full local quality gate:

```powershell
.\check_quality.ps1
```

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
docs/           Deployment notes, demo runbook, demo access
deploy/aws/     AWS EC2 Docker Compose deployment bundle
docker-compose.yml
check_quality.ps1
check_integration.ps1
check_runtime.ps1
```

## Privacy Model

SourceCast is designed for private research workflows. User data is scoped by
account, retrieval filters enforce user ownership, and deleting a source removes
its transcript records and vector points.
