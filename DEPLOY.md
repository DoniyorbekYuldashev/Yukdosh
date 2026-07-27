# Deploying Sarbon24 on a VPS (Hetzner) with Docker

Runs the whole stack — Postgres + web admin + bot + scheduler + HTTPS — with one command.
Cost: ~€4/month (Hetzner CX22). The admin site is protected by a password and HTTPS.

---

## 1. Create the server
1. Sign up at https://console.hetzner.cloud → create a Project.
2. **Add Server**: Image = **Ubuntu 24.04**, Type = **CX22** (2 vCPU / 4 GB), pick a location.
3. Add your SSH key (recommended) or set a root password.
4. Copy the server's **public IP** (e.g. 203.0.113.45).

## 2. Free HTTPS link (DuckDNS) — gives you a clean web address
1. Go to https://www.duckdns.org → sign in → create a subdomain, e.g. `sarbon24`.
2. Set its IP to your server's IP. Your admin link becomes `https://sarbon24.duckdns.org`.
   (Skip this only if you don't mind using `http://SERVER_IP:8000` without HTTPS.)

## 3. Connect + install Docker
```bash
ssh root@SERVER_IP
curl -fsSL https://get.docker.com | sh          # installs Docker + Compose
```

## 4. Get the code (private repo)
Create a GitHub token: GitHub → Settings → Developer settings → **Personal access tokens**
→ Fine-grained token → read-only access to the Sarbon24 repo. Then:
```bash
git clone https://YOUR_TOKEN@github.com/YOUR_USERNAME/Sarbon24.git
cd Sarbon24
```

## 5. Create the .env (production values)
```bash
nano .env
```
Paste and fill in:
```
POSTGRES_USER=sarbon
POSTGRES_PASSWORD=CHANGE_ME_strong_db_password
POSTGRES_DB=sarbon

ADMIN_USER=admin
ADMIN_PASSWORD=CHANGE_ME_strong_admin_password

DOMAIN=sarbon24.duckdns.org        # or leave as localhost if using IP:port

BOT_TOKEN=your-botfather-token
OPENAI_API_KEY=your-openai-key      # or GEMINI_API_KEY=...
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_PHONE=+998...
```
Save: Ctrl+O, Enter, Ctrl+X.
(No DATABASE_URL needed — docker-compose sets it to the internal Postgres automatically.)

## 6. Upload the Telegram session (do this BEFORE step 7)
The scraper needs your login session file. You already have it locally.
From YOUR computer (PowerShell), in the project folder:
```powershell
scp sarbon_session.session root@SERVER_IP:~/Sarbon24/
```
(If you don't have it: on the server run `docker compose run --rm scheduler python -m app.scraper.login`
and enter the code Telegram sends — but uploading the existing file is easier.)

## 7. Launch everything
```bash
docker compose up -d --build
```
Wait ~1 minute for the build. Check it's running:
```bash
docker compose ps
docker compose logs -f web bot scheduler
```

## 8. Open the admin
- Visit `https://sarbon24.duckdns.org` (or `http://SERVER_IP:8000`).
- Log in with ADMIN_USER / ADMIN_PASSWORD.
- Go to **Settings** → add your Telegram groups → turn the **scheduler ON** with a 1–2 min interval → Save.
- Message your bot on Telegram to test search.

---

## Everyday commands
```bash
cd ~/Sarbon24
docker compose ps                 # status
docker compose logs -f scheduler  # watch scraping
docker compose restart bot        # restart one service
git pull && docker compose up -d --build   # deploy an update
```

## Backup the database (weekly is plenty)
```bash
docker compose exec db pg_dump -U sarbon sarbon > backup_$(date +%F).sql
```

## Restore a backup
```bash
cat backup_2026-07-20.sql | docker compose exec -T db psql -U sarbon sarbon
```
