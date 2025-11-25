#!/usr/bin/env python3
"""
Test script to make a GET request to NetSuite invoices endpoint using access token
"""
import requests
import csv
import sys
from pathlib import Path

def make_netsuite_api_request(access_token: str, account_id: str, endpoint: str, params: dict = None):
    """
    Make an authenticated GET request to NetSuite REST API
    
    Args:
        access_token: OAuth 2.0 access token
        account_id: NetSuite account ID (e.g., "4083091-sb2")
        endpoint: API endpoint (e.g., "/record/v1/metadata-catalog")
        params: Optional query parameters
        
    Returns:
        Response object
    """
    # Construct the base URL
    if '_' in account_id or '-' in account_id:
        # Sandbox account
        account_id_url = account_id.replace('_', '-').lower()
        base_url = f"https://{account_id_url}.suitetalk.api.netsuite.com"
    else:
        # Production account
        base_url = f"https://{account_id}.suitetalk.api.netsuite.com"
    
    url = f"{base_url}{endpoint}"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Prefer': 'transient'  # Optional: for transient responses
    }
    
    print("=" * 60)
    print("NetSuite API Request")
    print("=" * 60)
    print(f"URL: {url}")
    if params:
        print(f"Query Parameters: {params}")
    print(f"Headers: Authorization: Bearer {access_token[:50]}...")
    print()
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            print("✓ SUCCESS!")
            try:
                data = response.json()
                return data
            except:
                print(f"Response Text: {response.text[:500]}")
                return None
        else:
            print(f"❌ Error Response:")
            print(f"  Status Code: {response.status_code}")
            print(f"  Response Text: {response.text}")
            try:
                error_json = response.json()
                import json
                print(f"  Error JSON: {json.dumps(error_json, indent=2)}")
            except:
                pass
            return None
        
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return None


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


def search_invoice_and_export(access_token: str, account_id: str, invoice_number: str, output_file: str = None):
    """Search for invoice and export to CSV"""
    if output_file is None:
        output_file = f"invoice_{invoice_number}_results.csv"
    
    print(f"Searching for invoice number: {invoice_number}")
    print()
    
    # Search invoices endpoint
    endpoint = "/services/rest/record/v1/invoice"
    params = {
        'q': f'tranid={invoice_number}',
        'limit': 1000
    }
    
    data = make_netsuite_api_request(access_token, account_id, endpoint, params)
    
    if not data:
        print("No data returned. Creating empty CSV.")
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["error", "No data returned from API"])
        return
    
    # Get items from response
    items = data.get("items", [])
    print(f"\nFound {len(items)} invoice item(s) in response")
    
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


if __name__ == "__main__":
    import os
    
    # Get access token from environment variable or use provided one
    access_token = os.getenv('NETSUITE_ACCESS_TOKEN', 
        "eyJraWQiOiJjLjQwODMwOTFfU0IyLjIwMjUtMTAtMDRfMDItMzAtNTQiLCJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9")
    
    # Account ID
    account_id = os.getenv('NETSUITE_ACCOUNT_ID', "4083091_SB2")
    
    # Invoice number to search
    invoice_number = "205449"
    
    # Allow override via command line
    if len(sys.argv) > 1:
        invoice_number = sys.argv[1]
    
    output_file = f"invoice_{invoice_number}_results.csv"
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    # Allow access token override via command line
    if len(sys.argv) > 3:
        access_token = sys.argv[3]
    
    print(f"Using access token: {access_token[:50]}...")
    print(f"Account ID: {account_id}")
    print(f"Invoice number: {invoice_number}\n")
    
    search_invoice_and_export(access_token, account_id, invoice_number, output_file)

