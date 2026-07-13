#!/bin/bash
# Start all Company Lens services
cd /home/ubuntu/app

# Start backend
cd backend
pm2 start --name backend --interpreter bash -- -c "source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000"

# Start worker
pm2 start --name worker --interpreter bash -- -c "source .venv/bin/activate && arq app.jobs.settings.WorkerSettings"

# Start frontend
cd ../frontend
pm2 start --name frontend -- npm start

# Save
pm2 save

echo "=== All services started ==="
echo "Frontend: http://$(curl -s ifconfig.me):3000"
echo "Backend:  http://$(curl -s ifconfig.me):8000/api/docs"
