"""
CSV Invoice Service - Fallback service that searches local CSV file
for invoice matches when NetSuite API is unavailable
"""
import csv
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher


class CSVInvoiceService:
    """Service for searching invoices from CSV file"""
    
    def __init__(self, csv_path: Optional[str] = None):
        """
        Initialize CSV invoice service
        
        Args:
            csv_path: Path to CSV file. If None, looks for cleaned_open_invoices.csv
                     in project root or current directory
        """
        if csv_path:
            self.csv_path = Path(csv_path)
        else:
            # Try to find CSV in project root
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent
            self.csv_path = project_root / "cleaned_open_invoices.csv"
            
            # Fallback to current directory
            if not self.csv_path.exists():
                self.csv_path = Path("cleaned_open_invoices.csv")
        
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"CSV file not found at: {self.csv_path}. "
                f"Please ensure cleaned_open_invoices.csv exists in the project root."
            )
        
        self._invoices_cache = None
    
    def _load_invoices(self) -> List[Dict[str, Any]]:
        """Load and cache invoices from CSV"""
        if self._invoices_cache is not None:
            return self._invoices_cache
        
        invoices = []
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Clean invoice number (remove "Invoice #" prefix if present)
                    invoice_num = row.get('Invoice Number', '').strip()
                    if invoice_num.startswith('Invoice #'):
                        invoice_num = invoice_num.replace('Invoice #', '').strip()
                    
                    # Parse amount
                    amount_str = row.get('Amount', '0').strip()
                    try:
                        amount = float(amount_str) if amount_str else 0.0
                    except (ValueError, TypeError):
                        amount = 0.0
                    
                    invoice = {
                        "invoice_id": invoice_num,  # Use invoice number as ID
                        "invoice_number": invoice_num,
                        "customer_name": row.get('Name', '').strip(),
                        "amount": amount,
                        "due_date": row.get('Due Date', '').strip(),
                        "status": row.get('Status', '').strip(),
                        "date_created": row.get('Date Created', '').strip(),
                        "account": row.get('Account', '').strip(),
                        "subsidiary": None,  # Not in CSV
                        "raw_data": row  # Keep original row data
                    }
                    invoices.append(invoice)
            
            self._invoices_cache = invoices
            return invoices
        except Exception as e:
            raise Exception(f"Failed to load CSV file: {str(e)}")
    
    def search_invoices_by_number(self, invoice_number: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search invoices by invoice number"""
        invoices = self._load_invoices()
        results = []
        
        # Clean search term
        search_term = invoice_number.strip().upper()
        if search_term.startswith('INVOICE #'):
            search_term = search_term.replace('INVOICE #', '').strip()
        
        for invoice in invoices:
            inv_num = invoice["invoice_number"].upper()
            
            # Exact match
            if inv_num == search_term:
                results.append(invoice)
            # Contains match
            elif search_term in inv_num or inv_num in search_term:
                results.append(invoice)
            
            if len(results) >= limit:
                break
        
        return results
    
    def search_invoices_by_customer(self, customer_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search invoices by customer name (fuzzy match)"""
        invoices = self._load_invoices()
        results = []
        
        search_term = customer_name.strip().upper()
        
        # Calculate similarity scores
        scored_invoices = []
        for invoice in invoices:
            customer = invoice["customer_name"].upper()
            
            # Exact match
            if customer == search_term:
                scored_invoices.append((1.0, invoice))
            # Contains match
            elif search_term in customer or customer in search_term:
                scored_invoices.append((0.8, invoice))
            # Fuzzy match
            else:
                similarity = SequenceMatcher(None, search_term, customer).ratio()
                if similarity > 0.5:  # 50% similarity threshold
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

