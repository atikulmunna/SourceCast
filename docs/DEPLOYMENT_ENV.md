# SourceCast Deployment Environment

Use this checklist before setting `ENVIRONMENT=production`.

## Required Backend Values

| Variable | Production requirement |
|---|---|
| `ENVIRONMENT` | Set to `production`. |
| `DEBUG` | Set to `false`. |
| `DATABASE_URL` | Use a managed or private PostgreSQL URL. |
| `DIRECT_URL` | Optional migration-only database URL; recommended for Supabase session pooler. |
| `REDIS_URL` | Use a managed or private Redis URL; use `rediss://` for TLS providers such as Upstash. |
| `QDRANT_URL` | Use a hosted Qdrant URL or a private service URL. |
| `JWT_ACCESS_SECRET` | Use a random secret with at least 32 characters. |
| `JWT_REFRESH_SECRET` | Use a different random secret with at least 32 characters. |
| `FRONTEND_URL` | Use the deployed frontend origin, for example `https://app.example.com`. |

## Optional Backend Values

| Variable | When needed |
|---|---|
| `QDRANT_API_KEY` | Required only for hosted Qdrant instances that enforce API keys. |
| `GROQ_API_KEY` | Required only when `LLM_PROVIDER=groq`. |
| `GROQ_BASE_URL` | Keep the default unless Groq changes the API base URL. |
| `LLM_PROVIDER` | Keep `extractive` for no external LLM key, or use `groq` for hosted generation. |
| `LLM_MODEL` | Set to the hosted model name when using `groq`. |
| `TRANSCRIPTION_PROVIDER` | Use `local` for local faster-whisper or `groq` for hosted transcription. |
| `GROQ_TRANSCRIPTION_MODEL` | Use `whisper-large-v3-turbo` for fast hosted transcription, or `whisper-large-v3` for higher accuracy. |
| `TRANSCRIPTION_TIMEOUT_SECONDS` | HTTP timeout for hosted transcription requests. |
| `EMBEDDING_PROVIDER` | Use `hash` on small hosted workers, or `sentence-transformers` when the worker can load MiniLM. |
| `WHISPER_MODEL` | Use `tiny` for small Render workers; larger models need more memory, CPU, or GPU capacity. |
| `YOUTUBE_TRANSCRIPT_LANGUAGES` | Comma-separated YouTube caption language preference order. Defaults to `en,en-US,en-GB`. |
| `YTDLP_COOKIES_FILE` | Optional path to a Netscape-format YouTube cookies file mounted into the backend container. |
| `WORKER_MAX_JOBS` | Keep `1` on small/free hosted workers. |
| `WORKER_POLL_DELAY_SECONDS` | Use `10` or higher on request-metered Redis providers such as Upstash free tier. |

## Supabase Database URLs

For Supabase, use the transaction-mode pooler for runtime and the session-mode
pooler for Alembic migrations:

```env
DATABASE_URL=postgresql+asyncpg://postgres.project-ref:YOUR_URL_ENCODED_PASSWORD@aws-1-region.pooler.supabase.com:6543/postgres?ssl=require&prepared_statement_cache_size=0
DIRECT_URL=postgresql+asyncpg://postgres.project-ref:YOUR_URL_ENCODED_PASSWORD@aws-1-region.pooler.supabase.com:5432/postgres?ssl=require
```

If the password includes reserved URL characters, URL-encode it before placing it
in either connection string.

SourceCast automatically detects the Supabase transaction pooler URL and disables
asyncpg prepared-statement caching for runtime connections.

## Redis URLs

Upstash Redis typically requires TLS:

```env
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST.upstash.io:6379
```

If the worker logs `Connection closed by server` while connecting to an Upstash
host, confirm the URL starts with `rediss://` instead of `redis://`.

If the worker logs `max requests limit exceeded`, the Redis plan has exhausted
its request quota. Create a fresh Redis instance, wait for the quota reset, or
upgrade the plan. Also keep the worker polling slower on request-metered Redis:

```env
WORKER_MAX_JOBS=1
WORKER_POLL_DELAY_SECONDS=10
```

## Whisper Model Size

For low-memory hosted workers, keep:

```env
WHISPER_MODEL=tiny
```

If Render logs show the worker downloading `faster-whisper-base` and then the
instance restarts without a Python traceback, the process was likely killed by
the platform while loading the model. Upgrade the worker before using `base` or
larger models.

## Hosted Transcription

Small Render workers may also restart while loading `faster-whisper-tiny`. In
that case, offload transcription to Groq on both the web service and the
background worker:

```env
TRANSCRIPTION_PROVIDER=groq
GROQ_API_KEY=your-groq-api-key
GROQ_TRANSCRIPTION_MODEL=whisper-large-v3-turbo
TRANSCRIPTION_TIMEOUT_SECONDS=300
```

When `TRANSCRIPTION_PROVIDER=groq`, `WHISPER_MODEL` is ignored for ingestion.

## YouTube Sources

SourceCast tries YouTube captions before downloading audio. When captions are
available, ingestion skips audio download and hosted transcription, which is
faster and avoids many server-side bot checks.

Use this language preference list on both the web service and worker:

```env
YOUTUBE_TRANSCRIPT_LANGUAGES=en,en-US,en-GB
```

Some YouTube videos still block hosted metadata or audio extraction. For those,
mount a Netscape-format cookies file into the backend container and set:

```env
YTDLP_COOKIES_FILE=/app/secrets/youtube-cookies.txt
```

Do not commit the cookies file. Treat it like a password and rotate it if it is
shared accidentally.

## Hosted Worker Embeddings

Small Render workers can also restart while loading the local
`sentence-transformers/all-MiniLM-L6-v2` embedding model. For the MVP demo path,
use deterministic hash embeddings instead:

```env
EMBEDDING_PROVIDER=hash
DEFAULT_EMBEDDING_MODEL=all-MiniLM-L6-v2
DEFAULT_QDRANT_COLLECTION=source_chunks_v1_minilm_384
```

Hash embeddings keep Qdrant indexing and retrieval working without loading a
local ML model. Use `EMBEDDING_PROVIDER=sentence-transformers` again when the
backend runs on a worker with enough memory for MiniLM.

## Required Frontend Values

| Variable | Production requirement |
|---|---|
| `NEXT_PUBLIC_API_URL` | Use the deployed backend origin, for example `https://api.example.com`. |
| `NEXT_PUBLIC_APP_NAME` | Keep `SourceCast` unless renaming the app. |

## Secret Generation

Generate separate JWT secrets with PowerShell:

```powershell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
```

Run the quality gate after changing env behavior:

```powershell
.\check_quality.ps1
```

Run the runtime smoke check after deploying or restarting services:

```powershell
.\check_runtime.ps1 -BackendUrl "https://api.example.com" -FrontendUrl "https://app.example.com"
```

## Container Packaging

The repository includes production Dockerfiles for the backend and frontend plus
`docker-compose.prod.example.yml`. Copy the example compose file before editing
real secrets, then replace every `replace-with-*` value.

The production compose example stays on `LLM_PROVIDER=extractive`, so no hosted
LLM API key is required until you choose to enable `groq`.

For Render Docker deployments, set the backend web service Docker command to:

```sh
./start-web.sh
```

Set the Render background worker Docker command to:

```sh
./start-worker.sh
```
