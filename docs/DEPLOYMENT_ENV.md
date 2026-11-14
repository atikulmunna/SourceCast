# SourceCast Deployment Environment

Use this checklist before setting `ENVIRONMENT=production`.

## Required Backend Values

| Variable | Production requirement |
|---|---|
| `ENVIRONMENT` | Set to `production`. |
| `DEBUG` | Set to `false`. |
| `DATABASE_URL` | Use a managed or private PostgreSQL URL; for Neon, the pooled URL. |
| `DIRECT_URL` | Optional migration-only database URL; for Neon, the direct (non-pooled) URL. |
| `REDIS_URL` | Use a managed or private Redis URL; use `rediss://` for TLS providers such as Upstash. |
| `QDRANT_URL` | Use a hosted Qdrant URL or a private service URL. |
| `OPENROUTER_API_KEY` | A real OpenRouter key; production refuses to start without one. Server side only, never in a `NEXT_PUBLIC_*` variable. |
| `JWT_ACCESS_SECRET` | Use a random secret with at least 32 characters. |
| `JWT_REFRESH_SECRET` | Use a different random secret with at least 32 characters. |
| `FRONTEND_URL` | Use the deployed frontend origin, for example `https://app.example.com`. |

## Optional Backend Values

| Variable | When needed |
|---|---|
| `QDRANT_API_KEY` | Required only for hosted Qdrant instances that enforce API keys. |
| `OPENROUTER_BASE_URL` | Keep the default (`https://openrouter.ai/api/v1`). |
| `OPENROUTER_TIMEOUT_SECONDS` | Timeout for chat and embedding requests. Default `60`. |
| `OPENROUTER_MAX_RETRIES` | Retries for rate limits and transient upstream errors. Default `3`. |
| `CHAT_MODEL` | `openrouter/auto` (the Auto Router) or a fixed model slug. |
| `CHAT_ALLOWED_MODELS` | Comma-separated models the Auto Router may pick; wildcards such as `deepseek/deepseek-v4.1-flash*` work. |
| `CHAT_COST_TIER` | Auto Router policy: `low`, `medium` or `high`. Default `low`. |
| `CHAT_MAX_PROMPT_PRICE`, `CHAT_MAX_COMPLETION_PRICE` | Price cap in USD per million tokens; `0` means no cap. |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` | Embedding model and its vector size. Changing either starts a new collection (see below). |
| `TRANSCRIPTION_MODEL` | Whisper model that returns `verbose_json` segments. |
| `TRANSCRIPTION_CHUNK_MINUTES` | Audio chunk length for transcription. Default `10`. |
| `TRANSCRIPTION_TIMEOUT_SECONDS` | Timeout per audio chunk. Default `120`. |
| `YOUTUBE_TRANSCRIPT_LANGUAGES` | Comma-separated YouTube caption language preference order. Defaults to `en,en-US,en-GB`. |
| `YTDLP_COOKIES_FILE` | Optional path to a Netscape-format YouTube cookies file mounted into the backend container. |
| `YTDLP_PROXY_URL` | Optional proxy URL for yt-dlp metadata/audio requests. |
| `YOUTUBE_TRANSCRIPT_PROXY_HTTP_URL` | Optional generic HTTP proxy URL for YouTube transcript requests. |
| `YOUTUBE_TRANSCRIPT_PROXY_HTTPS_URL` | Optional generic HTTPS proxy URL for YouTube transcript requests. |
| `WEBSHARE_PROXY_USERNAME` | Optional Webshare rotating residential proxy username for YouTube transcript requests. |
| `WEBSHARE_PROXY_PASSWORD` | Optional Webshare rotating residential proxy password for YouTube transcript requests. |
| `WEBSHARE_PROXY_LOCATIONS` | Optional comma-separated Webshare country filters, for example `us,de`. |
| `WORKER_MAX_JOBS` | Keep `1` on small/free hosted workers. |
| `WORKER_POLL_DELAY_SECONDS` | Use `10` or higher on request-metered Redis providers such as Upstash free tier. |

## Neon Database URLs

The hosted database is Neon Postgres. Neon gives two connection strings for the
same database: a pooled one (the host ends in `-pooler`; PgBouncer in
transaction mode) and a direct one. Use the pooled URL for the app and the
direct URL for Alembic migrations:

```env
DATABASE_URL=postgresql://USER:PASSWORD@ep-name-123456-pooler.c-2.us-east-1.aws.neon.tech/sourcecast?sslmode=require&channel_binding=require
DIRECT_URL=postgresql://USER:PASSWORD@ep-name-123456.c-2.us-east-1.aws.neon.tech/sourcecast?sslmode=require&channel_binding=require
```

Paste both as the Neon console prints them, or as `neon connection-string`
prints them (add `--pooled` for `DATABASE_URL`). SourceCast adapts them for
asyncpg: it switches the driver to `postgresql+asyncpg`, turns `sslmode` into
`ssl`, and drops `channel_binding`, which asyncpg does not support. If a
password includes reserved URL characters, URL-encode it.

For the pooled URL, SourceCast detects the `-pooler` host, turns off asyncpg's
prepared-statement cache and opens a fresh connection per session, so nothing
depends on reaching the same server connection twice.

On the free plan, Neon suspends the compute after 5 minutes without queries and
wakes it on the next connection, which adds a few hundred milliseconds to that
first request. Neon does not pause the project itself, so the database needs no
keepalive job. Keep the Neon project in the same region as the EC2 instance
(`aws-us-east-1` by default).

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

## OpenRouter

SourceCast makes every AI call through OpenRouter with one key. Use a dedicated
key with a credit limit set in the OpenRouter dashboard, and a separate key for
local development so spend shows per environment.

| Job | Default | Why | Cost |
|---|---|---|---|
| Answers and comparisons | Auto Router (`openrouter/auto`), `low` tier, limited to `openai/gpt-6-luna` and `deepseek/deepseek-v4.1-flash*` | Matched the `medium` tier on the eval at about a sixth of the cost | about $0.0004 per answer |
| Transcription | `openai/whisper-large-v3-turbo` | Same timestamp accuracy as `whisper-large-v3` on a one-hour talk, for less than half the price | about $0.012 per hour of audio |
| Embeddings | `mongodb/voyage-4-lite`, 1024 dimensions | Found the expected moment in the top 5 for every eval question | about $0.02 per million tokens |

Prices and models change; run the eval in `backend/evals` before switching one.

Before transcription, audio is converted to 16 kHz mono and split into
10-minute chunks, which keeps every request under OpenRouter's 25 MB upload cap
and 60-second upstream timeout. The worker needs ffmpeg; the backend image
includes it.

`CHAT_MAX_PROMPT_PRICE` and `CHAT_MAX_COMPLETION_PRICE` reject any model priced
above the cap. If no allowed model fits, a question fails with "no allowed model
is available".

### Changing the embedding model

The Qdrant collection is named after the embedding model and its dimensions, for
example `source_chunks_voyage_4_lite_1024`. Changing `EMBEDDING_MODEL` or
`EMBEDDING_DIMENSIONS` starts a new, empty collection, so existing sources stop
appearing in search until they are re-ingested. Afterwards, remove the old
collections (the first command only lists them):

```sh
docker compose exec backend python -m app.cli.prune_vector_collections
docker compose exec backend python -m app.cli.prune_vector_collections --apply
```

## Keeping the Free Tiers Awake

Qdrant Cloud suspends a free cluster after a week without requests, and Upstash
archives a free Redis database after 30 days without activity. The `Managed
Services Keepalive` workflow (`.github/workflows/keepalive.yml`) pings both every
day and re-enables itself, so GitHub's 60-day inactivity rule cannot switch it
off. It needs these repository secrets: `QDRANT_URL`, `QDRANT_API_KEY`,
`UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_READONLY_TOKEN`. Neon needs no
keepalive.

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

Cloud provider IPs may also be blocked from public YouTube transcript endpoints.
The most reliable production option is a rotating residential proxy for
transcript lookup. With Webshare Residential proxies, set these on both the web
service and worker:

```env
WEBSHARE_PROXY_USERNAME=your-webshare-proxy-username
WEBSHARE_PROXY_PASSWORD=your-webshare-proxy-password
WEBSHARE_PROXY_LOCATIONS=us
```

For another proxy provider, use generic proxy URLs:

```env
YOUTUBE_TRANSCRIPT_PROXY_HTTP_URL=http://user:password@host:port
YOUTUBE_TRANSCRIPT_PROXY_HTTPS_URL=http://user:password@host:port
YTDLP_PROXY_URL=http://user:password@host:port
```

The transcript proxy is used before audio download. `YTDLP_PROXY_URL` is only
needed when you also want yt-dlp metadata or audio fallback traffic to use the
same proxy.

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

## AWS Container Packaging

The repository includes production Dockerfiles for the backend and frontend plus
an AWS EC2 Docker Compose bundle in `deploy/aws`.

For the simplest production path, copy `deploy/aws/.env.example` to
`deploy/aws/.env`, fill in real secrets, then run:

```sh
cd deploy/aws
docker compose up -d --build
docker compose exec backend python -m alembic upgrade head
```

The AWS compose setup runs four containers on one EC2 instance:

- `caddy`: public reverse proxy on ports `80` and `443`
- `frontend`: Next.js standalone server
- `backend`: FastAPI API
- `worker`: ARQ ingestion worker

Keep `NEXT_PUBLIC_API_URL` empty in `deploy/aws/.env` so the browser calls the
API on the same origin through Caddy.
