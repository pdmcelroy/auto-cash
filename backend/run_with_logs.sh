#!/bin/bash
# Run backend with logs visible and saved to file

cd "$(dirname "$0")"
source venv/bin/activate

# Create logs directory if it doesn't exist
mkdir -p logs

# Run uvicorn with logs going to both terminal and file
uvicorn app.main:app --reload --port 8000 --log-level info 2>&1 | tee logs/backend.log

