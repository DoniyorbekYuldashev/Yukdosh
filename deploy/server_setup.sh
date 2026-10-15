#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu server (Oracle Always Free, x86 or ARM).
# Run on the server:   bash deploy/server_setup.sh
set -euo pipefail

echo "==> Updating system"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
sudo apt-get install -y git curl ca-certificates unattended-upgrades

echo "==> Timezone: Asia/Tashkent"
sudo timedatectl set-timezone Asia/Tashkent || true

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker (official script from get.docker.com)"
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker

# Small machines (1 GB AMD micro) need swap or the build/pip can run out of memory.
MEM_MB=$(free -m | awk '/^Mem:/{print $2}')
if [ "$MEM_MB" -lt 3000 ] && [ ! -f /swapfile ]; then
  echo "==> RAM is ${MEM_MB} MB — adding 2 GB swap"
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo
echo "✅ Server ready. IMPORTANT: log out and SSH back in once (so 'docker' works without sudo)."
