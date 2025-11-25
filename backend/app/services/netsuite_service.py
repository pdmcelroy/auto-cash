"""
NetSuite Service - Wrapper around netsuite-test client
Handles invoice searching and retrieval
"""
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
import os

# Add netsuite-test repo to path
# Try relative path first, then absolute path
current_file = Path(__file__).resolve()
# Go up from: automated-cash-app/backend/app/services/netsuite_service.py
# To: development/
development_dir = current_file.parent.parent.parent.parent.parent
netsuite_test_path = development_dir / "netsuite-test"

# Fallback: try environment variable or common locations
if not netsuite_test_path.exists():
    # Try to find it via environment variable
    env_path = os.getenv("NETSUITE_TEST_PATH")
    if env_path and Path(env_path).exists():
        netsuite_test_path = Path(env_path)
    else:
        # Try common location
        common_path = Path.home() / "Documents" / "development" / "netsuite-test"
        if common_path.exists():
            netsuite_test_path = common_path

if netsuite_test_path.exists():
    sys.path.insert(0, str(netsuite_test_path))
else:
    raise ImportError(
        f"Could not find netsuite-test repository. "
        f"Expected at: {netsuite_test_path}. "
        f"Please set NETSUITE_TEST_PATH environment variable or ensure netsuite-test is in the expected location."
    )

from config import NetSuiteConfig
from netsuite_client import NetSuiteClient


class NetSuiteService:
    """Service for interacting with NetSuite to search invoices"""
    
    def __init__(self):
        self.config = NetSuiteConfig()
        self.client = NetSuiteClient(self.config)
        self._authenticated = False
    
    def _ensure_authenticated(self):
        """Ensure we're authenticated with NetSuite"""
        if not self._authenticated:
            if not self.client.authenticate():
                raise Exception("Failed to authenticate with NetSuite")
            self._authenticated = True
    
    def search_invoices_by_number(self, invoice_number: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search invoices by invoice number"""
        self._ensure_authenticated()
        
        try:
            # Search using query parameter
            query = f"tranid={invoice_number}"
            response = self.client.search_records(
                record_type="invoice",
                query=query,
                limit=limit
            )
            
            invoices = []
            if "items" in response:
                for item in response["items"]:
                    invoices.append(self._format_invoice(item))
            
            return invoices
        except Exception as e:
            print(f"Error searching invoices by number: {e}")
            return []
    
    def search_invoices_by_customer(self, customer_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search invoices by customer name (fuzzy match)"""
        self._ensure_authenticated()
        
        try:
            # Search for customer first
            customer_query = f"entity LIKE '%{customer_name}%'"
            customer_response = self.client.search_records(
                record_type="customer",
                query=customer_query,
                limit=10
            )
            
            customer_ids = []
            if "items" in customer_response:
                for item in customer_response["items"]:
                    if "id" in item:
                        customer_ids.append(item["id"])
            
            # If no customers found, try searching invoices directly
            if not customer_ids:
                invoice_query = f"entity LIKE '%{customer_name}%'"
                response = self.client.search_records(
                    record_type="invoice",
                    query=invoice_query,
                    limit=limit
                )
            else:
                # Search invoices for these customers
                invoices = []
                for customer_id in customer_ids[:5]:  # Limit to first 5 customers
                    invoice_query = f"entity={customer_id}"
                    response = self.client.search_records(
                        record_type="invoice",
                        query=invoice_query,
                        limit=limit
                    )
                    if "items" in response:
                        for item in response["items"]:
                            invoices.append(self._format_invoice(item))
                return invoices
            
            invoices = []
            if "items" in response:
                for item in response["items"]:
                    invoices.append(self._format_invoice(item))
            
            return invoices
        except Exception as e:
            print(f"Error searching invoices by customer: {e}")
            return []
    
    def search_invoices_by_amount(self, amount: float, tolerance: float = 0.01, limit: int = 50) -> List[Dict[str, Any]]:
        """Search invoices by amount (within tolerance)"""
        self._ensure_authenticated()
        
        try:
            # NetSuite search for amount range
            min_amount = amount - tolerance
            max_amount = amount + tolerance
            
            # Note: NetSuite query syntax may vary, this is a simplified approach
            query = f"amount >= {min_amount} AND amount <= {max_amount}"
            response = self.client.search_records(
                record_type="invoice",
                query=query,
                limit=limit
            )
            
            invoices = []
            if "items" in response:
                for item in response["items"]:
                    invoice = self._format_invoice(item)
                    # Filter by exact amount match within tolerance
                    if invoice.get("amount"):
                        if abs(invoice["amount"] - amount) <= tolerance:
                            invoices.append(invoice)
            
            return invoices
        except Exception as e:
            print(f"Error searching invoices by amount: {e}")
            return []
    
    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific invoice by ID"""
        self._ensure_authenticated()
        
        try:
            response = self.client.get_record(
                record_type="invoice",
                record_id=invoice_id,
                fields=["tranid", "entity", "amount", "duedate", "subsidiary", "status"]
            )
            return self._format_invoice(response)
        except Exception as e:
            print(f"Error getting invoice: {e}")
            return None
    
    def _format_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format invoice data from NetSuite response"""
        return {
            "invoice_id": invoice_data.get("id", ""),
            "invoice_number": invoice_data.get("tranid", ""),
            "customer_name": self._extract_customer_name(invoice_data),
            "amount": float(invoice_data.get("amount", 0)) if invoice_data.get("amount") else None,
            "due_date": invoice_data.get("duedate", ""),
            "subsidiary": self._extract_subsidiary(invoice_data),
            "status": invoice_data.get("status", "")
        }
    
    def _extract_customer_name(self, invoice_data: Dict[str, Any]) -> str:
        """Extract customer name from invoice data"""
        entity = invoice_data.get("entity")
        if isinstance(entity, dict):
            return entity.get("name", "")
        elif isinstance(entity, str):
            return entity
        return ""
    
    def _extract_subsidiary(self, invoice_data: Dict[str, Any]) -> str:
        """Extract subsidiary from invoice data"""
        subsidiary = invoice_data.get("subsidiary")
        if isinstance(subsidiary, dict):
            return subsidiary.get("name", "")
        elif isinstance(subsidiary, str):
            return subsidiary
        return ""

