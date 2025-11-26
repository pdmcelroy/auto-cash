from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class OCRResult(BaseModel):
    """Extracted data from OCR processing"""
    check_number: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[str] = None
    payor_name: Optional[str] = None
    payee_name: Optional[str] = None
    invoice_numbers: List[str] = []
    customer_name: Optional[str] = None
    raw_text: str = ""
    confidence: float = 0.0
    extracted_fields: Dict[str, Any] = {}


class InvoiceMatch(BaseModel):
    """NetSuite invoice match result"""
    invoice_id: str
    invoice_number: str
    customer_name: str
    amount: float
    due_date: Optional[str] = None
    subsidiary: Optional[str] = None
    match_score: float
    match_reasons: List[str] = []


class InvoiceSearchResponse(BaseModel):
    """Response containing OCR results and invoice matches"""
    ocr_result: OCRResult
    matches: List[InvoiceMatch]
    processing_time: float


class FileUploadResponse(BaseModel):
    """Response after file upload"""
    file_id: str
    filename: str
    file_type: str
    message: str


class BatchUploadResponse(BaseModel):
    """Response containing multiple processed checks/remittances"""
    results: List[InvoiceSearchResponse]  # One result per file
    total_processing_time: float
    total_files: int


class CheckGroup(BaseModel):
    """Grouped pages for a single check"""
    check_number: Optional[str]
    pages: List[int]  # Page indices (0-based)
    ocr_result: OCRResult
    matches: List[InvoiceMatch]
    processing_time: float


class PDFUploadResponse(BaseModel):
    """Response containing processed PDF with pages grouped by check"""
    check_groups: List[CheckGroup]
    total_processing_time: float
    total_pages: int

