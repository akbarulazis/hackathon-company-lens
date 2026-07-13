# AWS Deployment Guide — Company Lens

Region: **ap-southeast-3 (Jakarta)** — WAJIB

## Architecture

```
Internet → ALB (Application Load Balancer)
              ├── /api/* → ECS Backend (FastAPI + ARQ Worker)
              └── /* → ECS Frontend (Next.js)
              
Backend → RDS PostgreSQL (pgvector)
       → ElastiCache Redis
```

## Step-by-Step Deployment

### Prerequisites
- AWS CLI installed and configured with your IAM credentials
- Docker installed locally
- AWS account activated (region: ap-southeast-3)

---

### Step 1: Create ECR Repositories

```bash
aws ecr create-repository --repository-name company-lens-backend --region ap-southeast-3
aws ecr create-repository --repository-name company-lens-frontend --region ap-southeast-3
```

### Step 2: Build & Push Docker Images

```bash
# Login to ECR
aws ecr get-login-password --region ap-southeast-3 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.ap-southeast-3.amazonaws.com

# Build backend
docker build -f Dockerfile.backend -t company-lens-backend .
docker tag company-lens-backend:latest <ACCOUNT_ID>.dkr.ecr.ap-southeast-3.amazonaws.com/company-lens-backend:latest
docker push <ACCOUNT_ID>.dkr.ecr.ap-southeast-3.amazonaws.com/company-lens-backend:latest

# Build frontend
docker build -f Dockerfile.frontend -t company-lens-frontend .
docker tag company-lens-frontend:latest <ACCOUNT_ID>.dkr.ecr.ap-southeast-3.amazonaws.com/company-lens-frontend:latest
docker push <ACCOUNT_ID>.dkr.ecr.ap-southeast-3.amazonaws.com/company-lens-frontend:latest
```

### Step 3: Create RDS PostgreSQL (with pgvector)

Via AWS Console (ap-southeast-3):
1. RDS → Create Database
2. Engine: **PostgreSQL 16**
3. Template: **Free tier** (or Dev/Test)
4. Instance: `db.t3.micro` or `db.t3.small`
5. DB name: `company_lens`
6. Master username: `postgres`
7. Master password: (save this!)
8. VPC: Default VPC
9. Public access: **Yes** (for initial setup, can restrict later)
10. Create

After creation, enable pgvector:
```sql
-- Connect via psql or pgAdmin
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Step 4: Create ElastiCache Redis

1. ElastiCache → Create
2. Engine: **Redis OSS**
3. Node type: `cache.t3.micro`
4. Number of replicas: 0
5. VPC: Same as RDS
6. Create

Note the **Primary endpoint** (e.g., `company-lens-redis.xxxxx.apse3.cache.amazonaws.com:6379`)

### Step 5: Create ECS Cluster

```bash
aws ecs create-cluster --cluster-name company-lens --region ap-southeast-3
```

### Step 6: Create Task Definitions

Create `task-backend.json`:
```json
{
  "family": "company-lens-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "<ACCOUNT_ID>.dkr.ecr.ap-southeast-3.amazonaws.com/company-lens-backend:latest",
      "portMappings": [{"containerPort": 8000}],
      "environment": [
        {"name": "SECRET_KEY", "value": "your-production-secret-key-here"},
        {"name": "OPENAI_API_KEY", "value": "sk-your-key"},
        {"name": "TAVILY_API_KEY", "value": "tvly-your-key"},
        {"name": "DATABASE_URL", "value": "postgresql://postgres:PASSWORD@RDS_ENDPOINT:5432/company_lens"},
        {"name": "REDIS_URL", "value": "redis://REDIS_ENDPOINT:6379/0"},
        {"name": "ENVIRONMENT", "value": "production"},
        {"name": "DEBUG", "value": "false"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/company-lens-backend",
          "awslogs-region": "ap-southeast-3",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

Register:
```bash
aws ecs register-task-definition --cli-input-json file://task-backend.json --region ap-southeast-3
```

### Step 7: Create ALB + Target Groups

Via Console:
1. EC2 → Load Balancers → Create ALB
2. Name: `company-lens-alb`
3. Internet-facing, IPv4
4. VPC: Default, select all subnets
5. Security group: Allow HTTP (80) and HTTPS (443)
6. Listeners: HTTP:80
7. Target group: Create new → IP type, port 8000, health check `/api/docs`

### Step 8: Create ECS Services

```bash
# Backend service
aws ecs create-service \
  --cluster company-lens \
  --service-name backend \
  --task-definition company-lens-backend \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:...,containerName=backend,containerPort=8000" \
  --region ap-southeast-3
```

### Step 9: Run Migrations

```bash
# One-time task to run migrations
aws ecs run-task \
  --cluster company-lens \
  --task-definition company-lens-backend \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"backend","command":["alembic","upgrade","head"]}]}' \
  --region ap-southeast-3
```

---

## Simpler Alternative: EC2 (Recommended for Hackathon)

If ECS is too complex, use a single **EC2 instance** with Docker Compose:

### Quick EC2 Deploy

```bash
# 1. Launch EC2 (t3.small, Ubuntu 22.04, ap-southeast-3)
# 2. SSH in and install Docker
sudo apt update && sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu

# 3. Clone your repo
git clone https://github.com/akbarulazis/hackathon-company-lens.git
cd hackathon-company-lens

# 4. Create production .env
cat > backend/.env << 'EOF'
SECRET_KEY=your-production-secret-32chars
OPENAI_API_KEY=sk-your-key
TAVILY_API_KEY=tvly-your-key
DATABASE_URL=postgresql://postgres:postgres@db:5432/company_lens
REDIS_URL=redis://redis:6379/0
ENVIRONMENT=production
DEBUG=false
EOF

# 5. Create production docker-compose
cat > docker-compose.prod.yml << 'EOF'
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: company_lens
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  redis:
    image: redis:7-alpine
    restart: always

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    env_file: backend/.env
    depends_on: [db, redis]
    ports:
      - "8000:8000"
    restart: always

  worker:
    build:
      context: .
      dockerfile: Dockerfile.backend
    command: arq app.jobs.settings.WorkerSettings
    env_file: backend/.env
    depends_on: [db, redis]
    restart: always

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    environment:
      - BACKEND_URL=http://backend:8000
    ports:
      - "80:3000"
    depends_on: [backend]
    restart: always

volumes:
  postgres_data:
EOF

# 6. Build and run
docker compose -f docker-compose.prod.yml up -d --build

# 7. Run migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# 8. Enable pgvector
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d company_lens -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

Your app is now at `http://<EC2-PUBLIC-IP>` !

### EC2 Security Group
- Inbound: SSH (22), HTTP (80), HTTPS (443)
- Outbound: All traffic

### EC2 Instance Type Recommendation
- **t3.small** (2 vCPU, 2GB RAM) — good for demo, ~$0.02/hr
- **t3.medium** (2 vCPU, 4GB RAM) — better for multiple concurrent users

---

## Cost Estimate (within $1000 budget)

| Service | Monthly Cost |
|---------|-------------|
| EC2 t3.small (24/7) | ~$15 |
| RDS db.t3.micro (if using managed) | ~$15 |
| ElastiCache (if using managed) | ~$12 |
| ECR storage | ~$1 |
| ALB (if using) | ~$16 |
| **Total (EC2 simple)** | **~$15/month** |
| **Total (full managed)** | **~$60/month** |

With $1000 credit, you have plenty of runway.
