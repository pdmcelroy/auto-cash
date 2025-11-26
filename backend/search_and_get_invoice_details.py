#!/usr/bin/env python3
"""
Search/filter invoices and get detailed information for each match
Uses Step 3 from NETSUITE_OAUTH_IMPLEMENTATION_GUIDE
"""
import requests
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


def flatten_dict(d, parent_key='', sep='_'):
    """Flatten nested dictionary"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Convert lists to string representation
            items.append((new_key, str(v)))
        else:
            items.append((new_key, v))
    return dict(items)


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime object"""
    if not date_str:
        return None
    try:
        # Try common date formats
        for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y']:
            try:
                return datetime.strptime(date_str.split('T')[0], fmt)
            except:
                continue
    except:
        pass
    return None


def query_invoices_suiteql(access_token: str, base_url: str,
                           status: Optional[str] = None,
                           min_amount: Optional[float] = None,
                           max_amount: Optional[float] = None,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           customer_name: Optional[str] = None,
                           max_results: int = 10,
                           verbose: bool = False) -> List[Dict[str, Any]]:
    """
    Query invoices using SuiteQL (much faster than individual API calls)
    Reference: https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_157909186990.html
    """
    suiteql_endpoint = "/services/rest/query/v1/suiteql"
    url = f"{base_url}{suiteql_endpoint}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "transient"
    }
    
    # Build SuiteQL query
    # Note: Field names in SuiteQL may differ from REST API field names
    # Common fields: id, tranid (invoice number), entity (customer), amount, status, trandate, duedate
    where_clauses = []
    
    if status:
        # Status in SuiteQL is typically a single letter code
        # 'A' = Open/Approved, 'B' = Closed, 'C' = Pending Approval, etc.
        # Map common status names to codes
        status_map = {
            'open': 'A',
            'closed': 'B',
            'pending': 'C',
            'approved': 'A'
        }
        status_code = status_map.get(status.lower(), status)
        # If user provided a single letter, use it directly; otherwise use mapping
        if len(status) == 1:
            where_clauses.append(f"transaction.status = '{status}'")
        else:
            # Use the mapped code
            where_clauses.append(f"transaction.status = '{status_code}'")
    
    if min_amount is not None:
        where_clauses.append(f"transaction.amount >= {min_amount}")
    
    if max_amount is not None:
        where_clauses.append(f"transaction.amount <= {max_amount}")
    
    if start_date:
        where_clauses.append(f"transaction.trandate >= '{start_date}'")
    
    if end_date:
        where_clauses.append(f"transaction.trandate <= '{end_date}'")
    
    if customer_name:
        # Join with customer/entity table if needed
        where_clauses.append(f"transaction.entity LIKE '%{customer_name}%'")
    
    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # Build SELECT query - SuiteQL has limited fields available
    # We'll use SuiteQL to get IDs, then fetch full details via REST API
    # Transaction type for invoices is 'CustInvc' (not 'CustInv')
    # Status is typically a single letter: 'A' = Open/Approved, 'B' = Closed, etc.
    query = f"""
    SELECT 
        transaction.id,
        transaction.tranid,
        transaction.status,
        transaction.trandate
    FROM transaction
    WHERE transaction.type = 'CustInvc'
    AND {where_clause}
    ORDER BY transaction.trandate DESC
    """
    
    query_data = {"q": query.strip()}
    
    params = {"limit": max_results, "offset": 0}
    
    if verbose:
        print(f"  SuiteQL Query:")
        print(f"  {query}")
        print(f"  URL: {url}")
        print(f"  Params: {params}")
        print()
    
    try:
        response = requests.post(url, headers=headers, json=query_data, params=params)
        
        if verbose:
            print(f"  Response Status: {response.status_code}")
            print(f"  Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            
            if verbose:
                print(f"  Response Data:")
                print(json.dumps(data, indent=2))
                print()
            
            print(f"✓ SuiteQL query returned {len(items)} invoice(s)")
            
            if verbose:
                print(f"\n  SuiteQL Results (first 5):")
                for item in items[:5]:
                    print(f"    ID: {item.get('id')}, tranid: {item.get('tranid')}, status: {item.get('status')}")
                print()
            
            # Get full details for each invoice ID from SuiteQL results
            print(f"  Fetching full details for {len(items)} invoices...")
            invoices = []
            for i, item in enumerate(items, 1):
                invoice_id = item.get("id")
                if not invoice_id:
                    continue
                
                if verbose and i <= 5:
                    print(f"    Fetching details for invoice {i}/{len(items)}: ID={invoice_id}")
                
                # Get full details via REST API
                details = get_invoice_details(access_token, base_url, str(invoice_id))
                if details:
                    invoices.append(details)
                    if verbose and i <= 5:
                        print(f"      ✓ Got details: tranid={details.get('tranid', 'N/A')}, amount={details.get('amount', 'N/A')}")
                elif verbose:
                    print(f"    ⚠️  Could not get details for invoice {invoice_id}")
            
            print(f"✓ Got full details for {len(invoices)} invoice(s)")
            return invoices
        else:
            print(f"  ❌ SuiteQL query failed: {response.status_code}")
            if verbose:
                print(f"  Response: {response.text}")
            return []
    except Exception as e:
        print(f"  ❌ Error executing SuiteQL query: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return []


def get_invoice_details(access_token: str, base_url: str, invoice_id: str) -> Optional[Dict[str, Any]]:
    """Get detailed information for a specific invoice"""
    endpoint = f"/services/rest/record/v1/invoice/{invoice_id}"
    url = f"{base_url}{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "transient"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  Warning: Failed to get details for invoice {invoice_id}: {response.status_code}")
            return None
    except Exception as e:
        print(f"  Error getting details for invoice {invoice_id}: {e}")
        return None


def filter_invoices(invoices: List[Dict], 
                   min_amount: Optional[float] = None,
                   max_amount: Optional[float] = None,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None,
                   customer_name: Optional[str] = None,
                   status: Optional[str] = None,
                   max_results: Optional[int] = None) -> List[Dict]:
    """Filter invoices based on criteria"""
    filtered = []
    
    for invoice in invoices:
        # Status filter (check status field - typically "Open", "Closed", etc.)
        if status:
            invoice_status = invoice.get("status", "")
            if isinstance(invoice_status, dict):
                invoice_status = invoice_status.get("name", "")
            if str(invoice_status).lower() != str(status).lower():
                continue
        
        # Amount filter
        if min_amount is not None or max_amount is not None:
            amount = invoice.get("amount")
            if amount is None:
                continue
            try:
                amount_float = float(amount)
                if min_amount is not None and amount_float < min_amount:
                    continue
                if max_amount is not None and amount_float > max_amount:
                    continue
            except (ValueError, TypeError):
                continue
        
        # Date filter (check trandate, duedate, or createddate)
        if start_date or end_date:
            date_match = False
            for date_field in ["trandate", "duedate", "createddate", "lastmodifieddate"]:
                date_val = invoice.get(date_field)
                if date_val:
                    date_obj = parse_date(str(date_val))
                    if date_obj:
                        if start_date:
                            start_obj = parse_date(start_date)
                            if start_obj and date_obj < start_obj:
                                continue
                        if end_date:
                            end_obj = parse_date(end_date)
                            if end_obj and date_obj > end_obj:
                                continue
                        date_match = True
                        break
            if not date_match and (start_date or end_date):
                continue
        
        # Customer name filter
        if customer_name:
            entity = invoice.get("entity", {})
            if isinstance(entity, dict):
                customer = entity.get("name", "")
            else:
                customer = str(entity) if entity else ""
            if customer_name.lower() not in customer.lower():
                continue
        
        filtered.append(invoice)
        
        # Stop if we've reached max_results
        if max_results and len(filtered) >= max_results:
            break
    
    return filtered


def search_and_get_invoice_details(access_token: str,
                                  output_file: str = "filtered_invoices_details.csv",
                                  min_amount: Optional[float] = None,
                                  max_amount: Optional[float] = None,
                                  start_date: Optional[str] = None,
                                  end_date: Optional[str] = None,
                                  customer_name: Optional[str] = None,
                                  status: Optional[str] = None,
                                  max_results: int = 10,
                                  limit: int = 100,
                                  max_invoices_to_check: int = 500,
                                  verbose: bool = False,
                                  use_suiteql: bool = True):
    """
    Search invoices with filters and get detailed information for each match
    """
    base_url = "https://4083091-sb2.suitetalk.api.netsuite.com"
    endpoint = "/services/rest/record/v1/invoice"
    url = f"{base_url}{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "transient"
    }
    
    print("=" * 60)
    print("NetSuite Invoice Search & Details Export")
    print("=" * 60)
    print(f"Filters:")
    if status:
        print(f"  - Status: {status}")
    if min_amount is not None:
        print(f"  - Min Amount: ${min_amount:,.2f}")
    if max_amount is not None:
        print(f"  - Max Amount: ${max_amount:,.2f}")
    if start_date:
        print(f"  - Start Date: {start_date}")
    if end_date:
        print(f"  - End Date: {end_date}")
    if customer_name:
        print(f"  - Customer: {customer_name}")
    print(f"  - Max Results: {max_results}")
    print(f"  - Method: {'SuiteQL Query' if use_suiteql else 'REST API List + Details'}")
    print(f"  - Verbose: {verbose}")
    print()
    
    # Use SuiteQL for faster querying with filters
    if use_suiteql:
        print("Step 1: Using SuiteQL query to filter invoices...")
        filtered_invoices = query_invoices_suiteql(
            access_token, base_url,
            status=status,
            min_amount=min_amount,
            max_amount=max_amount,
            start_date=start_date,
            end_date=end_date,
            customer_name=customer_name,
            max_results=max_results,
            verbose=verbose
        )
    else:
        # Original approach: Get details and filter incrementally until we have enough matches
        print("Step 1: Fetching invoice list and checking details incrementally...")
        all_invoice_ids = []
        offset = 0
        max_pages = (max_invoices_to_check // limit) + 1
        filtered_invoices = []
        
        for page in range(max_pages):
            params = {"limit": limit, "offset": offset}
            print(f"  Fetching page {page + 1} (offset {offset})...")
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                page_items = data.get("items", [])
                
                # Get details for each invoice in this page and filter immediately
                print(f"    Checking {len(page_items)} invoices (will stop after finding {max_results} matches)...")
                checked_count = 0
                for item in page_items:
                    invoice_id = item.get("id")
                    if not invoice_id:
                        continue
                    
                    checked_count += 1
                    if checked_count % 10 == 0:
                        print(f"      Progress: checked {checked_count}/{len(page_items)} invoices, found {len(filtered_invoices)}/{max_results} matches...")
                    
                    # Get detailed information
                    details = get_invoice_details(access_token, base_url, invoice_id)
                    if not details:
                        continue
                    
                    # Filter this invoice
                    matches = filter_invoices(
                        [details],
                        min_amount=min_amount,
                        max_amount=max_amount,
                        start_date=start_date,
                        end_date=end_date,
                        customer_name=customer_name,
                        status=status,
                        max_results=1
                    )
                    
                    if matches:
                        filtered_invoices.extend(matches)
                        print(f"    ✓ Match {len(filtered_invoices)}/{max_results}: ID={invoice_id}, "
                              f"tranid={matches[0].get('tranid', 'N/A')}, "
                              f"amount={matches[0].get('amount', 'N/A')}")
                        
                        # Stop if we have enough matches
                        if len(filtered_invoices) >= max_results:
                            print(f"\n✓ Found {len(filtered_invoices)} matching invoices (stopping early)")
                            break
                
                # Check if we should continue
                has_more = data.get("hasMore", False)
                total_results = data.get("totalResults", 0)
                
                if len(filtered_invoices) >= max_results:
                    break
                
                if not has_more or len(page_items) == 0:
                    break
                
                offset += limit
            else:
                print(f"    Error: {response.status_code}")
                if response.status_code == 401:
                    print("    ⚠️  Access token may have expired. You may need to get a new one.")
                break
    
    print(f"\n✓ Found {len(filtered_invoices)} matching invoice(s)")
    
    if not filtered_invoices:
        print("\n❌ No invoices match the filter criteria.")
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["message", "No invoices match the filter criteria"])
        return
    
    # Step 2: Export to CSV
    print(f"\nStep 2: Exporting to CSV...")
    
    # Flatten all items and collect all possible fieldnames
    flattened_items = []
    all_fieldnames = set()
    
    for item in filtered_invoices:
        flattened = flatten_dict(item)
        flattened_items.append(flattened)
        all_fieldnames.update(flattened.keys())
    
    fieldnames = sorted(all_fieldnames)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for item in flattened_items:
            row = {field: item.get(field, "") for field in fieldnames}
            writer.writerow(row)
    
    print(f"✓ Successfully exported {len(filtered_invoices)} invoice(s) to {output_file}")
    print(f"  Total fields: {len(fieldnames)}")
    print(f"  Output file: {Path(output_file).absolute()}")
    
    # Print summary
    print("\nSummary:")
    for i, invoice in enumerate(filtered_invoices[:10], 1):
        tranid = invoice.get("tranid", "N/A")
        invoice_id = invoice.get("id", "N/A")
        entity = invoice.get("entity", {})
        if isinstance(entity, dict):
            customer = entity.get("name", "N/A")
        else:
            customer = str(entity) if entity else "N/A"
        amount = invoice.get("amount", "N/A")
        trandate = invoice.get("trandate", "N/A")
        
        print(f"  {i}. ID: {invoice_id} | Invoice: {tranid} | Customer: {customer} | "
              f"Amount: ${amount} | Date: {trandate}")


if __name__ == "__main__":
    import os
    
    # Get access token from environment variable, command line, or use default (may be expired)
    access_token = os.getenv('NETSUITE_ACCESS_TOKEN', 
        "eyJraWQiOiJjLjQwODMwOTFfU0IyLjIwMjUtMTAtMDRfMDItMzAtNTQiLCJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIzOzgzMzg2IiwiYXVkIjpbIkEyQTNBQUMzLUQwRTgtNDU4MS1BRUI5LTBCNTU5NUQ4QjVCMDs0MDgzMDkxX1NCMiIsIjRjMDYzYjA5MjlkNDVjY2YyNWU4MjBlMjZmNmI5ODFmMTBmNmU1Nzk2MGYwN2M0YmFhMzNjNjlmNmZhZDEyZDYiXSwic2NvcGUiOlsicmVzdF93ZWJzZXJ2aWNlcyJdLCJpc3MiOiJodHRwczovL3N5c3RlbS5uZXRzdWl0ZS5jb20iLCJvaXQiOjE3NjQwOTI3NDYsImV4cCI6MTc2NDA5NjM0NiwiaWF0IjoxNzY0MDkyNzQ2LCJqdGkiOiI0MDgzMDkxX1NCMi5hLWMubnVsbC4xNzY0MDkyNzQ2MDE0In0.m525UIDjKnt2P7JtdhRN7nv7DDxI5dSpLXtIThiQrFiACIGdCUZtKit4_hPHcMBsKqjJ3Ww998GRVeqANFaXZH84WcaGaDCWpgvXK8w9o6mXJ3m5iySgXa91Y-rEPqZ9hfvoozsNLUByMhcLYOSLEbi_gZlDWf5BicP2EtEIL6r891eXn4Ec9I9Sk6JVq0HSUbN8tkVA2F1l8S6SGR7bzD_QFQnPVDqMx0WqoqQXA_SfvWTzVxVd_X76gr4Dxxi7TnrP6quny0uqh5EKOIZSvNkHyauiTnvE2rQHGfWTOFjcFaC-QrTTPnoJzO9PUclc9dX6cgxpuhMGcyYFZ-WbodMabYnwwHcCJS-1tLVR3auoi9I-7iFw45kBBVyXAQPt305kYCAdw3JR8h3R_Oigg_ddI37IK5AXiQQTcPZapt6cbMkSNBcoUpeDSS1Lg9TJjQM5YZO0E0ijpYWlAl0Yjd1yQM8gdn5whRD20lkJZL5bR5gp-p4ug2q8r8d-rcDe32KrEQANQ8Z7aHcI06gKzPSVggDwaOok6RRtPY62s4UOsTS4xoY7hJXX3rfm6XH8o5BBo7x_9SjPb7TPfpFfFiujArhniEOQOXyNWOX7Y4fHhBlpnnXzEuAOLm0ZxoV_D5xkn5nOqtRVElxkcq7gQI_FlDr3cTX6ONAszgjPB9Q")
    
    # Parse command line arguments
    output_file = "filtered_invoices_details.csv"
    min_amount = None
    max_amount = None
    start_date = None
    end_date = None
    customer_name = None
    status = "Open"  # Default to open invoices
    max_results = 10  # Default to 10 invoices
    verbose = False
    use_suiteql = True  # Use SuiteQL by default (much faster)
    
    # Simple argument parsing
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--token" and i + 1 < len(sys.argv):
            access_token = sys.argv[i + 1]
            i += 2
        elif arg == "--min-amount" and i + 1 < len(sys.argv):
            min_amount = float(sys.argv[i + 1])
            i += 2
        elif arg == "--max-amount" and i + 1 < len(sys.argv):
            max_amount = float(sys.argv[i + 1])
            i += 2
        elif arg == "--start-date" and i + 1 < len(sys.argv):
            start_date = sys.argv[i + 1]
            i += 2
        elif arg == "--end-date" and i + 1 < len(sys.argv):
            end_date = sys.argv[i + 1]
            i += 2
        elif arg == "--customer" and i + 1 < len(sys.argv):
            customer_name = sys.argv[i + 1]
            i += 2
        elif arg == "--status" and i + 1 < len(sys.argv):
            status = sys.argv[i + 1]
            i += 2
        elif arg == "--max-results" and i + 1 < len(sys.argv):
            max_results = int(sys.argv[i + 1])
            i += 2
        elif arg == "--output" and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            i += 2
        elif arg == "--verbose" or arg == "-v":
            verbose = True
            i += 1
        elif arg == "--no-suiteql":
            use_suiteql = False
            i += 1
        else:
            i += 1
    
    print("Usage examples:")
    print("  python search_and_get_invoice_details.py --status Open --max-results 10")
    print("  python search_and_get_invoice_details.py --status Open --min-amount 1000 --max-amount 5000")
    print("  python search_and_get_invoice_details.py --status Open --customer 'Amazon'")
    print("  python search_and_get_invoice_details.py --token <NEW_TOKEN> --status Open --max-results 10")
    print("  python search_and_get_invoice_details.py --status Open --max-results 10 --verbose")
    print("  python search_and_get_invoice_details.py --status Open --max-results 10 --no-suiteql")
    print()
    
    print("Usage examples:")
    print("  python search_and_get_invoice_details.py --status Open --max-results 10")
    print("  python search_and_get_invoice_details.py --status Open --min-amount 1000 --max-amount 5000")
    print("  python search_and_get_invoice_details.py --status Open --customer 'Amazon'")
    print()
    
    search_and_get_invoice_details(
        access_token,
        output_file=output_file,
        min_amount=min_amount,
        max_amount=max_amount,
        start_date=start_date,
        end_date=end_date,
        customer_name=customer_name,
        status=status,
        max_results=max_results,
        verbose=verbose,
        use_suiteql=use_suiteql
    )

