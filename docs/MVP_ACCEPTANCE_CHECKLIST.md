# SourceCast MVP Acceptance Checklist

Use this checklist before tagging or demoing the MVP. The automated gates should
pass first:

```powershell
.\check_quality.ps1
.\check_integration.ps1
```

## Environment

- Docker services start with `docker compose up -d`.
- `backend/.env` is copied from `backend/.env.example`.
- `LLM_PROVIDER=extractive` works without external API keys.
- `alembic upgrade head` applies through `005_research_briefs_schema`.
- Backend API docs load at `http://localhost:8000/api/docs`.
- Frontend loads at `http://localhost:3000`.

## Authentication and Spaces

- A new user can register.
- The user can log in and refresh the session.
- The user can create a knowledge space.
- Space-scoped data is not visible to another user.

## Source Ingestion

- A supported media URL can be previewed before ingestion.
- Preview shows metadata and processing estimate.
- Ingestion creates a background job.
- Job progress streams through authenticated SSE.
- Transcription, chunking, embedding, and indexing complete.
- Temporary audio is deleted according to the configured storage policy.
- The transcript viewer shows paginated timestamped segments.

## Evidence Chat

- A user can ask a source-scoped question.
- A user can ask a space-scoped question.
- Answers include evidence cards when evidence exists.
- Unsupported questions return a clear insufficient-evidence response.
- Evidence cards show title, excerpt, confidence, timestamp, and source link.
- YouTube evidence links open at the cited timestamp.
- Chat sessions persist.
- Prior chat sessions can be resumed.
- Deleting a chat removes its messages and evidence.

## Comparison

- A user can select at least two indexed sources.
- A comparison request returns source-grouped evidence.
- Missing evidence is stated per source.
- Local extractive mode does not invent agreements or differences.
- Citation links remain available on comparison evidence rows.

## Saved Insights

- A user can save a chat answer.
- A user can save a chat evidence card.
- A user can save comparison text or evidence.
- Saved insights appear in the owning space.
- Saved insights can be deleted.

## Research Briefs

- A user can generate a Markdown research brief from a space.
- Selected sources are listed in the brief.
- Saved insights appear in the key findings and evidence table.
- The brief includes limitations and missing-evidence language.
- The user can preview the Markdown.
- The user can export/download Markdown.
- Old briefs can be deleted.

## Cleanup and Regression

- Deleting a source removes relational transcript data and vector points.
- PostgreSQL, Redis, and Qdrant integration tests pass.
- Frontend lint and production build pass.
- No SRS documents are tracked by git.
