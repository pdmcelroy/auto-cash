"""
SuiteQL Invoice Service
Fetches open invoices from NetSuite using SuiteQL with caching
"""
import os
import time
import logging
import requests
import concurrent.futures
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)


class SuiteQLInvoiceService:
    """Service for fetching and searching NetSuite invoices using SuiteQL"""
    
    def __init__(self, access_token: Optional[str] = None, cache_ttl: int = 3600):
        """
        Initialize SuiteQL Invoice Service
        
        Args:
            access_token: NetSuite OAuth 2.0 access token. If None, reads from NETSUITE_ACCESS_TOKEN env var
            cache_ttl: Cache time-to-live in seconds (default: 3600 = 1 hour)
        """
        # Load environment variables if not already loaded
        _current_file = Path(__file__).resolve()
        _backend_dir = _current_file.parent.parent.parent
        _project_root = _backend_dir.parent
        
        env_paths = [
            _backend_dir / ".env",
            _project_root / ".env",
        ]
        
        for env_path in env_paths:
            if env_path.exists():
                load_dotenv(env_path, override=True)
                break
        
        self.access_token = access_token or os.getenv("NETSUITE_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError(
                "NETSUITE_ACCESS_TOKEN not provided and not found in environment variables. "
                "Please set NETSUITE_ACCESS_TOKEN in your .env file or pass it to the constructor."
            )
        
        self.base_url = os.getenv(
            "NETSUITE_BASE_URL",
            "https://4083091-sb2.suitetalk.api.netsuite.com"
        )
        self.cache_ttl = cache_ttl
        self._cache = None
        self._cache_timestamp = None
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        if self._cache is None or self._cache_timestamp is None:
            return False
        elapsed = time.time() - self._cache_timestamp
        return elapsed < self.cache_ttl
    
    def _fetch_invoices_via_suiteql(self) -> List[Dict[str, Any]]:
        """Fetch invoices using SuiteQL query"""
        suiteql_endpoint = "/services/rest/query/v1/suiteql"
        url = f"{self.base_url}{suiteql_endpoint}"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Prefer": "transient"
        }
        
        # Calculate date range for last 12 months
        today = datetime.now()
        start_date = today - timedelta(days=365)  # 12 months ago
        # Format dates as M/D/YYYY (remove leading zeros)
        start_date_str = f"{start_date.month}/{start_date.day}/{start_date.year}"
        end_date_str = f"{today.month}/{today.day}/{today.year}"
        
        # Build SuiteQL query
        query = f"""
        SELECT 
            transaction.id,
            transaction.tranid,
            transaction.status,
            transaction.trandate,
            transaction.duedate,
            transaction.entity,
            transaction.subsidiary
        FROM transaction
        WHERE transaction.type = 'CustInvc'
        AND transaction.status = 'A'
        AND transaction.trandate >= '{start_date_str}'
        AND transaction.trandate <= '{end_date_str}'
        ORDER BY transaction.trandate DESC
        """
        
        query_data = {"q": query.strip()}
        
        all_invoices = []
        offset = 0
        page_size = 1000
        page = 0
        max_pages = 1000  # Safety limit
        
        logger.info(f"Fetching open invoices from last 12 months via SuiteQL...")
        
        try:
            while page < max_pages:
                params = {"limit": page_size, "offset": offset}
                
                response = requests.post(url, headers=headers, json=query_data, params=params, timeout=30)
                
                if response.status_code != 200:
                    logger.error(f"SuiteQL query failed: {response.status_code} - {response.text}")
                    break
                
                data = response.json()
                items = data.get("items", [])
                
                if not items:
                    break
                
                all_invoices.extend(items)
                logger.info(f"Fetched {len(items)} invoices (total: {len(all_invoices)})")
                
                # Check if there are more results
                has_more = data.get("hasMore", False)
                if not has_more or len(items) < page_size:
                    break
                
                offset += page_size
                page += 1
            
            logger.info(f"SuiteQL query complete. Total invoices: {len(all_invoices)}")
            
            # Fetch additional details (amounts and customer info)
            if all_invoices:
                logger.info("Fetching invoice amounts and customer information...")
                all_invoices = self._fetch_invoice_amounts(all_invoices)
                all_invoices = self._fetch_customer_info(all_invoices)
            
            return all_invoices
            
        except Exception as e:
            logger.error(f"Error fetching invoices via SuiteQL: {e}", exc_info=True)
            raise
    
    def _fetch_invoice_amounts(self, invoices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch amount remaining for invoices via parallel REST API calls"""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Prefer": "transient"
        }
        
        def fetch_amount(invoice):
            """Fetch amount remaining for a single invoice"""
            invoice_id = invoice.get("id")
            if not invoice_id:
                invoice["amountremaining"] = 0.0
                return invoice
            
            try:
                url = f"{self.base_url}/services/rest/record/v1/invoice/{invoice_id}"
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    invoice_data = response.json()
                    amount_remaining = invoice_data.get("amountremaining", invoice_data.get("amountRemaining", 0))
                    invoice["amountremaining"] = float(amount_remaining) if amount_remaining else 0.0
                else:
                    invoice["amountremaining"] = 0.0
            except Exception as e:
                logger.debug(f"Error fetching amount for invoice {invoice_id}: {e}")
                invoice["amountremaining"] = 0.0
            
            return invoice
        
        # Use ThreadPoolExecutor for parallel requests
        max_workers = min(20, len(invoices))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            invoices = list(executor.map(fetch_amount, invoices))
        
        return invoices
    
    def _fetch_customer_info(self, invoices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch customer information for invoices via parallel REST API calls"""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Prefer": "transient"
        }
        
        # Get unique customer IDs
        customer_ids = list(set(str(inv.get("entity", "")) for inv in invoices if inv.get("entity")))
        
        if not customer_ids:
            # Add default companyname if no customers
            for invoice in invoices:
                invoice["companyname"] = "N/A"
            return invoices
        
        logger.info(f"Fetching customer info for {len(customer_ids)} unique customers...")
        
        customer_map = {}
        
        def fetch_customer(customer_id):
            """Fetch a single customer"""
            try:
                url = f"{self.base_url}/services/rest/record/v1/customer/{customer_id}"
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    customer = response.json()
                    # Try multiple fields for company name
                    company_name = (customer.get("companyName") or 
                                  customer.get("companyname") or
                                  customer.get("entityId") or
                                  customer.get("entityid") or 
                                  customer.get("altname") or
                                  customer.get("name") or
                                  "N/A")
                    return customer_id, {"companyname": company_name}
                else:
                    return customer_id, None
            except Exception as e:
                logger.debug(f"Error fetching customer {customer_id}: {e}")
                return customer_id, None
        
        # Use ThreadPoolExecutor for parallel requests
        max_workers = min(20, len(customer_ids))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_customer = {executor.submit(fetch_customer, cid): cid for cid in customer_ids}
            
            for future in concurrent.futures.as_completed(future_to_customer):
                customer_id, customer_info = future.result()
                if customer_info:
                    customer_map[customer_id] = customer_info
        
        # Add customer info to invoices
        for invoice in invoices:
            entity_id = str(invoice.get("entity", ""))
            if entity_id in customer_map:
                invoice.update(customer_map[entity_id])
            else:
                invoice["companyname"] = "N/A"
        
        return invoices
    
    def get_open_invoices(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get all open invoices from the last 12 months
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh data
        
        Returns:
            List of invoice dictionaries with fields: id, tranid, status, trandate, duedate, 
            entity, subsidiary, amountremaining, companyname
        """
        # Check cache first
        if not force_refresh and self._is_cache_valid():
            logger.info("Using cached invoice data")
            return self._cache
        
        # Fetch fresh data
        logger.info("Fetching fresh invoice data from NetSuite...")
        invoices = self._fetch_invoices_via_suiteql()
        
        # Update cache
        self._cache = invoices
        self._cache_timestamp = time.time()
        
        logger.info(f"Cached {len(invoices)} invoices (TTL: {self.cache_ttl}s)")
        return invoices
    
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
    
    def search_by_number(self, invoice_number: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search invoices by invoice number with fuzzy matching"""
        invoices = self.get_open_invoices()
        results = []
        
        # Clean and normalize search term
        search_term = invoice_number.strip().upper()
        search_term_normalized = self._normalize_invoice_number(search_term)
        
        logger.debug(f"SuiteQL: Searching for invoice number '{search_term}' (normalized: '{search_term_normalized}') in {len(invoices)} invoices")
        
        for invoice in invoices:
            inv_num = invoice.get("tranid", "").upper()
            inv_num_normalized = self._normalize_invoice_number(inv_num)
            
            # Exact match (with or without prefix)
            if inv_num == search_term:
                logger.debug(f"SuiteQL: Found exact match: {inv_num}")
                results.append(self._format_invoice(invoice))
            # Normalized exact match (both without prefix)
            elif inv_num_normalized and search_term_normalized and inv_num_normalized == search_term_normalized:
                logger.debug(f"SuiteQL: Found normalized match: {inv_num} (normalized: {inv_num_normalized})")
                results.append(self._format_invoice(invoice))
            # Contains match (search term in invoice number)
            elif search_term in inv_num or search_term_normalized in inv_num:
                logger.debug(f"SuiteQL: Found contains match: {inv_num} contains {search_term}")
                results.append(self._format_invoice(invoice))
            # Contains match (invoice number in search term)
            elif inv_num in search_term or inv_num_normalized in search_term:
                logger.debug(f"SuiteQL: Found reverse contains match: {search_term} contains {inv_num}")
                results.append(self._format_invoice(invoice))
            # Numeric-only match (if both are mostly numeric, compare the numeric parts)
            elif search_term_normalized.isdigit() and inv_num_normalized.isdigit():
                if search_term_normalized == inv_num_normalized:
                    logger.debug(f"SuiteQL: Found numeric match: {inv_num_normalized}")
                    results.append(self._format_invoice(invoice))
            
            if len(results) >= limit:
                break
        
        logger.info(f"SuiteQL: Found {len(results)} invoices matching '{search_term}'")
        return results
    
    def search_by_customer(self, customer_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search invoices by customer name (fuzzy match)"""
        from difflib import SequenceMatcher
        
        invoices = self.get_open_invoices()
        results = []
        
        # Normalize customer name
        def normalize_name(name: str) -> str:
            import re
            name = name.upper().strip()
            name = re.sub(r'\s*-\s*\([^)]+\)', '', name)  # Remove (SFO) VENDOR etc
            name = re.sub(r'\s*,\s*', ' ', name)  # Normalize commas
            name = re.sub(r'\s+', ' ', name)  # Normalize spaces
            name = re.sub(r'[^\w\s]', '', name)  # Remove punctuation except spaces
            return name.strip()
        
        search_term = normalize_name(customer_name)
        
        # Calculate similarity scores
        scored_invoices = []
        for invoice in invoices:
            customer = normalize_name(invoice.get("companyname", ""))
            
            # Exact match after normalization
            if customer == search_term:
                scored_invoices.append((1.0, invoice))
            # Contains match
            elif search_term in customer or customer in search_term:
                scored_invoices.append((0.8, invoice))
            # Fuzzy match
            else:
                similarity = SequenceMatcher(None, search_term, customer).ratio()
                if similarity > 0.4:
                    scored_invoices.append((similarity, invoice))
        
        # Sort by score (descending) and return top results
        scored_invoices.sort(key=lambda x: x[0], reverse=True)
        results = [self._format_invoice(inv) for _, inv in scored_invoices[:limit]]
        
        return results
    
    def search_by_amount(self, amount: float, tolerance: float = 0.01, limit: int = 50) -> List[Dict[str, Any]]:
        """Search invoices by amount (within tolerance)"""
        invoices = self.get_open_invoices()
        results = []
        
        for invoice in invoices:
            inv_amount = invoice.get("amountremaining", 0.0)
            if inv_amount:
                amount_diff = abs(inv_amount - amount)
                if amount_diff <= tolerance:
                    results.append(self._format_invoice(invoice))
                    if len(results) >= limit:
                        break
        
        return results
    
    def _format_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format invoice data to match expected structure"""
        return {
            "invoice_id": invoice_data.get("id", ""),
            "invoice_number": invoice_data.get("tranid", ""),
            "customer_name": invoice_data.get("companyname", "N/A"),
            "amount": invoice_data.get("amountremaining", 0.0),
            "due_date": invoice_data.get("duedate", ""),
            "subsidiary": invoice_data.get("subsidiary", ""),
            "status": invoice_data.get("status", ""),
            "date_created": invoice_data.get("trandate", ""),
            "account": None,  # Not available from SuiteQL
            "memo": "",  # Not available from SuiteQL
            "raw_data": invoice_data  # Keep original data
        }

