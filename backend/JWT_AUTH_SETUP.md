# JWT Authentication Setup Guide

This guide explains how to configure JWT Bearer Token authentication for NetSuite API calls.

## Required Environment Variables

Add these to your `.env` file in the `backend/` directory:

```bash
# JWT Authentication (OAuth 2.0) - Required for JWT auth
NETSUITE_PRIVATE_KEY_PATH=key.txt
NETSUITE_JWT_SUBJECT=administrator;Patrick McElroy
NETSUITE_JWT_SCOPE=rest_webservices
NETSUITE_JWT_KID=pvHJZk-siL5h1bm1pqypdH7dblr_ZYCE8gfODaKqAC4
NETSUITE_CLIENT_ID=4c063b0929d45ccf25e820e26f6b981f10f6e57960f07c4baa33c69f6fad12d6

# Optional - will be auto-generated from account_id if not provided
NETSUITE_TOKEN_ENDPOINT=https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token

# Account ID (still required)
NETSUITE_ACCOUNT_ID=4083091_SB2
```

## Environment Variable Descriptions

- **NETSUITE_PRIVATE_KEY_PATH**: Path to your private key file (e.g., `key.txt` or `key.pem`)
  - Can be relative to netsuite-test directory or absolute path
  - Example: `key.txt` or `/path/to/key.pem`

- **NETSUITE_JWT_SUBJECT**: Role and entity separated by semicolon
  - Format: `role;entity` or `role_id;entity_id`
  - Example: `administrator;Patrick McElroy` or `1111;10`

- **NETSUITE_JWT_SCOPE**: OAuth scope (optional, defaults to `rest_webservices`)
  - Options: `restlets`, `rest_webservices`, `suite_analytics`, `all`, or `mcp`
  - Can be comma-separated: `restlets,rest_webservices`

- **NETSUITE_JWT_KID**: Key ID of the certificate used for signing (REQUIRED)
  - This is the certificate ID that NetSuite uses to validate your token
  - Find available certificate IDs at: `https://<accountID>.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/keys`

- **NETSUITE_CLIENT_ID**: Your NetSuite OAuth 2.0 Client ID
  - Found in NetSuite: Setup > Integration > OAuth 2.0 Client Credentials

- **NETSUITE_TOKEN_ENDPOINT**: Token endpoint URL (optional)
  - Auto-generated from account_id if not provided
  - Format: `https://{account-id}.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token`

## How It Works

1. **JWT Generation**: The system generates a JWT token signed with your private key
2. **Token Exchange**: The JWT is exchanged for an access token via NetSuite's OAuth 2.0 endpoint
3. **API Calls**: The access token is used as a Bearer token in API requests

## Fallback to TBA

If JWT environment variables are not set, the system will fall back to Token-Based Authentication (TBA) using:
- `NETSUITE_CONSUMER_KEY`
- `NETSUITE_CONSUMER_SECRET`
- `NETSUITE_TOKEN_ID`
- `NETSUITE_TOKEN_SECRET`

## Testing

After setting up the environment variables, test the authentication:

```bash
cd backend
source venv/bin/activate
python search_invoice.py 205449
```

You should see:
```
Using JWT Bearer Token authentication (OAuth 2.0)
Generating JWT bearer token...
Exchanging JWT for access token...
✓ Successfully authenticated with NetSuite (JWT OAuth 2.0)
```

## Troubleshooting

### "JWT authentication requires NETSUITE_PRIVATE_KEY_PATH"
- Make sure you've set all required JWT environment variables
- Check that the private key file exists at the specified path

### "Private key file not found"
- Verify the path to your private key file
- If using relative path, it should be relative to the netsuite-test directory

### "Failed to exchange JWT for access token"
- Verify your `NETSUITE_JWT_KID` matches your certificate ID in NetSuite
- Check that your public certificate is uploaded to NetSuite
- Verify the integration record is enabled in NetSuite
- Check NetSuite Login Audit Trail for specific error details

### Still using TBA instead of JWT
- Ensure all required JWT environment variables are set
- Check that the .env file is being loaded (see backend/app/main.py for loading logic)

