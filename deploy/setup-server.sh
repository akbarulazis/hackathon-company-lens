#!/bin/bash
# Company Lens - AWS EC2 Server Setup Script
set -e

echo "=== Installing dependencies ==="
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Docker Compose plugin
sudo apt install -y docker-compose-plugin

# Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Python 3.11
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# PM2
sudo npm install -g pm2

# Nginx
sudo apt install -y nginx

echo "=== Cloning repository ==="
cd /home/ubuntu
git clone https://github.com/akbarulazis/hackathon-company-lens.git app
cd app

echo "=== Starting Docker services ==="
sudo docker compose up -d db redis
sleep 10
sudo docker compose exec db psql -U postgres -d company_lens -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;"

echo "=== Setting up backend ==="
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
deactivate

echo "=== Setting up frontend ==="
cd ../frontend
npm install
npm run build

echo "=== Setup complete! ==="
echo "Now create backend/.env and frontend/.env.local, then run start-app.sh"
