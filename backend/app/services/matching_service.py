"""
Invoice Matching Service
Scores and ranks NetSuite invoices based on OCR extracted data
Falls back to CSV file if NetSuite is unavailable
"""
import logging
from typing import List, Dict, Any, Optional
from app.models.schemas import InvoiceMatch, OCRResult
from app.services.netsuite_service import NetSuiteService
from app.services.csv_invoice_service import CSVInvoiceService
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class MatchingService:
    """Service for matching OCR results to NetSuite invoices with CSV fallback"""
    
    def __init__(self, use_netsuite: bool = False):
        """
        Initialize matching service
        
        Args:
            use_netsuite: If False, skip NetSuite and use CSV only (default: False)
        """
        # Initialize CSV service first (primary for now)
        self.csv_service = None
        try:
            self.csv_service = CSVInvoiceService()
            logger.info("CSV invoice service initialized successfully")
        except Exception as e:
            logger.error(f"CSV service initialization failed: {e}")
            raise
        
        # Try to initialize NetSuite service only if requested
        self.netsuite = None
        if use_netsuite:
            try:
                self.netsuite = NetSuiteService()
                logger.info("NetSuite service initialized successfully")
            except Exception as e:
                logger.warning(f"NetSuite service initialization failed: {e}. Will use CSV only.")
        else:
            logger.info("NetSuite service disabled - using CSV only")
    
    def _search_invoices_by_number(self, invoice_number: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search invoices by number, using CSV (or NetSuite if enabled)"""
        # Try NetSuite first if enabled
        if self.netsuite:
            try:
                results = self.netsuite.search_invoices_by_number(invoice_number, limit=limit)
                if results:
                    logger.info(f"Found {len(results)} invoices in NetSuite for {invoice_number}")
                    return results
            except Exception as e:
                logger.warning(f"NetSuite search failed: {e}. Falling back to CSV.")
        
        # Use CSV (primary or fallback)
        if self.csv_service:
            try:
                results = self.csv_service.search_invoices_by_number(invoice_number, limit=limit)
                if results:
                    logger.info(f"Found {len(results)} invoices in CSV for {invoice_number}")
                    return results
            except Exception as e:
                logger.error(f"CSV search failed: {e}")
        
        return []
    
    def _search_invoices_by_customer(self, customer_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search invoices by customer, using CSV (or NetSuite if enabled)"""
        # Try NetSuite first if enabled
        if self.netsuite:
            try:
                results = self.netsuite.search_invoices_by_customer(customer_name, limit=limit)
                if results:
                    logger.info(f"Found {len(results)} invoices in NetSuite for customer {customer_name}")
                    return results
            except Exception as e:
                logger.warning(f"NetSuite search failed: {e}. Falling back to CSV.")
        
        # Use CSV (primary or fallback)
        if self.csv_service:
            try:
                results = self.csv_service.search_invoices_by_customer(customer_name, limit=limit)
                if results:
                    logger.info(f"Found {len(results)} invoices in CSV for customer {customer_name}")
                    return results
            except Exception as e:
                logger.error(f"CSV search failed: {e}")
        
        return []
    
    def _search_invoices_by_amount(self, amount: float, tolerance: float = 0.01, limit: int = 20) -> List[Dict[str, Any]]:
        """Search invoices by amount, using CSV (or NetSuite if enabled)"""
        # Try NetSuite first if enabled
        if self.netsuite:
            try:
                results = self.netsuite.search_invoices_by_amount(amount, tolerance=tolerance, limit=limit)
                if results:
                    logger.info(f"Found {len(results)} invoices in NetSuite for amount ${amount:.2f}")
                    return results
            except Exception as e:
                logger.warning(f"NetSuite search failed: {e}. Falling back to CSV.")
        
        # Use CSV (primary or fallback)
        if self.csv_service:
            try:
                results = self.csv_service.search_invoices_by_amount(amount, tolerance=tolerance, limit=limit)
                if results:
                    logger.info(f"Found {len(results)} invoices in CSV for amount ${amount:.2f}")
                    return results
            except Exception as e:
                logger.error(f"CSV search failed: {e}")
        
        return []
    
    def find_matches(self, ocr_result: OCRResult, max_results: int = 10) -> List[InvoiceMatch]:
        """Find and score matching invoices from NetSuite"""
        all_matches = {}
        
        # Primary: Search by invoice number (exact match)
        if ocr_result.invoice_numbers:
            for inv_num in ocr_result.invoice_numbers:
                invoices = self._search_invoices_by_number(inv_num, limit=20)
                for invoice in invoices:
                    invoice_id = invoice["invoice_id"]
                    if invoice_id not in all_matches:
                        all_matches[invoice_id] = invoice
                        all_matches[invoice_id]["match_score"] = 0.0
                        all_matches[invoice_id]["match_reasons"] = []
                    
                    # High score for exact invoice number match
                    if invoice["invoice_number"].upper() == inv_num.upper():
                        all_matches[invoice_id]["match_score"] += 100.0
                        all_matches[invoice_id]["match_reasons"].append(f"Exact invoice number match: {inv_num}")
                        
                        # BONUS: If amount also matches, give very high score
                        if ocr_result.amount and invoice.get("amount"):
                            amount_diff = abs(ocr_result.amount - invoice["amount"])
                            if amount_diff < 0.01:  # Exact amount match
                                all_matches[invoice_id]["match_score"] += 150.0  # Big bonus for both matching
                                all_matches[invoice_id]["match_reasons"].append(f"Exact amount match: ${invoice['amount']:.2f}")
                            elif amount_diff < 1.0:  # Within $1
                                all_matches[invoice_id]["match_score"] += 100.0
                                all_matches[invoice_id]["match_reasons"].append(f"Amount match (within $1): ${invoice['amount']:.2f}")
                            elif amount_diff < 10.0:  # Within $10
                                all_matches[invoice_id]["match_score"] += 50.0
                                all_matches[invoice_id]["match_reasons"].append(f"Amount match (within $10): ${invoice['amount']:.2f}")
                    elif inv_num.upper() in invoice["invoice_number"].upper() or invoice["invoice_number"].upper() in inv_num.upper():
                        # Partial match - only give points if amount also matches reasonably
                        if ocr_result.amount and invoice.get("amount"):
                            amount_diff = abs(ocr_result.amount - invoice["amount"])
                            if amount_diff < 0.01:  # Exact amount match
                                all_matches[invoice_id]["match_score"] += 80.0
                                all_matches[invoice_id]["match_reasons"].append(f"Partial invoice number match: {inv_num}")
                                all_matches[invoice_id]["match_reasons"].append(f"Exact amount match: ${invoice['amount']:.2f}")
                            elif amount_diff < 10.0:  # Within $10
                                all_matches[invoice_id]["match_score"] += 50.0
                                all_matches[invoice_id]["match_reasons"].append(f"Partial invoice number match: {inv_num}")
                                all_matches[invoice_id]["match_reasons"].append(f"Amount match (within $10): ${invoice['amount']:.2f}")
                            else:
                                # Partial invoice match but amount doesn't match - give very low score
                                all_matches[invoice_id]["match_score"] += 20.0
                                all_matches[invoice_id]["match_reasons"].append(f"Partial invoice number match: {inv_num} (amount mismatch: ${amount_diff:.2f})")
                        else:
                            # No amount to compare - give low score for partial match only
                            all_matches[invoice_id]["match_score"] += 30.0
                            all_matches[invoice_id]["match_reasons"].append(f"Partial invoice number match: {inv_num} (no amount to verify)")
        
        # Secondary: Search by customer name + amount
        if ocr_result.customer_name or ocr_result.payor_name:
            customer_name = ocr_result.customer_name or ocr_result.payor_name
            if customer_name:
                invoices = self._search_invoices_by_customer(customer_name, limit=50)
                for invoice in invoices:
                    invoice_id = invoice["invoice_id"]
                    if invoice_id not in all_matches:
                        all_matches[invoice_id] = invoice
                        all_matches[invoice_id]["match_score"] = 0.0
                        all_matches[invoice_id]["match_reasons"] = []
                    
                    # Score based on customer name similarity
                    name_similarity = self._string_similarity(
                        customer_name.lower(),
                        invoice["customer_name"].lower()
                    )
                    
                    # Score based on amount match (if available)
                    amount_score = 0.0
                    if ocr_result.amount and invoice.get("amount"):
                        amount_diff = abs(ocr_result.amount - invoice["amount"])
                        if amount_diff < 0.01:  # Exact match
                            amount_score = 50.0
                        elif amount_diff < 1.0:  # Within $1
                            amount_score = 40.0
                        elif amount_diff < 10.0:  # Within $10
                            amount_score = 30.0
                        elif amount_diff < 100.0:  # Within $100
                            amount_score = 20.0
                    
                    combined_score = (name_similarity * 40.0) + amount_score
                    all_matches[invoice_id]["match_score"] += combined_score
                    
                    if name_similarity > 0.7:
                        all_matches[invoice_id]["match_reasons"].append(
                            f"Customer name match: {invoice['customer_name']} (similarity: {name_similarity:.2f})"
                        )
                    if amount_score > 0:
                        all_matches[invoice_id]["match_reasons"].append(
                            f"Amount match: ${invoice['amount']:.2f} (diff: ${amount_diff:.2f})"
                        )
        
        # Tertiary: Search by amount only (if no other strong matches)
        if ocr_result.amount and len(all_matches) < 5:
            invoices = self._search_invoices_by_amount(ocr_result.amount, tolerance=0.01, limit=20)
            for invoice in invoices:
                invoice_id = invoice["invoice_id"]
                if invoice_id not in all_matches:
                    all_matches[invoice_id] = invoice
                    all_matches[invoice_id]["match_score"] = 0.0
                    all_matches[invoice_id]["match_reasons"] = []
                
                # Lower score for amount-only match
                amount_score = 15.0
                all_matches[invoice_id]["match_score"] += amount_score
                all_matches[invoice_id]["match_reasons"].append(
                    f"Amount-only match: ${invoice['amount']:.2f}"
                )
        
        # Convert to InvoiceMatch objects and sort by score
        matches = []
        for invoice_id, invoice_data in all_matches.items():
            if invoice_data["match_score"] > 0:
                match = InvoiceMatch(
                    invoice_id=invoice_data["invoice_id"],
                    invoice_number=invoice_data["invoice_number"],
                    customer_name=invoice_data["customer_name"],
                    amount=invoice_data.get("amount", 0.0),
                    due_date=invoice_data.get("due_date"),
                    subsidiary=invoice_data.get("subsidiary"),
                    match_score=invoice_data["match_score"],
                    match_reasons=invoice_data["match_reasons"]
                )
                matches.append(match)
        
        # Sort by score (descending) and return top results
        matches.sort(key=lambda x: x.match_score, reverse=True)
        return matches[:max_results]
    
    def _string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (0.0 to 1.0)"""
        return SequenceMatcher(None, str1, str2).ratio()

