#!/bin/bash
# Start script for the cash application backend

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Please create one with your NetSuite and OpenAI credentials."
    echo "See README.md for details."
fi

# Start the FastAPI server
uvicorn app.main:app --reload --port 8000

