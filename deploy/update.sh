#!/usr/bin/env bash
# Pull the latest code and restart only what you choose.
#   bash deploy/update.sh            -> bot + web only (scraper keeps running)  [default]
#   bash deploy/update.sh all        -> everything, incl. scraper/parser
set -euo pipefail
cd "$(dirname "$0")/.."
git pull
if [ "${1:-app}" = "all" ]; then
  docker compose up -d --build
else
  docker compose up -d --build bot web
fi
docker compose ps
