# SourceCast Deployment Environment

Use this checklist before setting `ENVIRONMENT=production`.

## Required Backend Values

| Variable | Production requirement |
|---|---|
| `ENVIRONMENT` | Set to `production`. |
| `DEBUG` | Set to `false`. |
| `DATABASE_URL` | Use a managed or private PostgreSQL URL. |
| `REDIS_URL` | Use a managed or private Redis URL. |
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
| `WHISPER_MODEL` | Smaller models are faster; larger models need more CPU or GPU capacity. |

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
