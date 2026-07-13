# Deploy Company Lens to AWS (ap-southeast-3 Jakarta)

## Architecture

```
                    ┌─────────────────┐
                    │   CloudFront    │ (optional CDN)
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  EC2 Instance   │ (t3.small)
                    │  ┌───────────┐  │
                    │  │  Nginx    │  │ → Frontend (Next.js) + Backend (FastAPI)
                    │  │  Backend  │  │
                    │  │  Worker   │  │
                    │  │  Frontend │  │
                    │  └───────────┘  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼──────┐  ┌───▼───┐  ┌──────▼─────┐
    │ RDS PostgreSQL │  │ Redis │  │    S3      │
    │ (db.t3.micro)  │  │(cache)│  │ (uploads)  │
    └────────────────┘  └───────┘  └────────────┘
```

## Estimated Cost (per month)

| Service | Spec | Cost |
|---------|------|------|
| EC2 | t3.small (2 vCPU, 2GB) | ~$15/mo |
| RDS PostgreSQL | db.t3.micro (1 vCPU, 1GB) | ~$12/mo |
| ElastiCache Redis | cache.t3.micro | ~$12/mo |
| EBS | 20GB gp3 | ~$2/mo |
| Data Transfer | ~10GB | ~$1/mo |
| **Total** | | **~$42/mo** |

Well within your $1,000 budget for the hackathon period.

---

## Step 1: Configure AWS CLI

```bash
aws configure
```

Enter:
- AWS Access Key ID: (from your IAM user)
- AWS Secret Access Key: (from your IAM user)
- Default region: `ap-southeast-3`
- Default output: `json`

---

## Step 2: Create Security Group

```bash
# Create VPC security group
aws ec2 create-security-group \
  --group-name company-lens-sg \
  --description "Company Lens hackathon" \
  --region ap-southeast-3

# Allow SSH, HTTP, HTTPS
aws ec2 authorize-security-group-ingress --group-name company-lens-sg --protocol tcp --port 22 --cidr 0.0.0.0/0 --region ap-southeast-3
aws ec2 authorize-security-group-ingress --group-name company-lens-sg --protocol tcp --port 80 --cidr 0.0.0.0/0 --region ap-southeast-3
aws ec2 authorize-security-group-ingress --group-name company-lens-sg --protocol tcp --port 443 --cidr 0.0.0.0/0 --region ap-southeast-3
aws ec2 authorize-security-group-ingress --group-name company-lens-sg --protocol tcp --port 3000 --cidr 0.0.0.0/0 --region ap-southeast-3
aws ec2 authorize-security-group-ingress --group-name company-lens-sg --protocol tcp --port 8000 --cidr 0.0.0.0/0 --region ap-southeast-3
```

---

## Step 3: Create Key Pair

```bash
aws ec2 create-key-pair \
  --key-name company-lens-key \
  --query 'KeyMaterial' \
  --output text \
  --region ap-southeast-3 > ~/.ssh/company-lens-key.pem

chmod 400 ~/.ssh/company-lens-key.pem
```

---

## Step 4: Launch EC2 Instance

```bash
# Find latest Ubuntu 22.04 AMI in Jakarta
AMI_ID=$(aws ec2 describe-images \
  --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
  --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
  --output text \
  --region ap-southeast-3)

echo "AMI: $AMI_ID"

# Launch instance
aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type t3.small \
  --key-name company-lens-key \
  --security-groups company-lens-sg \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=company-lens}]' \
  --region ap-southeast-3

# Get public IP
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=company-lens" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region ap-southeast-3
```

---

## Step 5: SSH into the Instance and Set Up

```bash
# SSH in (replace YOUR_IP with the public IP from step 4)
ssh -i ~/.ssh/company-lens-key.pem ubuntu@YOUR_IP
```

Once inside the EC2 instance, run:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu
newgrp docker

# Install Docker Compose
sudo apt install -y docker-compose-plugin

# Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip

# Clone the repo
git clone https://github.com/akbarulazis/hackathon-company-lens.git
cd hackathon-company-lens

# Start PostgreSQL + Redis
docker compose up -d db redis

# Wait for DB to be ready
sleep 10

# Enable extensions
docker compose exec db psql -U postgres -d company_lens -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# Setup backend
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Create .env file (edit with your real keys)
cat > .env << 'EOF'
SECRET_KEY=your-production-secret-key-change-this
OPENAI_API_KEY=sk-your-real-openai-key
TAVILY_API_KEY=tvly-your-real-tavily-key
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/company_lens
REDIS_URL=redis://localhost:6379/0
ENVIRONMENT=production
DEBUG=false
EOF

# Run migrations
alembic upgrade head

# Setup frontend
cd ../frontend
npm install
cat > .env.local << 'EOF'
NEXT_PUBLIC_API_URL=/api
NEXT_PUBLIC_WS_URL=ws://YOUR_IP:8000
EOF
npm run build

# Start everything with PM2 (process manager)
sudo npm install -g pm2

# Start backend
cd ../backend
pm2 start "source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000" --name backend

# Start worker
pm2 start "source .venv/bin/activate && arq app.jobs.settings.WorkerSettings" --name worker

# Start frontend
cd ../frontend
pm2 start "npm start" --name frontend

# Save PM2 config
pm2 save
pm2 startup
```

---

## Step 6: Access Your App

- Frontend: `http://YOUR_IP:3000`
- API Docs: `http://YOUR_IP:8000/api/docs`

---

## Optional: Nginx Reverse Proxy (single port 80)

```bash
sudo apt install -y nginx

sudo cat > /etc/nginx/sites-available/company-lens << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/company-lens /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
```

Now access at: `http://YOUR_IP` (port 80)

---

## Troubleshooting

- **Can't connect**: Check security group allows your port
- **Backend won't start**: Check .env has all required keys
- **DB error**: Make sure Docker containers are running: `docker ps`
- **Kill stuck process**: `pm2 delete all` then restart
- **See logs**: `pm2 logs backend` or `pm2 logs worker`
