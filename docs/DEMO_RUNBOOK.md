# SourceCast MVP Demo Runbook

This runbook gives a repeatable demo path after the automated gates pass.

## 1. Start Services

```powershell
docker compose up -d

cd backend
Copy-Item .env.example .env -Force
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd backend
.\.venv\Scripts\python.exe worker.py
```

In a third terminal:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:3000`.

Before starting the demo flow, verify the running stack:

```powershell
.\check_runtime.ps1
```

## 2. Prepare Demo Data

- Register a demo user with an email you can recognize.
- Create a space named `MVP Demo`.
- Add one short YouTube or direct-audio URL first.
- Wait for the progress bar to show completion.
- Add a second source before testing comparison.

YouTube sources with captions are ready in seconds. Other audio is transcribed
through OpenRouter at about a minute per hour of audio.

## 3. Demo Flow

1. Open the space and confirm both sources show `READY`.
2. Open one source and show paginated transcript segments.
3. Ask a source-scoped question and open a timestamp citation.
4. Return to the space and ask a space-scoped chat question.
5. Save the chat answer or one evidence card as an insight.
6. Start a new chat, then resume the previous chat from the session list.
7. Compare two indexed sources on a concrete topic.
8. Save one comparison point or evidence card.
9. Generate a Markdown research brief.
10. Preview and download the `.md` export.

## 4. Model Calls

Answers, transcription and embeddings go through OpenRouter, so
`backend/.env` needs `OPENROUTER_API_KEY`. Questions the sources cannot answer
return the "could not find enough support" message instead of a guess; that is
worth showing in the demo too.

## 5. Quick Recovery

- If ingestion appears stuck, check the worker terminal first.
- If Docker services are unavailable, restart Docker Desktop and rerun
  `.\check_integration.ps1`.
- If a source has poor retrieval results, save a clearer insight manually from
  another answer or compare a narrower topic.
