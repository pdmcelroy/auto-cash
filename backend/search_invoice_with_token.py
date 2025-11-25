#!/usr/bin/env python3
"""
Search NetSuite invoices using access token (Step 3 from NETSUITE_OAUTH_IMPLEMENTATION_GUIDE)
Exports all invoice fields to CSV
"""
import requests
import csv
import sys
import json
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


def search_invoice_and_export(access_token: str, invoice_number: str, output_file: str = None):
    """
    Search for invoice using access token and export to CSV
    Follows Step 3 from NETSUITE_OAUTH_IMPLEMENTATION_GUIDE
    """
    if output_file is None:
        output_file = f"invoice_{invoice_number}_results.csv"
    
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
    
    # Try multiple query formats - NetSuite REST API query syntax can vary
    query_formats = [
        {"q": f"tranid={invoice_number}", "limit": 1000},
        {"q": f"tranid IS '{invoice_number}'", "limit": 1000},
        {"q": f"tranid:'{invoice_number}'", "limit": 1000},
        {"limit": 1000, "fields": "tranid,id,entity,amount,status"}  # Get all, filter client-side
    ]
    
    # Start with first format
    params = query_formats[0]
    
    print("=" * 60)
    print("NetSuite Invoice Search (Step 3)")
    print("=" * 60)
    print(f"Searching for invoice number: {invoice_number}")
    print(f"URL: {url}")
    print(f"Query Parameters: {params}")
    print(f"Headers: Authorization: Bearer {access_token[:50]}...")
    print()
    
    try:
        # Make GET request
        response = requests.get(url, headers=headers, params=params)
        
        print(f"Response Status: {response.status_code}")
        print()
        
        if response.status_code == 200:
            print("✓ SUCCESS!")
            data = response.json()
            
            # Get items from response
            items = data.get("items", [])
            print(f"Found {len(items)} invoice item(s) in response")
            
            # If we got all invoices, filter by invoice number client-side
            if params.get("q") is None or "tranid" not in params.get("q", ""):
                print(f"Filtering {len(items)} invoices for tranid={invoice_number}...")
                filtered_items = []
                for item in items:
                    # Check if tranid matches (could be in different formats)
                    item_tranid = item.get("tranid", "")
                    if str(item_tranid) == str(invoice_number):
                        filtered_items.append(item)
                items = filtered_items
                print(f"Found {len(items)} matching invoice(s) after filtering")
            
            if not items:
                print("No invoices found. Writing empty CSV.")
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["message", "No invoices found"])
                return
            
            # Flatten all items and collect all possible fieldnames
            flattened_items = []
            all_fieldnames = set()
            
            for item in items:
                flattened = flatten_dict(item)
                flattened_items.append(flattened)
                all_fieldnames.update(flattened.keys())
            
            # Sort fieldnames for consistent output
            fieldnames = sorted(all_fieldnames)
            
            # Write to CSV
            print(f"\nWriting {len(flattened_items)} invoice(s) with {len(fieldnames)} fields to {output_file}...")
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for item in flattened_items:
                    # Fill in missing fields with empty strings
                    row = {field: item.get(field, "") for field in fieldnames}
                    writer.writerow(row)
            
            print(f"✓ Successfully exported {len(flattened_items)} invoice(s) to {output_file}")
            
            # Print summary of key fields
            print("\nSummary:")
            for i, item in enumerate(items, 1):
                tranid = item.get("tranid", "N/A")
                entity = item.get("entity", {})
                if isinstance(entity, dict):
                    customer = entity.get("name", "N/A")
                else:
                    customer = str(entity) if entity else "N/A"
                amount = item.get("amount", "N/A")
                status = item.get("status", "N/A")
                invoice_id = item.get("id", "N/A")
                
                print(f"{i}. ID: {invoice_id} | Invoice: {tranid} | Customer: {customer} | "
                      f"Amount: {amount} | Status: {status}")
            
            # Also print full JSON for reference
            print("\n" + "=" * 60)
            print("Full JSON Response (first item):")
            print("=" * 60)
            if items:
                print(json.dumps(items[0], indent=2))
            
        elif response.status_code == 400 and "Invalid search query" in response.text:
            # Try fallback: get all invoices and filter client-side with pagination
            print("Query format not supported. Trying to fetch invoices with pagination and filter client-side...")
            all_items = []
            offset = 0
            limit = 1000
            max_pages = 10  # Limit to prevent too many requests
            
            for page in range(max_pages):
                params = {"limit": limit, "offset": offset}
                print(f"Fetching page {page + 1} (offset {offset})...")
                response = requests.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    page_items = data.get("items", [])
                    all_items.extend(page_items)
                    
                    # Check if there are more pages
                    has_more = data.get("hasMore", False)
                    total_results = data.get("totalResults", 0)
                    
                    print(f"  Got {len(page_items)} items (total so far: {len(all_items)}/{total_results})")
                    
                    if not has_more or len(page_items) == 0:
                        break
                    
                    offset += limit
                else:
                    print(f"  Error on page {page + 1}: {response.status_code}")
                    break
            
            if all_items:
                print(f"✓ SUCCESS (fallback method)! Fetched {len(all_items)} total invoices")
                
                # Filter by invoice number - need to fetch full details to get tranid
                print(f"Checking invoices for tranid={invoice_number}...")
                print("Note: List endpoint may not include tranid. Fetching full details for matches...")
                filtered_items = []
                
                # First, try to find in items that have tranid
                for item in all_items:
                    item_tranid = item.get("tranid", "")
                    if item_tranid and str(item_tranid) == str(invoice_number):
                        filtered_items.append(item)
                        print(f"  Found match: tranid={item_tranid}, id={item.get('id', 'N/A')}")
                
                # If no matches and we have invoice IDs, try fetching full details for a sample
                if not filtered_items and len(all_items) > 0:
                    print(f"  No tranid in list response. Trying to fetch full details for first few invoices to check format...")
                    # Try fetching full details for first 10 items to see tranid format
                    for item in all_items[:10]:
                        item_id = item.get("id")
                        if item_id:
                            detail_url = f"{base_url}/services/rest/record/v1/invoice/{item_id}"
                            detail_response = requests.get(detail_url, headers=headers)
                            if detail_response.status_code == 200:
                                detail_data = detail_response.json()
                                detail_tranid = detail_data.get("tranid", "")
                                print(f"    Sample: id={item_id}, tranid={detail_tranid}")
                                if str(detail_tranid) == str(invoice_number):
                                    filtered_items.append(detail_data)
                                    print(f"  ✓ Found match in details: tranid={detail_tranid}, id={item_id}")
                                    break
                
                # If still no matches, the invoice might not be in the fetched set
                if not filtered_items:
                    print(f"  Invoice {invoice_number} not found in first {len(all_items)} invoices.")
                    print(f"  Total available: {data.get('totalResults', 'unknown')} invoices")
                    print(f"  You may need to search by ID or use a different search method.")
                
                items = filtered_items
                print(f"Found {len(items)} matching invoice(s)")
                
                if not items:
                    print("No invoices found. Writing empty CSV.")
                    with open(output_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(["message", "No invoices found"])
                    return
                
                # Continue with CSV export (code below handles this)
            else:
                print(f"❌ Fallback also failed:")
                print(f"  Status Code: {response.status_code}")
                print(f"  Response Text: {response.text}")
                # Create CSV with error information
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["error", "status_code", "message"])
                    writer.writerow(["api_error", response.status_code, response.text[:500]])
                return
        else:
            print(f"❌ Error Response:")
            print(f"  Status Code: {response.status_code}")
            print(f"  Response Text: {response.text}")
            try:
                error_json = response.json()
                print(f"  Error JSON: {json.dumps(error_json, indent=2)}")
            except:
                pass
            
            # Create CSV with error information
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["error", "status_code", "message"])
                writer.writerow(["api_error", response.status_code, response.text[:500]])
            return
        
        # CSV export code continues here (for successful responses)
        if response.status_code == 200:
            data = response.json() if not isinstance(data, dict) else data
            items = data.get("items", []) if isinstance(data, dict) else items
        
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        
        # Create CSV with error information
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["error", "message"])
            writer.writerow(["exception", str(e)])


if __name__ == "__main__":
    # Access token from user (full token)
    access_token = "eyJraWQiOiJjLjQwODMwOTFfU0IyLjIwMjUtMTAtMDRfMDItMzAtNTQiLCJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIzOzgzMzg2IiwiYXVkIjpbIkEyQTNBQUMzLUQwRTgtNDU4MS1BRUI5LTBCNTU5NUQ4QjVCMDs0MDgzMDkxX1NCMiIsIjRjMDYzYjA5MjlkNDVjY2YyNWU4MjBlMjZmNmI5ODFmMTBmNmU1Nzk2MGYwN2M0YmFhMzNjNjlmNmZhZDEyZDYiXSwic2NvcGUiOlsicmVzdF93ZWJzZXJ2aWNlcyJdLCJpc3MiOiJodHRwczovL3N5c3RlbS5uZXRzdWl0ZS5jb20iLCJvaXQiOjE3NjQwOTI3NDYsImV4cCI6MTc2NDA5NjM0NiwiaWF0IjoxNzY0MDkyNzQ2LCJqdGkiOiI0MDgzMDkxX1NCMi5hLWMubnVsbC4xNzY0MDkyNzQ2MDE0In0.m525UIDjKnt2P7JtdhRN7nv7DDxI5dSpLXtIThiQrFiACIGdCUZtKit4_hPHcMBsKqjJ3Ww998GRVeqANFaXZH84WcaGaDCWpgvXK8w9o6mXJ3m5iySgXa91Y-rEPqZ9hfvoozsNLUByMhcLYOSLEbi_gZlDWf5BicP2EtEIL6r891eXn4Ec9I9Sk6JVq0HSUbN8tkVA2F1l8S6SGR7bzD_QFQnPVDqMx0WqoqQXA_SfvWTzVxVd_X76gr4Dxxi7TnrP6quny0uqh5EKOIZSvNkHyauiTnvE2rQHGfWTOFjcFaC-QrTTPnoJzO9PUclc9dX6cgxpuhMGcyYFZ-WbodMabYnwwHcCJS-1tLVR3auoi9I-7iFw45kBBVyXAQPt305kYCAdw3JR8h3R_Oigg_ddI37IK5AXiQQTcPZapt6cbMkSNBcoUpeDSS1Lg9TJjQM5YZO0E0ijpYWlAl0Yjd1yQM8gdn5whRD20lkJZL5bR5gp-p4ug2q8r8d-rcDe32KrEQANQ8Z7aHcI06gKzPSVggDwaOok6RRtPY62s4UOsTS4xoY7hJXX3rfm6XH8o5BBo7x_9SjPb7TPfpFfFiujArhniEOQOXyNWOX7Y4fHhBlpnnXzEuAOLm0ZxoV_D5xkn5nOqtRVElxkcq7gQI_FlDr3cTX6ONAszgjPB9Q"
    
    # Invoice number to search
    invoice_number = "205449"
    
    # Allow override via command line
    if len(sys.argv) > 1:
        invoice_number = sys.argv[1]
    
    output_file = f"invoice_{invoice_number}_all_fields.csv"
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    # Allow access token override via command line
    if len(sys.argv) > 3:
        access_token = sys.argv[3]
    
    search_invoice_and_export(access_token, invoice_number, output_file)

