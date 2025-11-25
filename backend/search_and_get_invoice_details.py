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
                   customer_name: Optional[str] = None) -> List[Dict]:
    """Filter invoices based on criteria"""
    filtered = []
    
    for invoice in invoices:
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
    
    return filtered


def search_and_get_invoice_details(access_token: str,
                                  output_file: str = "filtered_invoices_details.csv",
                                  min_amount: Optional[float] = None,
                                  max_amount: Optional[float] = None,
                                  start_date: Optional[str] = None,
                                  end_date: Optional[str] = None,
                                  customer_name: Optional[str] = None,
                                  limit: int = 1000,
                                  max_invoices_to_fetch: int = 10000):
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
    print()
    
    # Step 1: Fetch invoice list
    print("Step 1: Fetching invoice list...")
    all_invoice_ids = []
    offset = 0
    max_pages = (max_invoices_to_fetch // limit) + 1
    
    for page in range(max_pages):
        params = {"limit": limit, "offset": offset}
        print(f"  Fetching page {page + 1} (offset {offset})...")
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            page_items = data.get("items", [])
            
            for item in page_items:
                invoice_id = item.get("id")
                if invoice_id:
                    all_invoice_ids.append(invoice_id)
            
            has_more = data.get("hasMore", False)
            total_results = data.get("totalResults", 0)
            
            print(f"    Got {len(page_items)} items (total IDs: {len(all_invoice_ids)}/{total_results})")
            
            if not has_more or len(page_items) == 0 or len(all_invoice_ids) >= max_invoices_to_fetch:
                break
            
            offset += limit
        else:
            print(f"    Error: {response.status_code}")
            break
    
    print(f"\n✓ Fetched {len(all_invoice_ids)} invoice IDs")
    
    # Step 2: Get detailed information for each invoice
    print(f"\nStep 2: Getting detailed information for {len(all_invoice_ids)} invoices...")
    all_invoices = []
    
    for i, invoice_id in enumerate(all_invoice_ids, 1):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(all_invoice_ids)}")
        
        details = get_invoice_details(access_token, base_url, invoice_id)
        if details:
            all_invoices.append(details)
    
    print(f"✓ Got detailed information for {len(all_invoices)} invoices")
    
    # Step 3: Filter invoices
    print(f"\nStep 3: Filtering invoices...")
    filtered_invoices = filter_invoices(
        all_invoices,
        min_amount=min_amount,
        max_amount=max_amount,
        start_date=start_date,
        end_date=end_date,
        customer_name=customer_name
    )
    
    print(f"✓ Found {len(filtered_invoices)} matching invoice(s)")
    
    if not filtered_invoices:
        print("\n❌ No invoices match the filter criteria.")
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["message", "No invoices match the filter criteria"])
        return
    
    # Step 4: Export to CSV
    print(f"\nStep 4: Exporting to CSV...")
    
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
    access_token = "eyJraWQiOiJjLjQwODMwOTFfU0IyLjIwMjUtMTAtMDRfMDItMzAtNTQiLCJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIzOzgzMzg2IiwiYXVkIjpbIkEyQTNBQUMzLUQwRTgtNDU4MS1BRUI5LTBCNTU5NUQ4QjVCMDs0MDgzMDkxX1NCMiIsIjRjMDYzYjA5MjlkNDVjY2YyNWU4MjBlMjZmNmI5ODFmMTBmNmU1Nzk2MGYwN2M0YmFhMzNjNjlmNmZhZDEyZDYiXSwic2NvcGUiOlsicmVzdF93ZWJzZXJ2aWNlcyJdLCJpc3MiOiJodHRwczovL3N5c3RlbS5uZXRzdWl0ZS5jb20iLCJvaXQiOjE3NjQwOTI3NDYsImV4cCI6MTc2NDA5NjM0NiwiaWF0IjoxNzY0MDkyNzQ2LCJqdGkiOiI0MDgzMDkxX1NCMi5hLWMubnVsbC4xNzY0MDkyNzQ2MDE0In0.m525UIDjKnt2P7JtdhRN7nv7DDxI5dSpLXtIThiQrFiACIGdCUZtKit4_hPHcMBsKqjJ3Ww998GRVeqANFaXZH84WcaGaDCWpgvXK8w9o6mXJ3m5iySgXa91Y-rEPqZ9hfvoozsNLUByMhcLYOSLEbi_gZlDWf5BicP2EtEIL6r891eXn4Ec9I9Sk6JVq0HSUbN8tkVA2F1l8S6SGR7bzD_QFQnPVDqMx0WqoqQXA_SfvWTzVxVd_X76gr4Dxxi7TnrP6quny0uqh5EKOIZSvNkHyauiTnvE2rQHGfWTOFjcFaC-QrTTPnoJzO9PUclc9dX6cgxpuhMGcyYFZ-WbodMabYnwwHcCJS-1tLVR3auoi9I-7iFw45kBBVyXAQPt305kYCAdw3JR8h3R_Oigg_ddI37IK5AXiQQTcPZapt6cbMkSNBcoUpeDSS1Lg9TJjQM5YZO0E0ijpYWlAl0Yjd1yQM8gdn5whRD20lkJZL5bR5gp-p4ug2q8r8d-rcDe32KrEQANQ8Z7aHcI06gKzPSVggDwaOok6RRtPY62s4UOsTS4xoY7hJXX3rfm6XH8o5BBo7x_9SjPb7TPfpFfFiujArhniEOQOXyNWOX7Y4fHhBlpnnXzEuAOLm0ZxoV_D5xkn5nOqtRVElxkcq7gQI_FlDr3cTX6ONAszgjPB9Q"
    
    # Parse command line arguments
    output_file = "filtered_invoices_details.csv"
    min_amount = None
    max_amount = None
    start_date = None
    end_date = None
    customer_name = None
    
    # Simple argument parsing
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--min-amount" and i + 1 < len(sys.argv):
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
        elif arg == "--output" and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    
    print("Usage examples:")
    print("  python search_and_get_invoice_details.py --min-amount 1000 --max-amount 5000")
    print("  python search_and_get_invoice_details.py --start-date 2024-01-01 --end-date 2024-12-31")
    print("  python search_and_get_invoice_details.py --customer 'Amazon' --min-amount 10000")
    print()
    
    search_and_get_invoice_details(
        access_token,
        output_file=output_file,
        min_amount=min_amount,
        max_amount=max_amount,
        start_date=start_date,
        end_date=end_date,
        customer_name=customer_name
    )

