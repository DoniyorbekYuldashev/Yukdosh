#!/usr/bin/env bash
# Dump the database to ./backups (keeps the last 14). Run by cron daily — see DEPLOY.md.
# Works in both modes: the local db container, or a hosted DATABASE_URL (Supabase keeps
# no backups on its free plan). Hosted mode uses a throwaway postgres:17 client container.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
f="backups/yukdosh_$(date +%Y%m%d_%H%M).dump"
if [ -n "$(docker compose ps -q db 2>/dev/null)" ]; then
  PGU=$(grep -E "^POSTGRES_USER=" .env | cut -d= -f2- || true); PGU=${PGU:-yukdosh}
  PGD=$(grep -E "^POSTGRES_DB=" .env | cut -d= -f2- || true); PGD=${PGD:-yukdosh}
  docker compose exec -T db pg_dump -U "$PGU" -d "$PGD" -Fc --no-owner --no-privileges > "$f"
else
  URL=$(grep -E "^DATABASE_URL=" .env | cut -d= -f2-)
  URL=${URL/postgresql+asyncpg:/postgresql:}
  docker run --rm postgres:17-alpine pg_dump "$URL" -Fc --no-owner --no-privileges > "$f"
fi
ls -1t backups/yukdosh_*.dump | tail -n +15 | xargs -r rm --
echo "backup: $f"
