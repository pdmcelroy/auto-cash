"""
CSV Invoice Service - Fallback service that searches local CSV file
for invoice matches when NetSuite API is unavailable
"""
import csv
import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class CSVInvoiceService:
    """Service for searching invoices from CSV file"""
    
    def __init__(self, csv_path: Optional[str] = None):
        """
        Initialize CSV invoice service
        
        Args:
            csv_path: Path to CSV file. If None, looks for open_invoices_dec2024_2025.csv
                     or cleaned_open_invoices.csv in backend directory or project root
        """
        if csv_path:
            self.csv_path = Path(csv_path)
        else:
            # Try to find CSV files in backend directory first, then project root
            current_file = Path(__file__).resolve()
            backend_dir = current_file.parent.parent.parent  # backend/
            project_root = backend_dir.parent  # project root
            
            # Try open_invoices_dec2024_2025.csv first (newer format)
            csv_paths = [
                backend_dir / "open_invoices_dec2024_2025.csv",
                project_root / "open_invoices_dec2024_2025.csv",
                backend_dir / "cleaned_open_invoices.csv",
                project_root / "cleaned_open_invoices.csv",
                Path("cleaned_open_invoices.csv"),  # Current directory fallback
            ]
            
            self.csv_path = None
            for path in csv_paths:
                if path.exists():
                    self.csv_path = path
                    break
        
        if not self.csv_path or not self.csv_path.exists():
            raise FileNotFoundError(
                f"CSV file not found. Tried: open_invoices_dec2024_2025.csv, cleaned_open_invoices.csv. "
                f"Please ensure one of these files exists in the backend directory or project root."
            )
        
        self._invoices_cache = None
        self._csv_mtime = None  # Track CSV file modification time
    
    def _load_invoices(self) -> List[Dict[str, Any]]:
        """Load and cache invoices from CSV"""
        # Check if CSV file has been modified
        current_mtime = self.csv_path.stat().st_mtime if self.csv_path.exists() else 0
        if self._invoices_cache is not None and self._csv_mtime == current_mtime:
            return self._invoices_cache
        
        # Clear cache if file was modified
        if self._csv_mtime is not None and self._csv_mtime != current_mtime:
            self._invoices_cache = None
        
        invoices = []
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                # Detect CSV format by checking column names
                fieldnames = reader.fieldnames or []
                is_suiteql_format = 'tranid' in fieldnames and 'companyname' in fieldnames
                
                for row in reader:
                    if is_suiteql_format:
                        # Format: id,tranid,status,trandate,duedate,entity,companyname,amountremaining,subsidiary
                        invoice_num = row.get('tranid', '').strip()
                        customer_name = row.get('companyname', '').strip()
                        amount_str = row.get('amountremaining', '0').strip()
                        due_date = row.get('duedate', '').strip()
                        status = row.get('status', '').strip()
                        date_created = row.get('trandate', '').strip()
                        subsidiary = row.get('subsidiary', '').strip()
                        invoice_id = row.get('id', '').strip()
                    else:
                        # Format: Invoice Number, Name, Amount, Due Date, Status, Date Created, Account, Memo
                        invoice_num = row.get('Invoice Number', '').strip()
                        if invoice_num.startswith('Invoice #'):
                            invoice_num = invoice_num.replace('Invoice #', '').strip()
                        customer_name = row.get('Name', '').strip()
                        amount_str = row.get('Amount', '0').strip()
                        due_date = row.get('Due Date', '').strip()
                        status = row.get('Status', '').strip()
                        date_created = row.get('Date Created', '').strip()
                        subsidiary = None
                        invoice_id = None
                    
                    # Parse amount
                    try:
                        amount = float(amount_str) if amount_str else 0.0
                    except (ValueError, TypeError):
                        amount = 0.0
                    
                    # Generate unique ID
                    memo = row.get('Memo', '').strip() if not is_suiteql_format else ''
                    if invoice_id:
                        unique_id = invoice_id
                    else:
                        unique_id = f"{invoice_num}_{amount}_{customer_name}_{memo}"
                    
                    invoice = {
                        "invoice_id": unique_id,
                        "invoice_number": invoice_num,
                        "customer_name": customer_name,
                        "amount": amount,
                        "due_date": due_date,
                        "status": status,
                        "date_created": date_created,
                        "account": row.get('Account', '').strip() if not is_suiteql_format else None,
                        "subsidiary": subsidiary,
                        "memo": memo,
                        "raw_data": row  # Keep original row data
                    }
                    invoices.append(invoice)
            
            self._invoices_cache = invoices
            self._csv_mtime = current_mtime  # Store modification time
            logger.info(f"CSV: Loaded {len(invoices)} invoices from {self.csv_path}")
            if invoices:
                logger.debug(f"CSV: Sample invoice numbers: {[inv.get('invoice_number') for inv in invoices[:5]]}")
            return invoices
        except Exception as e:
            logger.error(f"CSV: Failed to load CSV file: {e}")
            raise Exception(f"Failed to load CSV file: {str(e)}")
    
    def _normalize_invoice_number(self, inv_num: str) -> str:
        """Normalize invoice number by removing common prefixes for comparison"""
        if not inv_num:
            return ""
        inv_num = inv_num.strip().upper()
        # Remove common prefixes
        prefixes = ['INVOICE #', 'INVOICE#', 'INVOICE', 'INV-', 'INV']
        for prefix in prefixes:
            if inv_num.startswith(prefix):
                inv_num = inv_num[len(prefix):].strip()
        return inv_num
    
    def search_invoices_by_number(self, invoice_number: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search invoices by invoice number with fuzzy matching"""
        invoices = self._load_invoices()
        results = []
        
        # Clean and normalize search term
        search_term = invoice_number.strip().upper()
        search_term_normalized = self._normalize_invoice_number(search_term)
        
        logger.debug(f"CSV: Searching for invoice number '{search_term}' (normalized: '{search_term_normalized}') in {len(invoices)} invoices")
        
        for invoice in invoices:
            inv_num = invoice["invoice_number"].upper()
            inv_num_normalized = self._normalize_invoice_number(inv_num)
            
            # Exact match (with or without prefix)
            if inv_num == search_term:
                logger.debug(f"CSV: Found exact match: {inv_num}")
                results.append(invoice)
            # Normalized exact match (both without prefix)
            elif inv_num_normalized and search_term_normalized and inv_num_normalized == search_term_normalized:
                logger.debug(f"CSV: Found normalized match: {inv_num} (normalized: {inv_num_normalized})")
                results.append(invoice)
            # Contains match (search term in invoice number)
            elif search_term in inv_num or search_term_normalized in inv_num:
                logger.debug(f"CSV: Found contains match: {inv_num} contains {search_term}")
                results.append(invoice)
            # Contains match (invoice number in search term)
            elif inv_num in search_term or inv_num_normalized in search_term:
                logger.debug(f"CSV: Found reverse contains match: {search_term} contains {inv_num}")
                results.append(invoice)
            # Numeric-only match (if both are mostly numeric, compare the numeric parts)
            elif search_term_normalized.isdigit() and inv_num_normalized.isdigit():
                if search_term_normalized == inv_num_normalized:
                    logger.debug(f"CSV: Found numeric match: {inv_num_normalized}")
                    results.append(invoice)
            
            if len(results) >= limit:
                break
        
        logger.info(f"CSV: Found {len(results)} invoices matching '{search_term}'")
        return results
    
    def search_invoices_by_customer(self, customer_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search invoices by customer name (fuzzy match)"""
        invoices = self._load_invoices()
        results = []
        
        # Normalize customer name: remove common suffixes, punctuation, normalize spaces
        def normalize_name(name: str) -> str:
            name = name.upper().strip()
            # Remove common suffixes and parenthetical info
            name = re.sub(r'\s*-\s*\([^)]+\)', '', name)  # Remove (SFO) VENDOR etc
            name = re.sub(r'\s*,\s*', ' ', name)  # Normalize commas
            name = re.sub(r'\s+', ' ', name)  # Normalize spaces
            name = re.sub(r'[^\w\s]', '', name)  # Remove punctuation except spaces
            return name.strip()
        
        search_term = normalize_name(customer_name)
        
        # Calculate similarity scores
        scored_invoices = []
        for invoice in invoices:
            customer = normalize_name(invoice["customer_name"])
            
            # Exact match after normalization
            if customer == search_term:
                scored_invoices.append((1.0, invoice))
            # Contains match
            elif search_term in customer or customer in search_term:
                scored_invoices.append((0.8, invoice))
            # Fuzzy match
            else:
                similarity = SequenceMatcher(None, search_term, customer).ratio()
                if similarity > 0.4:  # Lower threshold to 40% to catch "U-FREIGHT" vs "UFREIGHT"
                    scored_invoices.append((similarity, invoice))
        
        # Sort by score (descending) and return top results
        scored_invoices.sort(key=lambda x: x[0], reverse=True)
        results = [inv for _, inv in scored_invoices[:limit]]
        
        return results
    
    def search_invoices_by_amount(self, amount: float, tolerance: float = 0.01, limit: int = 50) -> List[Dict[str, Any]]:
        """Search invoices by amount (within tolerance)"""
        invoices = self._load_invoices()
        results = []
        
        for invoice in invoices:
            inv_amount = invoice.get("amount", 0.0)
            if inv_amount:
                amount_diff = abs(inv_amount - amount)
                if amount_diff <= tolerance:
                    results.append(invoice)
                    if len(results) >= limit:
                        break
        
        return results
    
    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific invoice by ID (invoice number)"""
        invoices = self._load_invoices()
        for invoice in invoices:
            if invoice["invoice_id"] == invoice_id or invoice["invoice_number"] == invoice_id:
                return invoice
        return None

