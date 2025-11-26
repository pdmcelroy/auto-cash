#!/usr/bin/env python3
"""
Apply a payment to a NetSuite invoice using REST API
Uses Step 3 from NETSUITE_OAUTH_IMPLEMENTATION_GUIDE
"""
import requests
import json
import sys
from datetime import datetime


def find_cash_accounts(access_token: str, base_url: str, verbose: bool = False):
    """Try to find active cash/bank accounts by checking common account IDs"""
    print("Searching for active cash/bank accounts...")
    
    # Common account IDs to try (these vary by NetSuite instance)
    common_account_ids = ["1", "2", "3", "4", "5", "100", "101", "102", "200", "201", "300", "301"]
    
    cash_accounts = []
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "transient"
    }
    
    for account_id in common_account_ids:
        try:
            url = f"{base_url}/services/rest/record/v1/account/{account_id}"
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                account = response.json()
                acct_type = account.get("acctType", {}).get("refName", "")
                acct_name = account.get("acctName", "N/A")
                acct_number = account.get("acctNumber", "N/A")
                is_inactive = account.get("isInactive", False)
                is_summary = account.get("isSummary", False)
                
                # Check if it's an active, non-summary cash or bank account
                if (acct_type in ["Bank", "Cash"] and not is_inactive and not is_summary):
                    cash_accounts.append({
                        "id": account_id,
                        "name": acct_name,
                        "number": acct_number,
                        "type": acct_type
                    })
                    if verbose:
                        print(f"  Found: ID {account_id} - {acct_name} ({acct_type})")
        except:
            continue
    
    if cash_accounts:
        print(f"✓ Found {len(cash_accounts)} active cash/bank account(s):")
        for acc in cash_accounts:
            print(f"  ID: {acc['id']} | {acc['name']} ({acc['type']})")
    else:
        print("⚠️  Could not automatically find active cash/bank accounts.")
        print("   Will use undeposited funds instead (undepFunds=true)")
        print("   You can specify an account ID using --account parameter")
    
    return cash_accounts


def get_invoice_details(access_token: str, base_url: str, invoice_id: str, verbose: bool = False):
    """Get detailed information for a specific invoice"""
    endpoint = f"/services/rest/record/v1/invoice/{invoice_id}"
    url = f"{base_url}{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "transient"
    }
    
    if verbose:
        print(f"  Fetching invoice details: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def apply_payment_to_invoice(access_token: str, 
                            invoice_id: str,
                            payment_amount: float,
                            deposit_account_id: str = None,
                            payment_date: str = None,
                            verbose: bool = False):
    """
    Apply a payment to a NetSuite invoice
    
    Args:
        access_token: OAuth 2.0 access token
        invoice_id: Internal ID of the invoice to pay
        payment_amount: Amount to apply to the invoice
        deposit_account_id: Account ID where payment will be deposited (optional, will try to find default)
        payment_date: Payment date in YYYY-MM-DD format (optional, defaults to today)
        verbose: Show detailed request/response information
    """
    base_url = "https://4083091-sb2.suitetalk.api.netsuite.com"
    
    # Step 1: Get invoice details to extract customer ID and verify amount
    print("=" * 60)
    print("Apply Payment to Invoice")
    print("=" * 60)
    print(f"Invoice ID: {invoice_id}")
    print(f"Payment Amount: ${payment_amount:,.2f}")
    print()
    
    print("Step 1: Fetching invoice details...")
    invoice = get_invoice_details(access_token, base_url, invoice_id, verbose)
    
    if not invoice:
        print("❌ Failed to get invoice details")
        return None
    
    # Extract required information
    customer_id = None
    customer_info = invoice.get("entity", {})
    if isinstance(customer_info, dict):
        customer_id = customer_info.get("id")
        customer_name = customer_info.get("refName", customer_info.get("name", "N/A"))
    else:
        customer_id = customer_info
        customer_name = "N/A"
    
    invoice_number = invoice.get("tranId", invoice.get("tranid", "N/A"))
    invoice_amount = float(invoice.get("total", invoice.get("amount", 0)))
    invoice_status = invoice.get("status", {}).get("refName", invoice.get("status", "N/A"))
    
    print(f"✓ Invoice Details:")
    print(f"  Invoice #: {invoice_number}")
    print(f"  Customer: {customer_name} (ID: {customer_id})")
    print(f"  Invoice Amount: ${invoice_amount:,.2f}")
    print(f"  Status: {invoice_status}")
    print()
    
    if not customer_id:
        print("❌ Could not determine customer ID from invoice")
        return None
    
    # Step 2: Get deposit account (optional - can use undeposited funds)
    # Customer payments can use a cash/bank account OR undeposited funds
    if not deposit_account_id:
        print("Step 2: Finding deposit account...")
        cash_accounts = find_cash_accounts(access_token, base_url, verbose)
        if cash_accounts:
            # Use the first found active cash account
            deposit_account_id = cash_accounts[0]["id"]
            print(f"  Using account: {cash_accounts[0]['name']} (ID: {deposit_account_id})")
        else:
            print("  Will use undeposited funds (undepFunds=true)")
            print("  This allows the payment to be deposited later in NetSuite")
        print()
    
    # Step 3: Prepare payment date
    if not payment_date:
        payment_date = datetime.now().strftime("%Y-%m-%d")
    
    # Step 3: Create customer payment record
    print("Step 3: Creating customer payment record...")
    
    payment_endpoint = "/services/rest/record/v1/customerpayment"
    payment_url = f"{base_url}{payment_endpoint}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "transient"
    }
    
    # Extract currency from invoice if available
    currency_id = "1"  # Default to USD
    currency_info = invoice.get("currency", {})
    if isinstance(currency_info, dict):
        currency_id = currency_info.get("id", "1")
    elif isinstance(currency_info, str):
        currency_id = currency_info
    
    # Extract subsidiary from invoice if available
    subsidiary_id = None
    subsidiary_info = invoice.get("subsidiary", {})
    if isinstance(subsidiary_info, dict):
        subsidiary_id = subsidiary_info.get("id")
    
    # Extract class from invoice (divisions are stored as classifications in NetSuite)
    class_id = None
    division_id = None
    class_info = invoice.get("class", {})
    if isinstance(class_info, dict) and class_info.get("id"):
        class_id = class_info.get("id")
        division_id = class_id  # Divisions are classifications, so use the same ID
    
    # Build payment payload
    # Note: If account is invalid, try using undepFunds=true instead
    payment_payload = {
        "customer": {
            "id": str(customer_id)
        },
        "payment": payment_amount,
        "tranDate": payment_date,
        "currency": {
            "id": str(currency_id)
        },
        "undepFunds": True,  # Use undeposited funds if account is problematic
        "apply": {
            "items": [
                {
                    "doc": {
                        "id": str(invoice_id)
                    },
                    "apply": True,
                    "amount": payment_amount
                }
            ]
        }
    }
    
    # Only add account if explicitly provided (otherwise use undepFunds)
    # Accounts are often subsidiary-specific, so we use undepFunds as fallback
    if deposit_account_id:
        payment_payload["account"] = {
            "id": deposit_account_id
        }
        payment_payload["undepFunds"] = False
    else:
        # Use undeposited funds - this is more flexible across subsidiaries
        payment_payload["undepFunds"] = True
    
    # Add subsidiary if available
    if subsidiary_id:
        payment_payload["subsidiary"] = {
            "id": str(subsidiary_id)
        }
    
    # Add class if available
    if class_id:
        payment_payload["class"] = {
            "id": str(class_id)
        }
        if verbose:
            print(f"  Using class ID: {class_id}")
    
    # Add division - divisions are stored as classifications in NetSuite
    # "Three Rivers" = classification ID 19
    if division_id:
        payment_payload["division"] = {
            "id": str(division_id)
        }
        if verbose:
            print(f"  Using division ID: {division_id} (from classification)")
    
    if verbose:
        print(f"  Payment URL: {payment_url}")
        print(f"  Payment Payload:")
        print(json.dumps(payment_payload, indent=2))
        print()
    
    try:
        # POST request to create payment
        response = requests.post(payment_url, headers=headers, json=payment_payload)
        
        print(f"  Response Status: {response.status_code}")
        
        if verbose:
            print(f"  Response Headers: {dict(response.headers)}")
        
        # 204 No Content means success (payment created, no response body)
        # 200/201 also mean success (with response body)
        if response.status_code in [200, 201, 204]:
            print("✓ Payment applied successfully!")
            print()
            
            # For 204, get payment details from Location header
            if response.status_code == 204:
                location = response.headers.get("Location", "")
                if location:
                    payment_id = location.split("/")[-1]
                    print(f"  Payment created at: {location}")
                    # Fetch the created payment to get details
                    try:
                        payment_response = requests.get(location, headers=headers)
                        if payment_response.status_code == 200:
                            payment_data = payment_response.json()
                            if verbose:
                                print("  Payment Response:")
                                print(json.dumps(payment_data, indent=2))
                                print()
                            
                            payment_id = payment_data.get("id", payment_id)
                            payment_number = payment_data.get("tranId", payment_data.get("tranid", "N/A"))
                            
                            print(f"Payment Details:")
                            print(f"  Payment ID: {payment_id}")
                            print(f"  Payment #: {payment_number}")
                            print(f"  Amount: ${payment_amount:,.2f}")
                            print(f"  Applied to Invoice: {invoice_number} (ID: {invoice_id})")
                            print()
                            
                            return payment_data
                    except Exception as e:
                        if verbose:
                            print(f"  Could not fetch payment details: {e}")
                
                print(f"Payment Details:")
                print(f"  Payment ID: {payment_id if 'payment_id' in locals() else 'N/A'}")
                print(f"  Amount: ${payment_amount:,.2f}")
                print(f"  Applied to Invoice: {invoice_number} (ID: {invoice_id})")
                print()
                return {"id": payment_id if 'payment_id' in locals() else None, "status": "created"}
            else:
                # 200/201 with response body
                payment_data = response.json()
                if verbose:
                    print("  Payment Response:")
                    print(json.dumps(payment_data, indent=2))
                    print()
                
                payment_id = payment_data.get("id", "N/A")
                payment_number = payment_data.get("tranId", payment_data.get("tranid", "N/A"))
                
                print(f"Payment Details:")
                print(f"  Payment ID: {payment_id}")
                print(f"  Payment #: {payment_number}")
                print(f"  Amount: ${payment_amount:,.2f}")
                print(f"  Applied to Invoice: {invoice_number} (ID: {invoice_id})")
                print()
                
                return payment_data
        else:
            print(f"❌ Payment application failed:")
            print(f"  Status Code: {response.status_code}")
            print(f"  Response: {response.text}")
            
            try:
                error_json = response.json()
                print(f"  Error Details:")
                print(json.dumps(error_json, indent=2))
            except:
                pass
            
            return None
            
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import os
    
    # Access token
    access_token = os.getenv('NETSUITE_ACCESS_TOKEN',
        "eyJraWQiOiJjLjQwODMwOTFfU0IyLjIwMjUtMTAtMDRfMDItMzAtNTQiLCJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIzOzgzMzg2IiwiYXVkIjpbIkEyQTNBQUMzLUQwRTgtNDU4MS1BRUI5LTBCNTU5NUQ4QjVCMDs0MDgzMDkxX1NCMiIsIjRjMDYzYjA5MjlkNDVjY2YyNWU4MjBlMjZmNmI5ODFmMTBmNmU1Nzk2MGYwN2M0YmFhMzNjNjlmNmZhZDEyZDYiXSwic2NvcGUiOlsicmVzdF93ZWJzZXJ2aWNlcyJdLCJpc3MiOiJodHRwczovL3N5c3RlbS5uZXRzdWl0ZS5jb20iLCJvaXQiOjE3NjQxMTQ2NjAsImV4cCI6MTc2NDExODI2MCwiaWF0IjoxNzY0MTE0NjYwLCJqdGkiOiI0MDgzMDkxX1NCMi5hLWMubnVsbC4xNzY0MTE0NjYwMDU1In0.VhSQO-uJTbeiR4dvUq6C2g7_5kwvXnj-JReHnuseuHYZqtdIaOzC5Ge_RUdd-V8riJZ-urlZjRI5Z7i0lNoIemKR6HvNcy288yg_hoWLk8zJYBE_cxPaBC2UxCaieJiZys-0RekVFNeZW9w1J_Uk4IE9PIdDr70qemiFwhDGvDf-H-Qh_-xxMzD5LCXx2t7saroRX5VZeZnW7R2fvS2rN_QWU-g7-VX1KE0qX-yH4-BRjYhYERpevuN1w8fQHMkLBQO-HJGmEsdGNWtk8RK3frFi-b2_IHi6JwcftSiYCo0MnMt5up-J18ZP6X9jwxvcYymW0Jw59l3Y7ZOUtWlbNRIGsxGig4LY7B5zK4QwUSdCIQ0VmGXnIYzgeYJ-z5AaWL49KxLrUIsgHMbK3numHy4qf65XfWqiYvJrCLHkN4IAGsKSaaOkLRcCTDGrp3omM3FMVwQzTPN9FDHsIyklvCvJEpEkL6uH33FEJYsZbbfMuKTwTlyPQMVa_54Gyus-V1wv5N2PyilsinTNQh2En27K17hwEvgPOsQxwtXA-hCEJyNC2MFFAAzcxiWquRc48d9GBQcsNZpHeEOANNmrAGaHz0j0cmL0Cc0s1fqYgZ_k5shBXkT8anshnrQLlP6w4GfMtGQIXrLS_c8PPayb0jDEQrrDveTH-3-VK3SDaw0")
    
    # Default invoice ID from the CSV
    invoice_id = "4414641"
    payment_amount = 11000.0  # Full amount of the invoice
    
    # Parse command line arguments
    verbose = False
    deposit_account_id = None
    payment_date = None
    
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--token" and i + 1 < len(sys.argv):
            access_token = sys.argv[i + 1]
            i += 2
        elif arg == "--invoice-id" and i + 1 < len(sys.argv):
            invoice_id = sys.argv[i + 1]
            i += 2
        elif arg == "--amount" and i + 1 < len(sys.argv):
            payment_amount = float(sys.argv[i + 1])
            i += 2
        elif arg == "--account" and i + 1 < len(sys.argv):
            deposit_account_id = sys.argv[i + 1]
            i += 2
        elif arg == "--date" and i + 1 < len(sys.argv):
            payment_date = sys.argv[i + 1]
            i += 2
        elif arg == "--verbose" or arg == "-v":
            verbose = True
            i += 1
        else:
            i += 1
    
    print("Usage:")
    print("  python apply_payment_to_invoice.py --invoice-id 4414641 --amount 11000.0")
    print("  python apply_payment_to_invoice.py --invoice-id 4414641 --amount 5000.0 --account 328 --verbose")
    print()
    
    apply_payment_to_invoice(
        access_token,
        invoice_id=invoice_id,
        payment_amount=payment_amount,
        deposit_account_id=deposit_account_id,
        payment_date=payment_date,
        verbose=verbose
    )

