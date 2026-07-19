#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/sourcecast"
REPO_URL="${SOURCECAST_REPO_URL:-https://github.com/atikulmunna/SourceCast.git}"

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker

if [ ! -d "$APP_DIR/.git" ]; then
  rm -rf "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only
fi

cd "$APP_DIR/deploy/aws"
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
fi

cat <<MSG
SourceCast bootstrap complete.

Next:
1. Edit $APP_DIR/deploy/aws/.env with production secrets.
2. Run:
   cd $APP_DIR/deploy/aws
   docker compose up -d --build
3. Check:
   docker compose ps
   curl http://localhost/health
MSG
