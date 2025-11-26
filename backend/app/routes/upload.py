"""
File upload routes for remittance PDFs and lockbox checks PDFs
"""
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import time
from app.services.ocr_service import OCRService
from app.services.matching_service import MatchingService
from app.models.schemas import OCRResult, InvoiceSearchResponse, BatchUploadResponse, PDFUploadResponse, CheckGroup
from typing import Optional, List

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
        # Use SuiteQL as primary, CSV as fallback
        _matching_service = MatchingService(use_suiteql=True)
    return _matching_service


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


@router.post("/batch", response_model=BatchUploadResponse)
async def upload_batch(
    files: List[UploadFile] = File(...)
):
    """Upload and process multiple remittance PDFs separately"""
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="At least one file must be provided")
    
    try:
        start_time = time.time()
        results = []
        
        ocr_service = get_ocr_service()
        matching_service = get_matching_service()
        
        # Process each file separately
        for file in files:
            try:
                file_start_time = time.time()
                file_bytes = await file.read()
                
                # Only process PDFs
                if file.content_type != "application/pdf":
                    logger.warning(f"Skipping file {file.filename}: must be a PDF (got {file.content_type})")
                    continue
                
                # Process as remittance PDF
                ocr_data = ocr_service.process_remittance_pdf(file_bytes)
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
                
                # Find matching invoices for this file
                matches = matching_service.find_matches(ocr_result, max_results=10)
                
                file_processing_time = time.time() - file_start_time
                
                results.append(InvoiceSearchResponse(
                    ocr_result=ocr_result,
                    matches=matches,
                    processing_time=file_processing_time
                ))
                
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {e}", exc_info=True)
                # Continue processing other files even if one fails
                continue
        
        total_processing_time = time.time() - start_time
        
        if not results:
            raise HTTPException(status_code=500, detail="Failed to process any files")
        
        return BatchUploadResponse(
            results=results,
            total_processing_time=total_processing_time,
            total_files=len(results)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing batch: {str(e)}")


@router.post("/pdf", response_model=PDFUploadResponse)
async def upload_pdf(
    file: UploadFile = File(...)
):
    """Upload and process a lockbox checks PDF, grouping pages by check number"""
    if not file.content_type or file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        start_time = time.time()
        
        logger.info(f"Starting PDF upload processing for file: {file.filename}")
        
        # Read file bytes
        file_bytes = await file.read()
        logger.info(f"PDF file read: {len(file_bytes)} bytes")
        
        # Process PDF and group by checks
        ocr_service = get_ocr_service()
        logger.info("Processing PDF pages and grouping by check...")
        check_groups_data = ocr_service.process_pdf_by_checks(file_bytes)
        logger.info(f"PDF processing complete. Found {len(check_groups_data)} check group(s)")
        
        matching_service = get_matching_service()
        check_groups = []
        
        # Process each check group
        for idx, group_data in enumerate(check_groups_data):
            group_start_time = time.time()
            check_num = group_data.get("check_number") or f"Unknown-{idx+1}"
            logger.info(f"Processing check group {idx + 1}/{len(check_groups_data)}: Check #{check_num}")
            
            # Convert to OCRResult
            ocr_result = OCRResult(
                check_number=group_data.get("check_number"),
                amount=group_data.get("amount"),
                date=group_data.get("date"),
                payor_name=group_data.get("payor_name"),
                payee_name=group_data.get("payee_name"),
                invoice_numbers=group_data.get("invoice_numbers", []),
                customer_name=group_data.get("customer_name") or group_data.get("payor_name"),
                raw_text=group_data.get("raw_text", ""),
                confidence=1.0,
                extracted_fields=group_data
            )
            
            # Find matching invoices
            logger.info(f"Finding invoice matches for check #{check_num}...")
            matches = matching_service.find_matches(ocr_result, max_results=10)
            logger.info(f"Found {len(matches)} matches for check #{check_num}")
            
            group_processing_time = time.time() - group_start_time
            
            check_groups.append(CheckGroup(
                check_number=group_data.get("check_number"),
                pages=group_data.get("pages", []),
                ocr_result=ocr_result,
                matches=matches,
                processing_time=group_processing_time
            ))
        
        total_processing_time = time.time() - start_time
        
        # Count total pages
        total_pages = sum(len(group.pages) for group in check_groups)
        
        logger.info(f"PDF processing complete. Total time: {total_processing_time:.2f}s, {len(check_groups)} check(s), {total_pages} page(s)")
        
        return PDFUploadResponse(
            check_groups=check_groups,
            total_processing_time=total_processing_time,
            total_pages=total_pages
        )
    
    except Exception as e:
        logger.error(f"Error processing PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

