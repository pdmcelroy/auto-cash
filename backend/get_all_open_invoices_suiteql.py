#!/usr/bin/env python3
"""
Get all open invoices from NetSuite using SuiteQL
Much faster than individual REST API calls
"""
import requests
import json
import csv
import sys
import os
import time
from typing import List, Dict, Any, Optional


def fetch_invoice_amounts(access_token: str, base_url: str, invoices: List[Dict[str, Any]], 
                          verbose: bool = False) -> List[Dict[str, Any]]:
    """
    Fetch amount remaining for invoices via REST API
    Uses parallel requests for efficiency
    """
    import concurrent.futures
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "transient"
    }
    
    def fetch_amount(invoice):
        """Fetch amount remaining for a single invoice"""
        invoice_id = invoice.get("id")
        if not invoice_id:
            return invoice
        
        try:
            url = f"{base_url}/services/rest/record/v1/invoice/{invoice_id}"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                invoice_data = response.json()
                amount_remaining = invoice_data.get("amountremaining", invoice_data.get("amountRemaining", 0))
                invoice["amountremaining"] = float(amount_remaining) if amount_remaining else 0.0
            else:
                invoice["amountremaining"] = 0.0
        except Exception as e:
            if verbose:
                print(f"    Error fetching amount for invoice {invoice_id}: {e}")
            invoice["amountremaining"] = 0.0
        
        return invoice
    
    # Use ThreadPoolExecutor for parallel requests
    max_workers = min(20, len(invoices))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        invoices = list(executor.map(fetch_amount, invoices))
    
    return invoices


def fetch_customer_info(access_token: str, base_url: str, invoices: List[Dict[str, Any]], 
                        verbose: bool = False, batch_size: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch customer information for invoices via REST API
    Uses batching and parallel requests for efficiency
    """
    import concurrent.futures
    import threading
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "transient"
    }
    
    # Get unique customer IDs
    customer_ids = list(set(str(inv.get("entity", "")) for inv in invoices if inv.get("entity")))
    
    if not customer_ids:
        return invoices
    
    print(f"  Fetching details for {len(customer_ids)} unique customers...")
    
    customer_map = {}
    lock = threading.Lock()
    
    def fetch_customer(customer_id):
        """Fetch a single customer"""
        try:
            url = f"{base_url}/services/rest/record/v1/customer/{customer_id}"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                customer = response.json()
                # Try multiple fields for company name (note: camelCase in NetSuite)
                company_name = (customer.get("companyName") or 
                              customer.get("companyname") or
                              customer.get("entityId") or
                              customer.get("entityid") or 
                              customer.get("altname") or
                              customer.get("name") or
                              "N/A")
                return customer_id, {
                    "companyname": company_name
                }
            else:
                return customer_id, None
        except Exception as e:
            if verbose:
                print(f"    Error fetching customer {customer_id}: {e}")
            return customer_id, None
    
    # Use ThreadPoolExecutor for parallel requests
    max_workers = min(20, len(customer_ids))  # Limit concurrent requests
    fetched = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_customer = {executor.submit(fetch_customer, cid): cid for cid in customer_ids}
        
        for future in concurrent.futures.as_completed(future_to_customer):
            customer_id, customer_info = future.result()
            if customer_info:
                customer_map[customer_id] = customer_info
                fetched += 1
                if verbose and fetched % 50 == 0:
                    print(f"    Fetched {fetched}/{len(customer_ids)} customers...")
    
    # Add customer info to invoices
    for invoice in invoices:
        entity_id = str(invoice.get("entity", ""))
        if entity_id in customer_map:
            invoice.update(customer_map[entity_id])
        else:
            invoice["companyname"] = "N/A"
    
    return invoices


def query_all_open_invoices_suiteql(access_token: str, 
                                    base_url: str = "https://4083091-sb2.suitetalk.api.netsuite.com",
                                    output_file: Optional[str] = None,
                                    year: Optional[int] = None,
                                    include_customer: bool = True,
                                    verbose: bool = False) -> List[Dict[str, Any]]:
    """
    Query all open invoices using SuiteQL with pagination
    
    Args:
        access_token: OAuth 2.0 access token
        base_url: NetSuite base URL
        output_file: Optional CSV file to export results
        verbose: Show detailed request/response information
    
    Returns:
        List of invoice records
    """
    suiteql_endpoint = "/services/rest/query/v1/suiteql"
    url = f"{base_url}{suiteql_endpoint}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "transient"
    }
    
    # SuiteQL query to get all open invoices
    # Status 'A' = Open/Approved
    # Type 'CustInvc' = Customer Invoice
    # Note: amount and amountremaining may not be directly available in transaction table
    # We'll get basic fields via SuiteQL, then fetch full details if needed
    
    # Build WHERE clause
    where_clauses = [
        "transaction.type = 'CustInvc'",
        "transaction.status = 'A'"
    ]
    
    # Add year filter if specified (NetSuite date format: M/D/YYYY)
    # If year is 2025, include December 2024 as well
    if year:
        if year == 2025:
            # Include Dec 2024 through Dec 2025
            where_clauses.append(f"transaction.trandate >= '12/1/2024'")
            where_clauses.append(f"transaction.trandate < '1/1/2026'")
        else:
            where_clauses.append(f"transaction.trandate >= '1/1/{year}'")
            where_clauses.append(f"transaction.trandate < '1/1/{year + 1}'")
    
    where_clause = " AND ".join(where_clauses)
    
    # Build SELECT clause
    # Note: Entity joins in SuiteQL are limited, so we'll fetch customer details separately
    # Note: amountremaining may need to be fetched via REST API if not available in SuiteQL
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
    WHERE {where_clause}
    ORDER BY transaction.trandate DESC
    """
    
    query_data = {"q": query.strip()}
    
    all_invoices = []
    offset = 0
    page_size = 1000  # Max per page
    page = 0
    max_pages = 1000  # Safety limit
    
    print("=" * 60)
    print("Get All Open Invoices via SuiteQL")
    print("=" * 60)
    if year == 2025:
        year_filter = " from Dec 2024 - Dec 2025"
    elif year:
        year_filter = f" from {year}"
    else:
        year_filter = ""
    customer_info = " (with customer info)" if include_customer else ""
    print(f"Query: Get all open invoices{year_filter}{customer_info} (status='A', type='CustInvc')")
    print()
    
    if verbose:
        print(f"  SuiteQL Query:")
        print(f"  {query}")
        print(f"  URL: {url}")
        print()
    
    # Start timing
    start_time = time.time()
    
    try:
        while page < max_pages:
            params = {"limit": page_size, "offset": offset}
            
            if verbose:
                print(f"  Fetching page {page + 1} (offset: {offset})...")
            
            # Time each page request
            page_start = time.time()
            response = requests.post(url, headers=headers, json=query_data, params=params)
            page_elapsed = time.time() - page_start
            
            if verbose:
                print(f"    Page {page + 1} fetched in {page_elapsed:.2f} seconds")
            
            if response.status_code != 200:
                print(f"❌ Error: {response.status_code}")
                print(response.text)
                break
            
            data = response.json()
            items = data.get("items", [])
            
            if not items:
                break
            
            all_invoices.extend(items)
            print(f"  ✓ Fetched {len(items)} invoices (total: {len(all_invoices)})")
            
            # Check if there are more results
            has_more = data.get("hasMore", False)
            if not has_more or len(items) < page_size:
                break
            
            offset += page_size
            page += 1
        
        # Calculate elapsed time for SuiteQL query
        query_elapsed = time.time() - start_time
        
        # Fetch additional invoice details (amount remaining) and customer info if requested
        if all_invoices:
            print(f"Fetching invoice details (amount remaining) for {len(all_invoices)} invoices...")
            details_start = time.time()
            all_invoices = fetch_invoice_amounts(access_token, base_url, all_invoices, verbose)
            details_elapsed = time.time() - details_start
            print(f"✓ Invoice amounts fetched in {details_elapsed:.2f} seconds")
            
            if include_customer:
                print(f"Fetching customer information for {len(all_invoices)} invoices...")
                customer_start = time.time()
                all_invoices = fetch_customer_info(access_token, base_url, all_invoices, verbose)
                customer_elapsed = time.time() - customer_start
                print(f"✓ Customer info fetched in {customer_elapsed:.2f} seconds")
            else:
                customer_elapsed = 0
            print()
        
        # Calculate total elapsed time
        total_elapsed = time.time() - start_time
        
        print()
        print(f"✓ Total open invoices found: {len(all_invoices)}")
        print(f"✓ SuiteQL query time: {query_elapsed:.2f} seconds ({query_elapsed/60:.2f} minutes)")
        print(f"✓ Invoice amounts fetch time: {details_elapsed:.2f} seconds")
        if include_customer:
            print(f"✓ Customer fetch time: {customer_elapsed:.2f} seconds")
        print(f"✓ Total time elapsed: {total_elapsed:.2f} seconds ({total_elapsed/60:.2f} minutes)")
        print(f"✓ Average: {len(all_invoices)/total_elapsed:.1f} invoices/second")
        print()
        
        # Export to CSV if requested
        if output_file:
            export_to_csv(all_invoices, output_file, verbose)
        
        return all_invoices
        
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return []


def export_to_csv(invoices: List[Dict[str, Any]], output_file: str, verbose: bool = False):
    """Export invoices to CSV file"""
    if not invoices:
        print("⚠️  No invoices to export")
        return
    
    print(f"Exporting {len(invoices)} invoices to {output_file}...")
    
    # Get all unique keys from all invoices, excluding removed fields
    excluded_fields = {"currency", "email", "phone", "links"}
    all_keys = set()
    for invoice in invoices:
        all_keys.update(k for k in invoice.keys() if k not in excluded_fields)
    
    # Define preferred column order
    preferred_order = ["id", "tranid", "status", "trandate", "duedate", "entity", "companyname", 
                       "amountremaining", "subsidiary"]
    # Sort keys: preferred order first, then others alphabetically
    fieldnames = [k for k in preferred_order if k in all_keys]
    fieldnames.extend(sorted(all_keys - set(fieldnames)))
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for invoice in invoices:
                # Convert dict/list values to strings for CSV
                row = {}
                for key in fieldnames:
                    value = invoice.get(key)
                    if isinstance(value, (dict, list)):
                        row[key] = json.dumps(value)
                    else:
                        row[key] = value
                writer.writerow(row)
        
        print(f"✓ Exported to {output_file}")
        print()
        
        if verbose:
            print("Sample invoice data (first invoice):")
            print(json.dumps(invoices[0], indent=2))
            print()
        
        # Print summary
        print("Summary:")
        print(f"  Total invoices: {len(invoices)}")
        if invoices:
            total_amount = sum(float(inv.get('amount', 0) or 0) for inv in invoices)
            total_remaining = sum(float(inv.get('amountremaining', 0) or 0) for inv in invoices)
            print(f"  Total amount: ${total_amount:,.2f}")
            print(f"  Total remaining: ${total_remaining:,.2f}")
            print()
    
    except Exception as e:
        print(f"❌ Error exporting to CSV: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Access token - get from environment variable or command line
    access_token = os.getenv('NETSUITE_ACCESS_TOKEN', None)
    
    output_file = "all_open_invoices_suiteql.csv"
    verbose = False
    year = None
    include_customer = True
    
    # Parse command line arguments
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--token" and i + 1 < len(sys.argv):
            access_token = sys.argv[i + 1]
            i += 2
        elif arg == "--output" and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            i += 2
        elif arg == "--year" and i + 1 < len(sys.argv):
            year = int(sys.argv[i + 1])
            i += 2
        elif arg == "--no-customer":
            include_customer = False
            i += 1
        elif arg == "--verbose" or arg == "-v":
            verbose = True
            i += 1
        else:
            i += 1
    
    if not access_token:
        print("❌ Error: Access token required")
        print()
        print("Usage:")
        print("  python get_all_open_invoices_suiteql.py --token <access_token> [--output filename.csv] [--verbose]")
        print()
        print("Or set NETSUITE_ACCESS_TOKEN environment variable:")
        print("  export NETSUITE_ACCESS_TOKEN='your_token_here'")
        print("  python get_all_open_invoices_suiteql.py [--output filename.csv] [--verbose]")
        print()
        sys.exit(1)
    
    print("Usage:")
    print("  python get_all_open_invoices_suiteql.py --token <access_token> [--output filename.csv] [--year 2025] [--no-customer] [--verbose]")
    print()
    
    query_all_open_invoices_suiteql(
        access_token=access_token,
        output_file=output_file,
        year=year,
        include_customer=include_customer,
        verbose=verbose
    )

