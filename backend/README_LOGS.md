# Viewing Backend Logs

## Option 1: Run in Foreground (See logs in terminal)
Stop the current background process and run:
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```
This will show all logs directly in your terminal.

## Option 2: Run with Log File
Use the provided script to save logs to a file:
```bash
cd backend
./run_with_logs.sh
```
Then in another terminal, tail the log file:
```bash
tail -f backend/logs/backend.log
```

## Option 3: Check Current Process Output
If the backend is running in the background, you can:
1. Find the process: `ps aux | grep uvicorn`
2. Check if there's a log file: `ls -la backend/logs/`
3. Or restart it in foreground to see logs

## Option 4: Add Python Logging
The backend uses Python's logging. You can add more detailed logging by:
- Setting log level: `uvicorn app.main:app --log-level debug`
- Adding logging configuration in `app/main.py`

## Quick Check Current Status
```bash
# Check if backend is running
curl http://localhost:8000/health

# Check environment variables
curl http://localhost:8000/env-check
```


