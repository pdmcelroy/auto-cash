#!/usr/bin/env python3
"""
Get invoices from NetSuite and export to CSV (Step 3 from NETSUITE_OAUTH_IMPLEMENTATION_GUIDE)
"""
import requests
import csv
import json
import sys
from pathlib import Path


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


def get_invoices_and_export(access_token: str, output_file: str = "invoices_export.csv", limit: int = 1000):
    """
    Get invoices from NetSuite and export to CSV
    Follows Step 3 from NETSUITE_OAUTH_IMPLEMENTATION_GUIDE
    """
    # Base URL from guide
    base_url = "https://4083091-sb2.suitetalk.api.netsuite.com"
    
    # Invoice endpoint
    endpoint = "/services/rest/record/v1/invoice"
    
    # Full URL
    url = f"{base_url}{endpoint}"
    
    # Headers as specified in Step 3
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "transient"
    }
    
    # Query parameters
    params = {
        "limit": limit,
        "offset": 0
    }
    
    print("=" * 60)
    print("NetSuite Invoices Export (Step 3)")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Query Parameters: {params}")
    print(f"Headers: Authorization: Bearer {access_token[:50]}...")
    print()
    
    all_items = []
    offset = 0
    max_pages = 100  # Safety limit
    
    try:
        for page in range(max_pages):
            params = {"limit": limit, "offset": offset}
            print(f"Fetching page {page + 1} (offset {offset})...")
            
            response = requests.get(url, headers=headers, params=params)
            
            print(f"  Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                page_items = data.get("items", [])
                all_items.extend(page_items)
                
                # Check if there are more pages
                has_more = data.get("hasMore", False)
                total_results = data.get("totalResults", 0)
                
                print(f"  Got {len(page_items)} items (total so far: {len(all_items)}/{total_results})")
                
                if not has_more or len(page_items) == 0:
                    print(f"  No more pages. Total fetched: {len(all_items)}")
                    break
                
                offset += limit
            else:
                print(f"  Error on page {page + 1}: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                break
        
        if not all_items:
            print("\n❌ No invoices found.")
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["message", "No invoices found"])
            return
        
        print(f"\n✓ Successfully fetched {len(all_items)} invoice(s)")
        
        # Flatten all items and collect all possible fieldnames
        flattened_items = []
        all_fieldnames = set()
        
        print("Processing invoice data...")
        for item in all_items:
            flattened = flatten_dict(item)
            flattened_items.append(flattened)
            all_fieldnames.update(flattened.keys())
        
        # Sort fieldnames for consistent output
        fieldnames = sorted(all_fieldnames)
        
        # Write to CSV
        print(f"Writing {len(flattened_items)} invoice(s) with {len(fieldnames)} fields to {output_file}...")
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for item in flattened_items:
                # Fill in missing fields with empty strings
                row = {field: item.get(field, "") for field in fieldnames}
                writer.writerow(row)
        
        print(f"✓ Successfully exported {len(flattened_items)} invoice(s) to {output_file}")
        print(f"  Total fields: {len(fieldnames)}")
        print(f"  Output file: {Path(output_file).absolute()}")
        
        # Print summary of first few invoices
        print("\nSummary (first 5 invoices):")
        for i, item in enumerate(all_items[:5], 1):
            tranid = item.get("tranid", "N/A")
            invoice_id = item.get("id", "N/A")
            entity = item.get("entity", {})
            if isinstance(entity, dict):
                customer = entity.get("name", "N/A")
            else:
                customer = str(entity) if entity else "N/A"
            amount = item.get("amount", "N/A")
            
            print(f"  {i}. ID: {invoice_id} | Invoice: {tranid} | Customer: {customer} | Amount: {amount}")
        
    except Exception as e:
        print(f"\n❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        
        # Create CSV with error information
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["error", "message"])
            writer.writerow(["exception", str(e)])


if __name__ == "__main__":
    # Access token from user
    access_token = "eyJraWQiOiJjLjQwODMwOTFfU0IyLjIwMjUtMTAtMDRfMDItMzAtNTQiLCJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIzOzgzMzg2IiwiYXVkIjpbIkEyQTNBQUMzLUQwRTgtNDU4MS1BRUI5LTBCNTU5NUQ4QjVCMDs0MDgzMDkxX1NCMiIsIjRjMDYzYjA5MjlkNDVjY2YyNWU4MjBlMjZmNmI5ODFmMTBmNmU1Nzk2MGYwN2M0YmFhMzNjNjlmNmZhZDEyZDYiXSwic2NvcGUiOlsicmVzdF93ZWJzZXJ2aWNlcyJdLCJpc3MiOiJodHRwczovL3N5c3RlbS5uZXRzdWl0ZS5jb20iLCJvaXQiOjE3NjQwOTI3NDYsImV4cCI6MTc2NDA5NjM0NiwiaWF0IjoxNzY0MDkyNzQ2LCJqdGkiOiI0MDgzMDkxX1NCMi5hLWMubnVsbC4xNzY0MDkyNzQ2MDE0In0.m525UIDjKnt2P7JtdhRN7nv7DDxI5dSpLXtIThiQrFiACIGdCUZtKit4_hPHcMBsKqjJ3Ww998GRVeqANFaXZH84WcaGaDCWpgvXK8w9o6mXJ3m5iySgXa91Y-rEPqZ9hfvoozsNLUByMhcLYOSLEbi_gZlDWf5BicP2EtEIL6r891eXn4Ec9I9Sk6JVq0HSUbN8tkVA2F1l8S6SGR7bzD_QFQnPVDqMx0WqoqQXA_SfvWTzVxVd_X76gr4Dxxi7TnrP6quny0uqh5EKOIZSvNkHyauiTnvE2rQHGfWTOFjcFaC-QrTTPnoJzO9PUclc9dX6cgxpuhMGcyYFZ-WbodMabYnwwHcCJS-1tLVR3auoi9I-7iFw45kBBVyXAQPt305kYCAdw3JR8h3R_Oigg_ddI37IK5AXiQQTcPZapt6cbMkSNBcoUpeDSS1Lg9TJjQM5YZO0E0ijpYWlAl0Yjd1yQM8gdn5whRD20lkJZL5bR5gp-p4ug2q8r8d-rcDe32KrEQANQ8Z7aHcI06gKzPSVggDwaOok6RRtPY62s4UOsTS4xoY7hJXX3rfm6XH8o5BBo7x_9SjPb7TPfpFfFiujArhniEOQOXyNWOX7Y4fHhBlpnnXzEuAOLm0ZxoV_D5xkn5nOqtRVElxkcq7gQI_FlDr3cTX6ONAszgjPB9Q"
    
    # Output file
    output_file = "invoices_export.csv"
    
    # Allow override via command line
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    
    if len(sys.argv) > 2:
        access_token = sys.argv[2]
    
    get_invoices_and_export(access_token, output_file)

