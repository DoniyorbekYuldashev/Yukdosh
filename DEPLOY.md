# Deploying Yukdosh on Azure — one VM: Postgres + web admin + driver bot + scraper

- **VM:** `Standard_B2als_v2` (2 vCPU, 4 GB RAM), region **Central India**, Ubuntu 24.04.
- **Cost:** ~$18/month for the VM + ~$5–10 (public IP, disk/bandwidth beyond the free amounts).
  Paid from the $200 free credit until it expires (**Nov 14, 2026**), then billed monthly.
- **Database:** Postgres container on the same VM (`COMPOSE_PROFILES=localdb` in `.env`).
  Loads older than 5 days are deleted, so it stays small (~15–20 MB).
- The admin site is **not** exposed to the internet — open it through an SSH tunnel.

Commands marked **[PC]** run in PowerShell on Windows; **[server]** run over SSH.

---

## 0. Push the latest code  [PC]
```powershell
cd "D:\All codes\Sarbon\sarbon"
git add -A
git commit -m "Deploy: Azure VM with local Postgres"
git push
```

## 1. Create the VM  (portal.azure.com → Virtual Machine → Create)
**Basics**
- Resource group: **Create new** → `yukdosh-rg`; VM name: `yukdosh-server`
- Region: **(Asia Pacific) Central India**; Availability: *No infrastructure redundancy required*
- Image: **Ubuntu Server 24.04 LTS – x64 Gen2**
- Size: **See all sizes** → search `B2als_v2` → **Standard_B2als_v2** (2 vCPU, 4 GiB)
- Authentication: **SSH public key**, username `azureuser`, **Generate new key pair**, name `yukdosh-key`
- Inbound ports: **Allow selected ports → SSH (22)** only

**Disks:** OS disk **Premium SSD (LRS)**, **64 GiB**. **Management:** auto-shutdown **off**.
Leave the rest default → **Review + create** → **Create** → **Download private key and create
resource** → save as `C:\Users\doniy\.ssh\yukdosh-key.pem`. Open the VM, copy its **Public IP**.

**Money safety (do now):** Cost Management → **Budgets** → add a **$5** alert.
**Before Nov 14:** portal home → **Upgrade to pay-as-you-go**, or Azure disables the account.

## 2. Connect  [PC]
Windows refuses a private key other users can read — restrict it once:
```powershell
icacls C:\Users\doniy\.ssh\yukdosh-key.pem /inheritance:r /grant:r "$($env:USERNAME):R"
ssh -i C:\Users\doniy\.ssh\yukdosh-key.pem azureuser@PUBLIC_IP
```

## 3. Get the code onto the server  [server]
Private repo → give the server a read-only **deploy key**:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/github -N "" && cat ~/.ssh/github.pub
```
GitHub → repo → Settings → **Deploy keys** → Add → paste it (leave "write" OFF). Then:
```bash
printf 'Host github.com\n  IdentityFile ~/.ssh/github\n' >> ~/.ssh/config
git clone git@github.com:DoniyorbekYuldashev/Yukdosh.git yukdosh
cd yukdosh
bash deploy/server_setup.sh     # updates, Docker, Tashkent time zone
exit          # log out once, then SSH back in (step 2) and:  cd yukdosh
```

## 4. Secrets  [server]
```bash
cp .env.example .env
openssl rand -hex 24      # run twice: one for POSTGRES_PASSWORD, one for ADMIN_PASSWORD
nano .env                 # keep COMPOSE_PROFILES=localdb; fill BOT_TOKEN, OPENAI_API_KEY, TELEGRAM_*
chmod 600 .env
```

## 5. ⚠ Stop Yukdosh on your PC first
Close `run_all` / `run_app` / `run_scraper` on Windows. Two copies of the same bot token or
the same Telegram session running at once fight each other (or get the session revoked).

## 6. Bring your data over (groups, settings, users, saved routes)  [PC → server]
**[PC]** dump the local database and upload it:
```powershell
& "D:\Programmes\PostgreSQL\16\bin\pg_dump.exe" -U postgres -d yukdosh -Fc --no-owner --no-privileges -f yukdosh.dump
scp -i C:\Users\doniy\.ssh\yukdosh-key.pem yukdosh.dump azureuser@PUBLIC_IP:~/yukdosh/
```
**[server]** load it into the new database:
```bash
docker compose up -d db
docker compose exec -T db pg_restore -U yukdosh -d yukdosh --no-owner --no-privileges < yukdosh.dump
rm yukdosh.dump
```
(Skip this step = fresh empty DB: re-add groups in the admin, then
`docker compose run --rm web python -m app.set_provider openai`.)
Old loads are deleted by the first pipeline run (5-day retention).

## 7. Telegram userbot session  [PC → server]
Reuse your existing login (no code needed) — the PC copy must stay stopped from now on:
```powershell
scp -i C:\Users\doniy\.ssh\yukdosh-key.pem yukdosh_session.session azureuser@PUBLIC_IP:~/yukdosh/
```
```bash
docker compose build
docker compose run --rm -T scheduler sh -c 'cat > /app/state/yukdosh_session.session' < yukdosh_session.session
rm yukdosh_session.session
```
Or log in fresh instead: `docker compose run --rm scheduler python -m app.scraper.login`
(enter the code Telegram sends you, and your 2FA password).

## 8. Start everything  [server]
```bash
docker compose up -d --build
docker compose ps                  # db "healthy", web "healthy", bot + scheduler "running"
docker compose logs -f scheduler   # Ctrl+C to stop watching (it keeps running)
free -m                            # RAM check
```
In the admin → Settings, make sure the **scheduler is ON**.

## 9. Open the admin  [PC]
```powershell
ssh -i C:\Users\doniy\.ssh\yukdosh-key.pem -N -L 8000:127.0.0.1:8000 azureuser@PUBLIC_IP
```
Leave that window open and browse to **http://localhost:8000** (log in with ADMIN_USER/PASSWORD).

## 10. Daily backups  [server]
```bash
chmod +x deploy/*.sh
(crontab -l 2>/dev/null; echo "0 4 * * * $HOME/yukdosh/deploy/backup.sh >> $HOME/yukdosh/backups/cron.log 2>&1") | crontab -
bash deploy/backup.sh    # test once
```
Copy a backup to your PC now and then:
`scp -i C:\Users\doniy\.ssh\yukdosh-key.pem "azureuser@PUBLIC_IP:~/yukdosh/backups/*.dump" .`

---

## Everyday use

| You changed…                         | On PC            | On server                              |
|--------------------------------------|------------------|----------------------------------------|
| Bot texts / formatting / web admin   | `git push`       | `bash deploy/update.sh` (scraper keeps running) |
| Parser / pipeline / scraper          | `git push`       | `bash deploy/update.sh all`            |
| Only `.env`                          | —                | `docker compose up -d`                 |

Logs: `docker compose logs -f bot` (or `web`, `scheduler`, `db`)
Restart one part: `docker compose restart bot`
Stop all: `docker compose down` — data is kept. **Never add `-v`: it deletes the database.**

## Later: shrink to the free 1 GB VM (database → Supabase)
Azure's 12-month free size is `Standard_B2ats_v2` (2 vCPU, **1 GB**) — too small for Postgres too,
so move the database to Supabase first (~15 min downtime, nothing lost):
1. Supabase: new project in **Mumbai**; copy Connect → **Session pooler** URI.
2. **[server]** `docker compose stop bot scheduler web && bash deploy/backup.sh`
3. Restore the newest dump into Supabase (from the server):
   `docker run --rm -i postgres:17-alpine pg_restore --no-owner --no-privileges -d "SESSION_POOLER_URI" < backups/yukdosh_YYYYMMDD_HHMM.dump`
4. `.env`: delete `COMPOSE_PROFILES` and the 3 `POSTGRES_*` lines, add `DATABASE_URL=<URI>`.
5. `docker compose up -d --remove-orphans` (the db container stops being used; its volume
   stays until you're sure — then `docker volume rm yukdosh_pgdata`).
6. Azure: VM → **Stop** → **Size** → `Standard_B2ats_v2` → **Start**. Run
   `bash deploy/server_setup.sh` once more — it adds 2 GB swap on machines with < 3 GB RAM.
