# SourceCast on AWS EC2

This deployment runs SourceCast on one always-on EC2 instance:

- Caddy reverse proxy on ports `80` and `443`
- Next.js frontend
- FastAPI backend
- ARQ background worker
- External managed Supabase Postgres, Upstash Redis, Qdrant Cloud, and Groq

The frontend and backend share one origin. Browser calls use `/api/v1/...`, and
Caddy routes `/api/*` to FastAPI.

## Recommended Instance

Start with `t4g.small` in a low-cost region such as `us-east-1`:

- 2 vCPU
- 2 GiB RAM
- Enough for the hosted MVP because transcription and vector storage are
  offloaded to Groq and Qdrant Cloud.

Use Ubuntu 24.04 ARM64. Allocate at least 20 GB gp3 EBS.

## Security Group

Allow inbound:

| Port | Source | Purpose |
|---|---|---|
| `22` | Your IP only | SSH |
| `80` | `0.0.0.0/0` | HTTP / Let's Encrypt |
| `443` | `0.0.0.0/0` | HTTPS |

Do not expose backend port `8000` or frontend port `3000` publicly.

## Bootstrap

Copy `bootstrap-ec2.sh` into EC2 user data when launching the instance, or run it
manually as root:

```bash
sudo bash bootstrap-ec2.sh
```

It installs Docker, clones the repo into `/opt/sourcecast`, and creates:

```text
/opt/sourcecast/deploy/aws/.env
```

If you want AWS CLI to create the EC2 instance, security group, and key pair,
run this locally from PowerShell:

```powershell
.\deploy\aws\provision-ec2.ps1 -Region us-east-1 -InstanceType t4g.small
```

By default, SSH is restricted to your current public IP and HTTP/HTTPS are open.
The script saves a generated private key under `deploy/aws/*.pem`, which is
ignored by git.

## Configure Secrets

SSH into the instance and edit:

```bash
sudo nano /opt/sourcecast/deploy/aws/.env
```

For first boot by public IP:

```env
SOURCECAST_SITE_ADDRESS=:80
FRONTEND_URL=http://YOUR_EC2_PUBLIC_IP
NEXT_PUBLIC_API_URL=
```

After pointing a domain to the EC2 public IP:

```env
SOURCECAST_SITE_ADDRESS=sourcecast.example.com
FRONTEND_URL=https://sourcecast.example.com
NEXT_PUBLIC_API_URL=
```

Keep `NEXT_PUBLIC_API_URL` empty for AWS. That makes the frontend call the API on
the same origin through Caddy.

## Start

```bash
cd /opt/sourcecast/deploy/aws
docker compose up -d --build
```

Apply migrations from the backend container:

```bash
docker compose exec backend python -m alembic upgrade head
```

Check health:

```bash
docker compose ps
curl http://localhost/health
```

Validate the compose file without real secrets:

```bash
SOURCECAST_ENV_FILE=./.env.example docker compose --env-file .env.example config
```

## Deploy Updates

```bash
cd /opt/sourcecast
git pull --ff-only
cd deploy/aws
docker compose up -d --build
docker compose exec backend python -m alembic upgrade head
```

## Logs

```bash
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f frontend
docker compose logs -f caddy
```

## Cost Guardrails

- Use one EC2 instance only for the MVP.
- Keep Supabase, Upstash, and Qdrant on their existing plans.
- Set an AWS Budget alert below your project cap, for example `$25` and `$40`.
- Stop or terminate the EC2 instance when you no longer need the always-on demo.

Create a `$40/month` AWS Budget alert from PowerShell:

```powershell
.\deploy\aws\create-budget.ps1 -MonthlyLimitUsd 40 -AlertEmail you@example.com
```

AWS sends a confirmation email before budget notifications activate.
