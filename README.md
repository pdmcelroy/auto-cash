# Cash Application Automation System

A human-in-the-loop system for automating cash application in NetSuite. Users upload check images and remittance PDFs through a React UI, the system extracts data via OCR using Vision Language Models, searches NetSuite for matching invoices, and presents suggestions for review.

## Features

- **File Upload**: Upload check images and/or remittance PDFs via drag-and-drop interface
- **OCR Processing**: Extract text from documents using GPT-4 Vision (handles both printed and handwritten text)
- **NetSuite Integration**: Search for matching invoices in NetSuite based on extracted data
- **Smart Matching**: Score and rank invoice matches by invoice number, customer name, and amount
- **Human Review**: Review extracted data and select the correct invoice match

## Architecture

### Backend (Python/FastAPI)
- FastAPI REST API with file upload endpoints
- OCR service using OpenAI GPT-4 Vision for text extraction
- NetSuite service wrapper (reuses `netsuite-test` repo client)
- Invoice matching service with scoring logic

### Frontend (React)
- React with Vite
- File upload components with drag-and-drop
- Display OCR results and NetSuite invoice suggestions
- Human review interface

## Prerequisites

- Python 3.8+
- Node.js 16+
- NetSuite account with REST API access (configured in `netsuite-test` repo)
- OpenAI API key for OCR processing
- Tesseract OCR (for PDF processing via pdf2image)

## Setup

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
   - Copy `.env` from `netsuite-test` repo or create a new one
   - Add OpenAI API key:
     ```
     OPENAI_API_KEY=your_openai_api_key_here
     ```
   - Ensure NetSuite credentials are set (from `netsuite-test` repo)

5. Run the backend server:
```bash
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. (Optional) Create `.env` file for API URL:
```
VITE_API_BASE_URL=http://localhost:8000
```

4. Run the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173` (or the port Vite assigns).

## Usage

1. Start both backend and frontend servers
2. Open the frontend in your browser
3. Upload a check image and/or remittance PDF
4. Review the extracted data (OCR results)
5. Review the suggested invoice matches from NetSuite
6. Select the correct invoice match
7. Confirm the match (payment application feature coming soon)

## API Endpoints

### Upload Endpoints
- `POST /api/upload/check` - Upload check image
- `POST /api/upload/remittance` - Upload remittance PDF
- `POST /api/upload/both` - Upload both files together

### Invoice Endpoints
- `GET /api/invoices/search` - Search invoices (query params: `invoice_number`, `customer_name`, `amount`)
- `GET /api/invoices/{invoice_id}` - Get specific invoice

## Configuration

### NetSuite Integration
The system reuses the NetSuite client from the `netsuite-test` repo. Ensure:
- NetSuite credentials are configured in `.env` (or symlink from `netsuite-test`)
- REST Web Services permissions are enabled in NetSuite
- Access token is active

### OCR Configuration
- Uses OpenAI GPT-4 Vision API
- Requires `OPENAI_API_KEY` environment variable
- Handles both printed and handwritten text

## File Structure

```
automated-cash-app/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── routes/
│   │   │   ├── upload.py        # File upload endpoints
│   │   │   └── invoices.py      # Invoice search endpoints
│   │   ├── services/
│   │   │   ├── ocr_service.py   # OCR processing
│   │   │   ├── netsuite_service.py  # NetSuite wrapper
│   │   │   └── matching_service.py  # Invoice matching logic
│   │   └── models/
│   │       └── schemas.py        # Pydantic models
│   ├── requirements.txt
│   └── .env                      # NetSuite config
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── FileUpload.jsx
│   │   │   ├── OCRResults.jsx
│   │   │   ├── InvoiceSuggestions.jsx
│   │   │   └── ReviewPanel.jsx
│   │   └── services/
│   │       └── api.js            # API client
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Current Limitations

- Payment application to NetSuite is not yet implemented (read-only for now)
- Matching logic is basic (can be enhanced with fuzzy matching, ML, etc.)
- No batch processing (one file at a time)
- No persistence of processed files or results

## Future Enhancements

- Implement payment application in NetSuite
- Batch processing for multiple files
- Database to store processing history
- Enhanced matching with ML models
- Email integration for automatic remittance processing
- Support for additional file formats

## Troubleshooting

### Backend Issues
- **NetSuite authentication fails**: Check credentials in `.env` and ensure access token is active
- **OCR fails**: Verify `OPENAI_API_KEY` is set and valid
- **PDF processing fails**: Ensure `pdf2image` dependencies are installed (requires poppler)

### Frontend Issues
- **API connection fails**: Verify backend is running on port 8000 and CORS is configured
- **File upload fails**: Check file size limits and file type restrictions

## License

This project is provided as-is for internal use.

