"""
FastAPI application for cash application automation
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler('logs/backend.log') if Path('logs').exists() else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables before importing routes
# Resolve paths relative to this file
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent  # backend/
_project_root = _backend_dir.parent  # project root

env_paths = [
    _backend_dir / ".env",
    _project_root / ".env",
]

# Load .env file
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        print(f"Loaded .env from: {env_path}")
        break
else:
    # Fallback to default behavior
    load_dotenv(override=True)
    print("Warning: No .env file found, using default load_dotenv()")

from app.routes import upload, invoices

app = FastAPI(
    title="Cash Application API",
    description="API for automating cash application in NetSuite",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router)
app.include_router(invoices.router)


@app.get("/")
async def root():
    return {
        "message": "Cash Application API",
        "version": "1.0.0",
        "endpoints": {
            "upload_remittance": "/api/upload/remittance",
            "upload_pdf": "/api/upload/pdf",
            "upload_batch": "/api/upload/batch",
            "search_invoices": "/api/invoices/search",
            "get_invoice": "/api/invoices/{invoice_id}"
        }
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/env-check")
async def env_check():
    """Check if environment variables are loaded (for debugging)"""
    import os
    return {
        "openai_api_key_set": bool(os.getenv("OPENAI_API_KEY")),
        "openai_api_key_length": len(os.getenv("OPENAI_API_KEY", "")),
        "netsuite_account_id": bool(os.getenv("NETSUITE_ACCOUNT_ID")),
        "cwd": os.getcwd(),
    }


@app.get("/logs")
async def get_logs(lines: int = 100):
    """Get recent backend logs"""
    log_file = Path("logs/backend.log")
    if log_file.exists():
        try:
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return {
                    "log_file": str(log_file),
                    "total_lines": len(all_lines),
                    "showing_last": len(recent_lines),
                    "logs": recent_lines
                }
        except Exception as e:
            return {"error": f"Could not read log file: {str(e)}"}
    else:
        return {
            "message": "Log file not found. Logs may be in the terminal where the backend was started.",
            "log_file": str(log_file),
            "exists": False
        }

