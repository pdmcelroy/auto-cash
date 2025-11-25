"""
File upload routes for check images and remittance PDFs
"""
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import time
from app.services.ocr_service import OCRService
from app.services.matching_service import MatchingService
from app.models.schemas import OCRResult, InvoiceSearchResponse
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["upload"])

# Lazy initialization to avoid errors at import time
_ocr_service = None
_matching_service = None

def get_ocr_service():
    global _ocr_service
    if _ocr_service is None:
        # Ensure environment is loaded before creating service
        import os
        from pathlib import Path
        from dotenv import load_dotenv
        
        # Try to load .env if not already loaded
        if not os.getenv("OPENAI_API_KEY"):
            backend_dir = Path(__file__).parent.parent.parent
            project_root = backend_dir.parent
            env_paths = [
                backend_dir / ".env",
                project_root / ".env",
            ]
            for env_path in env_paths:
                if env_path.exists():
                    load_dotenv(env_path, override=True)
                    break
        
        _ocr_service = OCRService()
    return _ocr_service

def get_matching_service():
    global _matching_service
    if _matching_service is None:
        # Use CSV only (skip NetSuite to avoid network errors)
        _matching_service = MatchingService(use_netsuite=False)
    return _matching_service


@router.post("/check", response_model=InvoiceSearchResponse)
async def upload_check(
    file: UploadFile = File(...)
):
    """Upload and process a check image"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        start_time = time.time()
        
        # Read file bytes
        file_bytes = await file.read()
        
        # Process with OCR
        try:
            logger.info("Getting OCR service...")
            ocr_service = get_ocr_service()
            logger.info("OCR service obtained successfully")
        except Exception as e:
            import os
            logger.error(f"Failed to get OCR service: {e}", exc_info=True)
            logger.error(f"OPENAI_API_KEY in env: {bool(os.getenv('OPENAI_API_KEY'))}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to initialize OCR service: {str(e)}"
            )
        
        ocr_data = ocr_service.process_check_image(file_bytes)
        
        # Convert to OCRResult
        ocr_result = OCRResult(
            check_number=ocr_data.get("check_number"),
            amount=ocr_data.get("amount"),
            date=ocr_data.get("date"),
            payor_name=ocr_data.get("payor_name"),
            payee_name=ocr_data.get("payee_name"),
            invoice_numbers=ocr_data.get("invoice_numbers", []),
            customer_name=ocr_data.get("payor_name"),  # Use payor as customer
            raw_text=ocr_data.get("raw_text", ""),
            confidence=1.0,  # VLM doesn't provide confidence scores
            extracted_fields=ocr_data
        )
        
        # Find matching invoices
        matching_service = get_matching_service()
        matches = matching_service.find_matches(ocr_result, max_results=10)
        
        processing_time = time.time() - start_time
        
        return InvoiceSearchResponse(
            ocr_result=ocr_result,
            matches=matches,
            processing_time=processing_time
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing check: {str(e)}")


@router.post("/remittance", response_model=InvoiceSearchResponse)
async def upload_remittance(
    file: UploadFile = File(...)
):
    """Upload and process a remittance PDF"""
    if not file.content_type or file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        start_time = time.time()
        
        # Read file bytes
        file_bytes = await file.read()
        
        # Process with OCR
        ocr_service = get_ocr_service()
        ocr_data = ocr_service.process_remittance_pdf(file_bytes)
        
        # Convert to OCRResult
        ocr_result = OCRResult(
            check_number=ocr_data.get("check_number"),
            amount=ocr_data.get("amount"),
            date=ocr_data.get("date"),
            payor_name=ocr_data.get("customer_name"),
            invoice_numbers=ocr_data.get("invoice_numbers", []),
            customer_name=ocr_data.get("customer_name"),
            raw_text=ocr_data.get("raw_text", ""),
            confidence=1.0,
            extracted_fields=ocr_data
        )
        
        # Find matching invoices
        matching_service = get_matching_service()
        matches = matching_service.find_matches(ocr_result, max_results=10)
        
        processing_time = time.time() - start_time
        
        return InvoiceSearchResponse(
            ocr_result=ocr_result,
            matches=matches,
            processing_time=processing_time
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing remittance: {str(e)}")


@router.post("/both", response_model=InvoiceSearchResponse)
async def upload_both(
    check: Optional[UploadFile] = File(None),
    remittance: Optional[UploadFile] = File(None)
):
    """Upload both check image and remittance PDF (combines data)"""
    if not check and not remittance:
        raise HTTPException(status_code=400, detail="At least one file (check or remittance) must be provided")
    
    try:
        start_time = time.time()
        
        # Combine OCR results from both files
        combined_ocr_data = {
            "check_number": None,
            "amount": None,
            "date": None,
            "payor_name": None,
            "payee_name": None,
            "invoice_numbers": [],
            "customer_name": None,
            "raw_text": ""
        }
        
        # Process check if provided
        if check:
            if not check.content_type or not check.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Check file must be an image")
            
            check_bytes = await check.read()
            ocr_service = get_ocr_service()
            check_data = ocr_service.process_check_image(check_bytes)
            
            # Merge check data
            combined_ocr_data["check_number"] = check_data.get("check_number") or combined_ocr_data["check_number"]
            combined_ocr_data["amount"] = check_data.get("amount") or combined_ocr_data["amount"]
            combined_ocr_data["date"] = check_data.get("date") or combined_ocr_data["date"]
            combined_ocr_data["payor_name"] = check_data.get("payor_name") or combined_ocr_data["payor_name"]
            combined_ocr_data["payee_name"] = check_data.get("payee_name") or combined_ocr_data["payee_name"]
            combined_ocr_data["invoice_numbers"].extend(check_data.get("invoice_numbers", []))
            combined_ocr_data["raw_text"] += f"\n\n--- Check Image ---\n{check_data.get('raw_text', '')}"
        
        # Process remittance if provided
        if remittance:
            if remittance.content_type != "application/pdf":
                raise HTTPException(status_code=400, detail="Remittance file must be a PDF")
            
            remittance_bytes = await remittance.read()
            ocr_service = get_ocr_service()
            remittance_data = ocr_service.process_remittance_pdf(remittance_bytes)
            
            # Merge remittance data (remittance takes precedence for some fields)
            combined_ocr_data["invoice_numbers"].extend(remittance_data.get("invoice_numbers", []))
            combined_ocr_data["amount"] = remittance_data.get("amount") or combined_ocr_data["amount"]
            combined_ocr_data["customer_name"] = remittance_data.get("customer_name") or combined_ocr_data["customer_name"]
            combined_ocr_data["check_number"] = remittance_data.get("check_number") or combined_ocr_data["check_number"]
            combined_ocr_data["date"] = remittance_data.get("date") or combined_ocr_data["date"]
            combined_ocr_data["raw_text"] += f"\n\n--- Remittance PDF ---\n{remittance_data.get('raw_text', '')}"
        
        # Remove duplicate invoice numbers
        combined_ocr_data["invoice_numbers"] = list(set(combined_ocr_data["invoice_numbers"]))
        
        # Convert to OCRResult
        ocr_result = OCRResult(
            check_number=combined_ocr_data["check_number"],
            amount=combined_ocr_data["amount"],
            date=combined_ocr_data["date"],
            payor_name=combined_ocr_data["payor_name"] or combined_ocr_data["customer_name"],
            payee_name=combined_ocr_data["payee_name"],
            invoice_numbers=combined_ocr_data["invoice_numbers"],
            customer_name=combined_ocr_data["customer_name"] or combined_ocr_data["payor_name"],
            raw_text=combined_ocr_data["raw_text"],
            confidence=1.0,
            extracted_fields=combined_ocr_data
        )
        
        # Find matching invoices
        matching_service = get_matching_service()
        matches = matching_service.find_matches(ocr_result, max_results=10)
        
        processing_time = time.time() - start_time
        
        return InvoiceSearchResponse(
            ocr_result=ocr_result,
            matches=matches,
            processing_time=processing_time
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing files: {str(e)}")

