#!/usr/bin/env python3
"""
Test NetSuite API connection using access token (Step 3 from NETSUITE_OAUTH_IMPLEMENTATION_GUIDE)
Simple verification that we can hit NetSuite properly
"""
import requests
import json

def test_netsuite_connection(access_token: str):
    """
    Test NetSuite API connection following Step 3 from the guide
    """
    # Base URL from guide
    base_url = "https://4083091-sb2.suitetalk.api.netsuite.com"
    
    # Use metadata-catalog endpoint as shown in Example 1 from the guide
    endpoint = "/services/rest/record/v1/metadata-catalog"
    
    # Full URL
    url = f"{base_url}{endpoint}"
    
    # Headers as specified in Step 3
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "transient"
    }
    
    print("=" * 60)
    print("NetSuite API Connection Test (Step 3)")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Headers: Authorization: Bearer {access_token[:50]}...")
    print()
    
    try:
        # Make GET request
        response = requests.get(url, headers=headers)
        
        print(f"Response Status: {response.status_code}")
        print()
        
        if response.status_code == 200:
            print("✓ SUCCESS! NetSuite API connection verified!")
            print()
            data = response.json()
            
            # Show summary
            items = data.get("items", [])
            print(f"Response Summary:")
            print(f"  - Total items: {len(items)}")
            if items:
                print(f"  - First item name: {items[0].get('name', 'N/A')}")
            print()
            print("✓ Connection test passed!")
            return True
        else:
            print(f"❌ Error Response:")
            print(f"  Status Code: {response.status_code}")
            print(f"  Response Text: {response.text}")
            try:
                error_json = response.json()
                print(f"  Error JSON: {json.dumps(error_json, indent=2)}")
            except:
                pass
            return False
        
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Access token from user
    access_token = "eyJraWQiOiJjLjQwODMwOTFfU0IyLjIwMjUtMTAtMDRfMDItMzAtNTQiLCJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIzOzgzMzg2IiwiYXVkIjpbIkEyQTNBQUMzLUQwRTgtNDU4MS1BRUI5LTBCNTU5NUQ4QjVCMDs0MDgzMDkxX1NCMiIsIjRjMDYzYjA5MjlkNDVjY2YyNWU4MjBlMjZmNmI5ODFmMTBmNmU1Nzk2MGYwN2M0YmFhMzNjNjlmNmZhZDEyZDYiXSwic2NvcGUiOlsicmVzdF93ZWJzZXJ2aWNlcyJdLCJpc3MiOiJodHRwczovL3N5c3RlbS5uZXRzdWl0ZS5jb20iLCJvaXQiOjE3NjQwOTI3NDYsImV4cCI6MTc2NDA5NjM0NiwiaWF0IjoxNzY0MDkyNzQ2LCJqdGkiOiI0MDgzMDkxX1NCMi5hLWMubnVsbC4xNzY0MDkyNzQ2MDE0In0.m525UIDjKnt2P7JtdhRN7nv7DDxI5dSpLXtIThiQrFiACIGdCUZtKit4_hPHcMBsKqjJ3Ww998GRVeqANFaXZH84WcaGaDCWpgvXK8w9o6mXJ3m5iySgXa91Y-rEPqZ9hfvoozsNLUByMhcLYOSLEbi_gZlDWf5BicP2EtEIL6r891eXn4Ec9I9Sk6JVq0HSUbN8tkVA2F1l8S6SGR7bzD_QFQnPVDqMx0WqoqQXA_SfvWTzVxVd_X76gr4Dxxi7TnrP6quny0uqh5EKOIZSvNkHyauiTnvE2rQHGfWTOFjcFaC-QrTTPnoJzO9PUclc9dX6cgxpuhMGcyYFZ-WbodMabYnwwHcCJS-1tLVR3auoi9I-7iFw45kBBVyXAQPt305kYCAdw3JR8h3R_Oigg_ddI37IK5AXiQQTcPZapt6cbMkSNBcoUpeDSS1Lg9TJjQM5YZO0E0ijpYWlAl0Yjd1yQM8gdn5whRD20lkJZL5bR5gp-p4ug2q8r8d-rcDe32KrEQANQ8Z7aHcI06gKzPSVggDwaOok6RRtPY62s4UOsTS4xoY7hJXX3rfm6XH8o5BBo7x_9SjPb7TPfpFfFiujArhniEOQOXyNWOX7Y4fHhBlpnnXzEuAOLm0ZxoV_D5xkn5nOqtRVElxkcq7gQI_FlDr3cTX6ONAszgjPB9Q"
    
    # Allow override via command line
    import sys
    if len(sys.argv) > 1:
        access_token = sys.argv[1]
    
    success = test_netsuite_connection(access_token)
    sys.exit(0 if success else 1)

