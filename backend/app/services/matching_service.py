"""
Invoice Matching Service
Scores and ranks NetSuite invoices based on OCR extracted data
Uses SuiteQL for primary invoice search, falls back to CSV if unavailable
Supports multi-invoice matching where invoice sums equal check amounts
"""
import logging
from typing import List, Dict, Any, Optional
from app.models.schemas import InvoiceMatch, OCRResult
from app.services.suiteql_invoice_service import SuiteQLInvoiceService
from app.services.csv_invoice_service import CSVInvoiceService
from difflib import SequenceMatcher
import itertools

logger = logging.getLogger(__name__)


class MatchingService:
    """Service for matching OCR results to NetSuite invoices using SuiteQL with CSV fallback"""
    
    def __init__(self, use_suiteql: bool = True):
        """
        Initialize matching service
        
        Args:
            use_suiteql: If True, use SuiteQL service (default: True). Falls back to CSV if SuiteQL fails.
        """
        # Initialize SuiteQL service as primary
        self.suiteql_service = None
        if use_suiteql:
            try:
                self.suiteql_service = SuiteQLInvoiceService()
                logger.info("SuiteQL invoice service initialized successfully")
            except Exception as e:
                logger.warning(f"SuiteQL service initialization failed: {e}. Will use CSV only.")
        
        # Initialize CSV service as fallback
        self.csv_service = None
        try:
            self.csv_service = CSVInvoiceService()
            logger.info("CSV invoice service initialized successfully (as fallback)")
        except Exception as e:
            logger.warning(f"CSV service initialization failed: {e}")
            if not self.suiteql_service:
                raise Exception("Both SuiteQL and CSV services failed to initialize")
    
    def _search_invoices_by_number(self, invoice_number: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search invoices by number, using SuiteQL (or CSV as fallback)"""
        # Try SuiteQL first if enabled
        if self.suiteql_service:
            try:
                results = self.suiteql_service.search_by_number(invoice_number, limit=limit)
                if results:
                    logger.info(f"Found {len(results)} invoices via SuiteQL for {invoice_number}")
                    return results
            except Exception as e:
                logger.warning(f"SuiteQL search failed: {e}. Falling back to CSV.")
        
        # Use CSV (fallback)
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
        """Search invoices by customer, using SuiteQL (or CSV as fallback)"""
        # Try SuiteQL first if enabled
        if self.suiteql_service:
            try:
                results = self.suiteql_service.search_by_customer(customer_name, limit=limit)
                if results:
                    logger.info(f"Found {len(results)} invoices via SuiteQL for customer {customer_name}")
                    return results
            except Exception as e:
                logger.warning(f"SuiteQL search failed: {e}. Falling back to CSV.")
        
        # Use CSV (fallback)
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
        """Search invoices by amount, using SuiteQL (or CSV as fallback)"""
        # Try SuiteQL first if enabled
        if self.suiteql_service:
            try:
                results = self.suiteql_service.search_by_amount(amount, tolerance=tolerance, limit=limit)
                if results:
                    logger.info(f"Found {len(results)} invoices via SuiteQL for amount ${amount:.2f}")
                    return results
            except Exception as e:
                logger.warning(f"SuiteQL search failed: {e}. Falling back to CSV.")
        
        # Use CSV (fallback)
        if self.csv_service:
            try:
                results = self.csv_service.search_invoices_by_amount(amount, tolerance=tolerance, limit=limit)
                if results:
                    logger.info(f"Found {len(results)} invoices in CSV for amount ${amount:.2f}")
                    return results
            except Exception as e:
                logger.error(f"CSV search failed: {e}")
        
        return []
    
    def _find_multi_invoice_matches(self, ocr_result: OCRResult, candidate_invoices: List[Dict[str, Any]], 
                                     tolerance: float = 0.01) -> List[Dict[str, Any]]:
        """
        Find combinations of invoices where the sum equals the check amount.
        Only returns matches if:
        - All invoice numbers from OCR are found in the combination
        - Customer matches (if customer name is available)
        
        Args:
            ocr_result: OCR result with check amount and invoice numbers
            candidate_invoices: List of candidate invoices to consider (should be invoices found via search)
            tolerance: Amount tolerance for matching (default: $0.01)
        
        Returns:
            List of multi-invoice match dictionaries with combined score and invoice IDs
        """
        if not ocr_result.amount or not candidate_invoices:
            return []
        
        # REQUIRE invoice numbers from OCR to be present
        if not ocr_result.invoice_numbers:
            logger.debug("Skipping multi-invoice matching: no invoice numbers found in OCR")
            return []
        
        target_amount = ocr_result.amount
        multi_matches = []
        
        # REQUIRE customer match if customer name is available
        filtered_invoices = candidate_invoices
        customer_match_required = bool(ocr_result.customer_name or ocr_result.payor_name)
        
        if customer_match_required:
            customer_name = (ocr_result.customer_name or ocr_result.payor_name).lower()
            filtered_invoices = [
                inv for inv in candidate_invoices
                if self._string_similarity(customer_name, inv.get("customer_name", "").lower()) > 0.7
            ]
            if not filtered_invoices:
                logger.debug(f"Skipping multi-invoice matching: no invoices match customer {customer_name}")
                return []
        
        # Limit to reasonable number of invoices to avoid combinatorial explosion
        if len(filtered_invoices) > 50:
            filtered_invoices = filtered_invoices[:50]
        
        # Normalize OCR invoice numbers for matching (remove common prefixes)
        def normalize_inv_num(inv_num: str) -> str:
            """Normalize invoice number by removing common prefixes"""
            if not inv_num:
                return ""
            inv_num = inv_num.strip().upper()
            prefixes = ['INVOICE #', 'INVOICE#', 'INVOICE', 'INV-', 'INV']
            for prefix in prefixes:
                if inv_num.startswith(prefix):
                    inv_num = inv_num[len(prefix):].strip()
            return inv_num
        
        ocr_invoice_numbers = [inv_num.upper().strip() for inv_num in ocr_result.invoice_numbers]
        ocr_invoice_numbers_normalized = [normalize_inv_num(inv_num) for inv_num in ocr_invoice_numbers]
        
        # Try combinations of 2-3 invoices (most common cases)
        for combo_size in [2, 3]:
            for combo in itertools.combinations(filtered_invoices, combo_size):
                total_amount = sum(inv.get("amount", 0.0) for inv in combo)
                amount_diff = abs(total_amount - target_amount)
                
                if amount_diff <= tolerance:
                    # REQUIRE: All OCR invoice numbers must be in the combination
                    combo_invoice_numbers = [inv.get("invoice_number", "").upper().strip() for inv in combo]
                    combo_invoice_numbers_normalized = [normalize_inv_num(inv_num) for inv_num in combo_invoice_numbers]
                    
                    # Check if all OCR invoice numbers are found in the combination (with fuzzy matching)
                    all_ocr_invoices_found = all(
                        any(
                            # Exact match
                            ocr_inv == combo_inv or ocr_inv_norm == combo_inv_norm or
                            # Contains match
                            ocr_inv in combo_inv or combo_inv in ocr_inv or
                            ocr_inv_norm in combo_inv or combo_inv_norm in ocr_inv or
                            # Normalized match (numeric parts match)
                            (ocr_inv_norm and combo_inv_norm and 
                             ocr_inv_norm.isdigit() and combo_inv_norm.isdigit() and 
                             ocr_inv_norm == combo_inv_norm)
                            for combo_inv, combo_inv_norm in zip(combo_invoice_numbers, combo_invoice_numbers_normalized)
                        )
                        for ocr_inv, ocr_inv_norm in zip(ocr_invoice_numbers, ocr_invoice_numbers_normalized)
                    )
                    
                    if not all_ocr_invoices_found:
                        continue  # Skip this combination - not all OCR invoices are present
                    
                    # Calculate combined score
                    combo_score = 200.0  # Base score for multi-invoice match
                    
                    # Bonus for exact amount match
                    if amount_diff < 0.01:
                        combo_score += 100.0
                    
                    # Bonus for customer match (already filtered, but add bonus)
                    if customer_match_required:
                        customer_name = (ocr_result.customer_name or ocr_result.payor_name).lower()
                        all_match_customer = all(
                            self._string_similarity(customer_name, inv.get("customer_name", "").lower()) > 0.7
                            for inv in combo
                        )
                        if all_match_customer:
                            combo_score += 50.0
                    
                    # Penalty for more invoices (prefer fewer invoices)
                    combo_score -= (combo_size - 2) * 10.0
                    
                    # Create match entry
                    invoice_ids = [inv.get("invoice_id", inv.get("invoice_number", "")) for inv in combo]
                    invoice_numbers = [inv.get("invoice_number", "") for inv in combo]
                    
                    multi_match = {
                        "invoice_ids": invoice_ids,
                        "invoice_numbers": invoice_numbers,
                        "invoices": combo,
                        "total_amount": total_amount,
                        "amount_diff": amount_diff,
                        "match_score": combo_score,
                        "match_reasons": [
                            f"Multi-invoice match: {len(combo)} invoice(s) sum to ${total_amount:.2f}",
                            f"Invoices: {', '.join(invoice_numbers)}",
                            f"All OCR invoice numbers found in combination"
                        ],
                        "is_multi_invoice": True
                    }
                    multi_matches.append(multi_match)
        
        # Sort by score (descending)
        multi_matches.sort(key=lambda x: x["match_score"], reverse=True)
        return multi_matches
    
    def find_matches(self, ocr_result: OCRResult, max_results: int = 10) -> List[InvoiceMatch]:
        """Find and score matching invoices, including multi-invoice matches"""
        all_matches = {}
        
        # Primary: Search by invoice number (exact match)
        if ocr_result.invoice_numbers:
            for inv_num in ocr_result.invoice_numbers:
                invoices = self._search_invoices_by_number(inv_num, limit=20)
                for invoice in invoices:
                    # Create unique key: invoice_number + amount + customer + memo (to handle duplicate invoice numbers)
                    # This allows multiple line items with the same invoice number to be shown separately
                    memo = invoice.get('memo', '') or invoice.get('raw_data', {}).get('Memo', '')
                    unique_key = f"{invoice['invoice_number']}_{invoice.get('amount', 0)}_{invoice.get('customer_name', '')}_{memo}"
                    if unique_key not in all_matches:
                        all_matches[unique_key] = invoice
                        all_matches[unique_key]["match_score"] = 0.0
                        all_matches[unique_key]["match_reasons"] = []
                    
                    # High score for exact invoice number match
                    if invoice["invoice_number"].upper() == inv_num.upper():
                        all_matches[unique_key]["match_score"] += 100.0
                        all_matches[unique_key]["match_reasons"].append(f"Exact invoice number match: {inv_num}")
                        
                        # BONUS: If amount also matches, give very high score
                        if ocr_result.amount and invoice.get("amount"):
                            amount_diff = abs(ocr_result.amount - invoice["amount"])
                            if amount_diff < 0.01:  # Exact amount match
                                all_matches[unique_key]["match_score"] += 150.0  # Big bonus for both matching
                                all_matches[unique_key]["match_reasons"].append(f"Exact amount match: ${invoice['amount']:.2f}")
                            elif amount_diff < 1.0:  # Within $1
                                all_matches[unique_key]["match_score"] += 100.0
                                all_matches[unique_key]["match_reasons"].append(f"Amount match (within $1): ${invoice['amount']:.2f}")
                            elif amount_diff < 10.0:  # Within $10
                                all_matches[unique_key]["match_score"] += 50.0
                                all_matches[unique_key]["match_reasons"].append(f"Amount match (within $10): ${invoice['amount']:.2f}")
                    elif inv_num.upper() in invoice["invoice_number"].upper() or invoice["invoice_number"].upper() in inv_num.upper():
                        # Partial match - only give points if amount also matches reasonably
                        if ocr_result.amount and invoice.get("amount"):
                            amount_diff = abs(ocr_result.amount - invoice["amount"])
                            if amount_diff < 0.01:  # Exact amount match
                                all_matches[unique_key]["match_score"] += 80.0
                                all_matches[unique_key]["match_reasons"].append(f"Partial invoice number match: {inv_num}")
                                all_matches[unique_key]["match_reasons"].append(f"Exact amount match: ${invoice['amount']:.2f}")
                            elif amount_diff < 10.0:  # Within $10
                                all_matches[unique_key]["match_score"] += 50.0
                                all_matches[unique_key]["match_reasons"].append(f"Partial invoice number match: {inv_num}")
                                all_matches[unique_key]["match_reasons"].append(f"Amount match (within $10): ${invoice['amount']:.2f}")
                            else:
                                # Partial invoice match but amount doesn't match - give very low score
                                all_matches[unique_key]["match_score"] += 20.0
                                all_matches[unique_key]["match_reasons"].append(f"Partial invoice number match: {inv_num} (amount mismatch: ${amount_diff:.2f})")
                        else:
                            # No amount to compare - give low score for partial match only
                            all_matches[unique_key]["match_score"] += 30.0
                            all_matches[unique_key]["match_reasons"].append(f"Partial invoice number match: {inv_num} (no amount to verify)")
        
        # Secondary: Search by customer name + amount
        if ocr_result.customer_name or ocr_result.payor_name:
            customer_name = ocr_result.customer_name or ocr_result.payor_name
            if customer_name:
                invoices = self._search_invoices_by_customer(customer_name, limit=50)
                for invoice in invoices:
                    # Create unique key: invoice_number + amount + customer + memo (to handle duplicate invoice numbers)
                    memo = invoice.get('memo', '') or invoice.get('raw_data', {}).get('Memo', '')
                    unique_key = f"{invoice['invoice_number']}_{invoice.get('amount', 0)}_{invoice.get('customer_name', '')}_{memo}"
                    if unique_key not in all_matches:
                        all_matches[unique_key] = invoice
                        all_matches[unique_key]["match_score"] = 0.0
                        all_matches[unique_key]["match_reasons"] = []
                    
                    # Score based on customer name similarity
                    name_similarity = self._string_similarity(
                        customer_name.lower(),
                        invoice["customer_name"].lower()
                    )
                    
                    # Score based on amount match (if available)
                    amount_score = 0.0
                    amount_diff = 0.0
                    if ocr_result.amount and invoice.get("amount"):
                        amount_diff = abs(ocr_result.amount - invoice["amount"])
                        if amount_diff < 0.01:  # Exact match
                            amount_score = 80.0  # Increased from 50.0 - exact amount is very important
                        elif amount_diff < 1.0:  # Within $1
                            amount_score = 60.0  # Increased from 40.0
                        elif amount_diff < 10.0:  # Within $10
                            amount_score = 40.0  # Increased from 30.0
                        elif amount_diff < 100.0:  # Within $100
                            amount_score = 25.0  # Increased from 20.0
                    
                    # Increased name similarity weight and ensure customer + exact amount = high score
                    name_score = name_similarity * 50.0  # Increased from 40.0
                    combined_score = name_score + amount_score
                    
                    # Bonus: If customer name is very similar (>0.9) AND amount matches exactly, give extra points
                    if name_similarity > 0.9 and amount_diff < 0.01:
                        combined_score += 30.0  # Bonus for high confidence match
                    
                    all_matches[unique_key]["match_score"] += combined_score
                    
                    if name_similarity > 0.7:
                        all_matches[unique_key]["match_reasons"].append(
                            f"Customer name match: {invoice['customer_name']} (similarity: {name_similarity:.2f})"
                        )
                    if amount_score > 0:
                        all_matches[unique_key]["match_reasons"].append(
                            f"Amount match: ${invoice['amount']:.2f} (diff: ${amount_diff:.2f})"
                        )
        
        # Tertiary: Search by amount only (if no other strong matches)
        if ocr_result.amount and len(all_matches) < 5:
                invoices = self._search_invoices_by_amount(ocr_result.amount, tolerance=0.01, limit=20)
                for invoice in invoices:
                    # Create unique key: invoice_number + amount + customer + memo (to handle duplicate invoice numbers)
                    memo = invoice.get('memo', '') or invoice.get('raw_data', {}).get('Memo', '')
                    unique_key = f"{invoice['invoice_number']}_{invoice.get('amount', 0)}_{invoice.get('customer_name', '')}_{memo}"
                    if unique_key not in all_matches:
                        all_matches[unique_key] = invoice
                        all_matches[unique_key]["match_score"] = 0.0
                        all_matches[unique_key]["match_reasons"] = []
                    
                    # Lower score for amount-only match
                    amount_score = 15.0
                    all_matches[unique_key]["match_score"] += amount_score
                    all_matches[unique_key]["match_reasons"].append(
                        f"Amount-only match: ${invoice['amount']:.2f}"
                    )
        
        # Find multi-invoice matches if check amount is available AND invoice numbers were found
        multi_invoice_matches = []
        if ocr_result.amount and ocr_result.invoice_numbers:
            # Only use invoices that were found via invoice number search
            # This ensures we're only matching against invoices that actually exist in NetSuite/CSV
            candidate_invoices = []
            found_invoice_numbers = set()
            
            # Collect all invoices found via invoice number search
            for inv_num in ocr_result.invoice_numbers:
                invoices = self._search_invoices_by_number(inv_num, limit=20)
                for invoice in invoices:
                    # Use unique key to avoid duplicates
                    memo = invoice.get('memo', '') or invoice.get('raw_data', {}).get('Memo', '')
                    unique_key = f"{invoice['invoice_number']}_{invoice.get('amount', 0)}_{invoice.get('customer_name', '')}_{memo}"
                    if unique_key not in found_invoice_numbers:
                        candidate_invoices.append(invoice)
                        found_invoice_numbers.add(unique_key)
            
            # Only proceed if we found invoices matching the OCR invoice numbers
            if candidate_invoices and len(candidate_invoices) >= 2:
                multi_matches = self._find_multi_invoice_matches(ocr_result, candidate_invoices)
                multi_invoice_matches.extend(multi_matches)
        
        # Convert single invoice matches to InvoiceMatch objects
        matches = []
        for unique_key, invoice_data in all_matches.items():
            # Only include matches with score above 100
            if invoice_data["match_score"] > 100.0:
                # Use unique_key as invoice_id to preserve uniqueness, but display the invoice_number
                match = InvoiceMatch(
                    invoice_id=unique_key,  # Use unique key to preserve separate line items
                    invoice_number=invoice_data["invoice_number"],
                    customer_name=invoice_data["customer_name"],
                    amount=invoice_data.get("amount", 0.0),
                    due_date=invoice_data.get("due_date"),
                    subsidiary=invoice_data.get("subsidiary"),
                    match_score=invoice_data["match_score"],
                    match_reasons=invoice_data["match_reasons"]
                )
                matches.append(match)
        
        # Convert multi-invoice matches to InvoiceMatch objects
        # For multi-invoice matches, create a single match entry representing the combination
        for multi_match in multi_invoice_matches:
            # Create a combined invoice number string
            combined_invoice_number = " + ".join(multi_match["invoice_numbers"])
            combined_invoice_id = "|".join(multi_match["invoice_ids"])
            
            match = InvoiceMatch(
                invoice_id=combined_invoice_id,
                invoice_number=combined_invoice_number,
                customer_name=multi_match["invoices"][0].get("customer_name", "N/A") if multi_match["invoices"] else "N/A",
                amount=multi_match["total_amount"],
                due_date=None,  # Multi-invoice matches don't have a single due date
                subsidiary=multi_match["invoices"][0].get("subsidiary") if multi_match["invoices"] else None,
                match_score=multi_match["match_score"],
                match_reasons=multi_match["match_reasons"]
            )
            matches.append(match)
        
        # Sort by score (descending) and return top results
        matches.sort(key=lambda x: x.match_score, reverse=True)
        return matches[:max_results]
    
    def _string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (0.0 to 1.0)"""
        return SequenceMatcher(None, str1, str2).ratio()

