#!/usr/bin/env python3
"""
Script to search NetSuite for invoice number and export results to CSV
"""
import sys
import csv
from pathlib import Path
import os
from dotenv import load_dotenv

# Add the app directory to the path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Load environment variables
env_paths = [
    backend_dir / ".env",
    backend_dir.parent / ".env",
]
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        break

from app.services.netsuite_service import NetSuiteService


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


def search_and_export_to_csv(invoice_number: str, output_file: str = None):
    """Search for invoice and export to CSV with ALL fields"""
    if output_file is None:
        output_file = f"invoice_{invoice_number}_results.csv"
    
    print(f"Searching for invoice number: {invoice_number}")
    
    try:
        # Initialize service
        service = NetSuiteService()
        
        # Get raw response by accessing the client directly
        print("Calling NetSuite API...")
        service._ensure_authenticated()
        
        query = f"tranid={invoice_number}"
        response = service.client.search_records(
            record_type="invoice",
            query=query,
            limit=1000
        )
        
        print(f"Raw response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        
        # Get all items from response
        items = response.get("items", []) if isinstance(response, dict) else []
        print(f"Found {len(items)} invoice item(s) in response")
        
        if not items:
            print("No invoices found. Writing empty CSV.")
            # Create empty CSV with headers
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
        print(f"Writing {len(flattened_items)} invoice(s) with {len(fieldnames)} fields to {output_file}...")
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for item in flattened_items:
                # Fill in missing fields with empty strings
                row = {field: item.get(field, "") for field in fieldnames}
                writer.writerow(row)
        
        print(f"Successfully exported {len(flattened_items)} invoice(s) to {output_file}")
        
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
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error: {error_msg}")
        
        # Create CSV with error information
        print(f"Creating CSV file with error information...")
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["error", "message"])
            writer.writerow(["authentication_error", error_msg])
            writer.writerow(["", ""])
            writer.writerow(["note", "Please check NetSuite access token configuration"])
            writer.writerow(["", "1. Ensure access token is ACTIVE in NetSuite"])
            writer.writerow(["", "2. Verify token ID and secret in .env file"])
            writer.writerow(["", "3. Check account ID format (e.g., 4083091_SB2 for sandbox)"])
        
        print(f"Error details written to {output_file}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    invoice_number = "205449"
    if len(sys.argv) > 1:
        invoice_number = sys.argv[1]
    
    output_file = f"invoice_{invoice_number}_results.csv"
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    search_and_export_to_csv(invoice_number, output_file)

