# NetSuite OAuth 2.0 Implementation Guide

## Overview

This guide provides step-by-step instructions for implementing NetSuite OAuth 2.0 authentication using JWT Bearer Token flow. This is the recommended authentication method for server-to-server integrations.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Authentication Flow](#authentication-flow)
3. [Step 1: Generate JWT Bearer Token](#step-1-generate-jwt-bearer-token)
4. [Step 2: Exchange JWT for Access Token](#step-2-exchange-jwt-for-access-token)
5. [Step 3: Use Access Token for API Calls](#step-3-use-access-token-for-api-calls)
6. [Current Credentials](#current-credentials)
7. [Example Requests](#example-requests)
8. [Error Handling](#error-handling)
9. [Best Practices](#best-practices)

---

## Prerequisites

### Required Information

- **Private Key File**: PEM-encoded private key (password-protected with password: `cargomatic`)
- **Key ID (kid)**: `pvHJZk-siL5h1bm1pqypdH7dblr_ZYCE8gfODaKqAC4`
- **Client ID**: `4c063b0929d45ccf25e820e26f6b981f10f6e57960f07c4baa33c69f6fad12d6`
- **Subject**: `administrator;Patrick McElroy` (role and entity, separated by semicolon)
- **Scope**: `rest_webservices` (or `restlets`, `suite_analytics`, `mcp`)
- **Account ID**: `4083091-sb2`
- **Token Endpoint**: `https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token`
- **Base URL**: `https://4083091-sb2.suitetalk.api.netsuite.com`

### Required Libraries

- **Python**: `PyJWT>=2.8.0`, `cryptography>=41.0.0`, `requests`
- **Other Languages**: Equivalent JWT libraries that support PS256 algorithm

---

## Authentication Flow

The NetSuite OAuth 2.0 flow consists of two steps:

1. **Generate JWT Bearer Token** - Create a signed JWT token
2. **Exchange JWT for Access Token** - POST the JWT to the token endpoint
3. **Use Access Token** - Include the access token in API request headers

```
┌─────────────┐
│  Generate   │
│  JWT Token  │
└──────┬───────┘
       │
       ▼
┌─────────────┐
│  Exchange   │
│  JWT for    │
│  Access     │
│  Token      │
└──────┬───────┘
       │
       ▼
┌─────────────┐
│  Make API   │
│  Requests   │
└─────────────┘
```

---

## Step 1: Generate JWT Bearer Token

### JWT Header

```json
{
  "typ": "JWT",
  "alg": "PS256",
  "kid": "pvHJZk-siL5h1bm1pqypdH7dblr_ZYCE8gfODaKqAC4"
}
```

**Important**: 
- `typ` must be `"JWT"`
- `alg` must be `"PS256"` (RSA-PSS with SHA-256)
- `kid` is **required** and must match your certificate's Key ID

### JWT Payload

```json
{
  "sub": "administrator;Patrick McElroy",
  "aud": "https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token",
  "scope": ["rest_webservices"],
  "iss": "4c063b0929d45ccf25e820e26f6b981f10f6e57960f07c4baa33c69f6fad12d6",
  "exp": 1764095918,
  "iat": 1764092318,
  "jti": "4083091-sb2.a-c.null.1764092318811"
}
```

**Payload Fields**:
- `sub`: Role and entity separated by semicolon (e.g., `"administrator;Patrick McElroy"`)
- `aud`: Token endpoint URL (must match exactly)
- `scope`: Array of scopes (e.g., `["rest_webservices"]`)
- `iss`: Client ID
- `exp`: Expiration timestamp (Unix epoch seconds) - typically 5 minutes from `iat`
- `iat`: Issued at timestamp (Unix epoch seconds)
- `jti`: Unique token ID (UUID or unique string)

### Python Example

```python
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import time
import uuid

# Load private key
with open("key.pem", "rb") as key_file:
    private_key = serialization.load_pem_private_key(
        key_file.read(),
        password=b'cargomatic',  # Your private key password
        backend=default_backend()
    )

# JWT Header
header = {
    "typ": "JWT",
    "alg": "PS256",
    "kid": "pvHJZk-siL5h1bm1pqypdH7dblr_ZYCE8gfODaKqAC4"
}

# JWT Payload
now = int(time.time())
payload = {
    "sub": "administrator;Patrick McElroy",
    "aud": "https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token",
    "scope": ["rest_webservices"],
    "iss": "4c063b0929d45ccf25e820e26f6b981f10f6e57960f07c4baa33c69f6fad12d6",
    "exp": now + 300,  # 5 minutes from now
    "iat": now,
    "jti": f"4083091-sb2.a-c.null.{now}{uuid.uuid4().hex[:4]}"
}

# Sign JWT
jwt_token = jwt.encode(
    payload,
    private_key,
    algorithm="PS256",
    headers=header
)
```

### JavaScript/Node.js Example

```javascript
const jwt = require('jsonwebtoken');
const fs = require('fs');

// Load private key
const privateKey = fs.readFileSync('private_key.pem', 'utf8');

// JWT Header
const header = {
  typ: 'JWT',
  alg: 'PS256',
  kid: 'pvHJZk-siL5h1bm1pqypdH7dblr_ZYCE8gfODaKqAC4'
};

// JWT Payload
const now = Math.floor(Date.now() / 1000);
const payload = {
  sub: 'administrator;Patrick McElroy',
  aud: 'https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token',
  scope: ['rest_webservices'],
  iss: '4c063b0929d45ccf25e820e26f6b981f10f6e57960f07c4baa33c69f6fad12d6',
  exp: now + 300,
  iat: now,
  jti: `4083091-sb2.a-c.null.${now}${Math.random().toString(36).substring(7)}`
};

// Sign JWT (Note: jsonwebtoken library may need additional configuration for PS256)
const jwtToken = jwt.sign(payload, privateKey, {
  algorithm: 'PS256',
  header: header,
  keyid: 'pvHJZk-siL5h1bm1pqypdH7dblr_ZYCE8gfODaKqAC4'
});
```

---

## Step 2: Exchange JWT for Access Token

### Endpoint

```
POST https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token
```

### Headers

```
Content-Type: application/x-www-form-urlencoded
```

### Request Body (Form Data)

```
grant_type=client_credentials
client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer
client_assertion=<JWT_TOKEN>
```

### Python Example

```python
import requests

token_endpoint = "https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token"

data = {
    "grant_type": "client_credentials",
    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
    "client_assertion": jwt_token  # From Step 1
}

headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

response = requests.post(token_endpoint, data=data, headers=headers)

if response.status_code == 200:
    token_data = response.json()
    access_token = token_data["access_token"]
    # access_token expires in token_data["expires_in"] seconds (typically 3600)
else:
    print(f"Error: {response.status_code} - {response.text}")
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

const tokenEndpoint = 'https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token';

const data = new URLSearchParams();
data.append('grant_type', 'client_credentials');
data.append('client_assertion_type', 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer');
data.append('client_assertion', jwtToken); // From Step 1

const response = await axios.post(tokenEndpoint, data, {
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded'
  }
});

if (response.status === 200) {
  const tokenData = response.data;
  const accessToken = tokenData.access_token;
  // accessToken expires in tokenData.expires_in seconds (typically 3600)
} else {
  console.error(`Error: ${response.status} - ${response.data}`);
}
```

### cURL Example

```bash
curl -X POST \
  'https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=client_credentials' \
  -d 'client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer' \
  -d "client_assertion=<JWT_TOKEN>"
```

### Expected Response

```json
{
  "access_token": "eyJraWQiOiJjLjQwODMwOTFfU0IyLjIwMjUtMTAtMDRfMDItMzAtNTQiLCJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": "3600"
}
```

---

## Step 3: Use Access Token for API Calls

### Base URL

```
https://4083091-sb2.suitetalk.api.netsuite.com
```

### Headers

```
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
Prefer: transient
```

### Python Example

```python
import requests

base_url = "https://4083091-sb2.suitetalk.api.netsuite.com"
endpoint = "/services/rest/record/v1/contact"

url = f"{base_url}{endpoint}"

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
    "Prefer": "transient"
}

params = {
    "limit": 10,
    "offset": 0
}

response = requests.get(url, headers=headers, params=params)

if response.status_code == 200:
    data = response.json()
    print(f"Success: {len(data.get('items', []))} items returned")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

const baseUrl = 'https://4083091-sb2.suitetalk.api.netsuite.com';
const endpoint = '/services/rest/record/v1/contact';

const url = `${baseUrl}${endpoint}`;

const headers = {
  'Authorization': `Bearer ${accessToken}`,
  'Content-Type': 'application/json',
  'Prefer': 'transient'
};

const params = {
  limit: 10,
  offset: 0
};

const response = await axios.get(url, { headers, params });

if (response.status === 200) {
  const data = response.data;
  console.log(`Success: ${data.items.length} items returned`);
} else {
  console.error(`Error: ${response.status} - ${response.data}`);
}
```

### cURL Example

```bash
curl -X GET \
  'https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/record/v1/contact?limit=10&offset=0' \
  -H 'Authorization: Bearer <ACCESS_TOKEN>' \
  -H 'Content-Type: application/json' \
  -H 'Prefer: transient'
```

---

## Current Credentials

### Current Access Token (Valid for 1 hour)

**Generated**: 2025-01-27 (expires in 60 minutes)

```
eyJraWQiOiJjLjQwODMwOTFfU0IyLjIwMjUtMTAtMDRfMDItMzAtNTQiLCJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIzOzgzMzg2IiwiYXVkIjpbIkEyQTNBQUMzLUQwRTgtNDU4MS1BRUI5LTBCNTU5NUQ4QjVCMDs0MDgzMDkxX1NCMiIsIjRjMDYzYjA5MjlkNDVjY2YyNWU4MjBlMjZmNmI5ODFmMTBmNmU1Nzk2MGYwN2M0YmFhMzNjNjlmNmZhZDEyZDYiXSwic2NvcGUiOlsicmVzdF93ZWJzZXJ2aWNlcyJdLCJpc3MiOiJodHRwczovL3N5c3RlbS5uZXRzdWl0ZS5jb20iLCJvaXQiOjE3NjQwOTI3NDYsImV4cCI6MTc2NDA5NjM0NiwiaWF0IjoxNzY0MDkyNzQ2LCJqdGkiOiI0MDgzMDkxX1NCMi5hLWMubnVsbC4xNzY0MDkyNzQ2MDE0In0.m525UIDjKnt2P7JtdhRN7nv7DDxI5dSpLXtIThiQrFiACIGdCUZtKit4_hPHcMBsKqjJ3Ww998GRVeqANFaXZH84WcaGaDCWpgvXK8w9o6mXJ3m5iySgXa91Y-rEPqZ9hfvoozsNLUByMhcLYOSLEbi_gZlDWf5BicP2EtEIL6r891eXn4Ec9I9Sk6JVq0HSUbN8tkVA2F1l8S6SGR7bzD_QFQnPVDqMx0WqoqQXA_SfvWTzVxVd_X76gr4Dxxi7TnrP6quny0uqh5EKOIZSvNkHyauiTnvE2rQHGfWTOFjcFaC-QrTTPnoJzO9PUclc9dX6cgxpuhMGcyYFZ-WbodMabYnwwHcCJS-1tLVR3auoi9I-7iFw45kBBVyXAQPt305kYCAdw3JR8h3R_Oigg_ddI37IK5AXiQQTcPZapt6cbMkSNBcoUpeDSS1Lg9TJjQM5YZO0E0ijpYWlAl0Yjd1yQM8gdn5whRD20lkJZL5bR5gp-p4ug2q8r8d-rcDe32KrEQANQ8Z7aHcI06gKzPSVggDwaOok6RRtPY62s4UOsTS4xoY7hJXX3rfm6XH8o5BBo7x_9SjPb7TPfpFfFiujArhniEOQOXyNWOX7Y4fHhBlpnnXzEuAOLm0ZxoV_D5xkn5nOqtRVElxkcq7gQI_FlDr3cTX6ONAszgjPB9Q
```

**Note**: This token expires in 1 hour. Generate a new one using the JWT exchange process when needed.

### Configuration Values

```yaml
Account ID: 4083091-sb2
Base URL: https://4083091-sb2.suitetalk.api.netsuite.com
Token Endpoint: https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token
Client ID: 4c063b0929d45ccf25e820e26f6b981f10f6e57960f07c4baa33c69f6fad12d6
Key ID (kid): pvHJZk-siL5h1bm1pqypdH7dblr_ZYCE8gfODaKqAC4
Subject: administrator;Patrick McElroy
Scope: rest_webservices
Private Key Password: cargomatic
```

---

## Example Requests

### Example 1: Get Metadata Catalog

**Endpoint**: `GET /services/rest/record/v1/metadata-catalog`

**Full URL**: 
```
https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/record/v1/metadata-catalog
```

**Headers**:
```
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
Prefer: transient
```

**Response**:
```json
{
  "items": [
    {
      "name": "customrecord_nav_shortcut_tooltip",
      "links": [...]
    },
    ...
  ]
}
```

### Example 2: Get Contacts List

**Endpoint**: `GET /services/rest/record/v1/contact`

**Full URL**: 
```
https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/record/v1/contact?limit=10&offset=0
```

**Query Parameters**:
- `limit`: Number of records to return (default: varies)
- `offset`: Starting position for pagination (default: 0)

**Headers**:
```
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
Prefer: transient
```

**Response**:
```json
{
  "links": [
    {
      "rel": "next",
      "href": "https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/record/v1/contact?limit=10&offset=10"
    }
  ],
  "count": 10,
  "hasMore": true,
  "items": [
    {
      "links": [
        {
          "rel": "self",
          "href": "https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/record/v1/contact/33040"
        }
      ],
      "id": "33040"
    },
    ...
  ],
  "offset": 0,
  "totalResults": 596
}
```

### Example 3: Get Specific Contact Details

**Endpoint**: `GET /services/rest/record/v1/contact/{contact_id}`

**Full URL**: 
```
https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/record/v1/contact/33040
```

**Headers**:
```
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
Prefer: transient
```

**Response**:
```json
{
  "id": "33040",
  "entityId": "Accounting",
  "firstName": "Darren",
  "lastName": "Love",
  "email": "accounting@1BestLogistics.com",
  "phone": "949-541-0123 x9",
  "company": {
    "id": "5434",
    "refName": "1 Best Logistics"
  }
}
```

### Example 4: Get Customers List

**Endpoint**: `GET /services/rest/record/v1/customer`

**Full URL**: 
```
https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/record/v1/customer?limit=10
```

**Headers**:
```
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
Prefer: transient
```

---

## Error Handling

### Common Errors

#### 1. Invalid JWT Token (400 Bad Request)

**Error Response**:
```json
{
  "error": "invalid_request",
  "error_description": "Invalid JWT token"
}
```

**Causes**:
- JWT expired (check `exp` claim)
- Invalid signature
- Missing required claims
- Wrong `aud` or `iss` values

**Solution**: Regenerate JWT with correct claims and ensure it hasn't expired.

#### 2. Invalid Login (401 Unauthorized)

**Error Response**:
```json
{
  "type": "https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.2",
  "title": "Unauthorized",
  "status": 401,
  "o:errorDetails": [
    {
      "detail": "Invalid login attempt. For more details, see the Login Audit Trail...",
      "o:errorCode": "INVALID_LOGIN"
    }
  ]
}
```

**Causes**:
- Using JWT token directly as Bearer token (must exchange for access token first)
- Expired access token
- Wrong credentials

**Solution**: 
- Always exchange JWT for access token first
- Regenerate access token if expired

#### 3. Invalid Scope (400 Bad Request)

**Error Response**:
```json
{
  "error": "invalid_scope"
}
```

**Causes**:
- Invalid scope value in JWT payload
- Scope not authorized for your integration

**Solution**: Use valid scope: `rest_webservices`, `restlets`, `suite_analytics`, or `mcp`

#### 4. Token Expired (401 Unauthorized)

**Error Response**:
```json
{
  "error": "invalid_token",
  "error_description": "The access token expired"
}
```

**Solution**: Generate a new access token using the JWT exchange process

### Error Handling Example (Python)

```python
import requests
import time

def get_access_token_with_retry(jwt_token, max_retries=3):
    """Get access token with automatic retry on failure"""
    token_endpoint = "https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token"
    
    data = {
        "grant_type": "client_credentials",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": jwt_token
    }
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    for attempt in range(max_retries):
        try:
            response = requests.post(token_endpoint, data=data, headers=headers)
            
            if response.status_code == 200:
                return response.json()["access_token"]
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                print(f"Attempt {attempt + 1} failed: {response.status_code} - {error_data}")
                
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise Exception(f"Failed to get access token after {max_retries} attempts")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
    
    return None

def make_api_request_with_retry(access_token, endpoint, max_retries=3):
    """Make API request with automatic token refresh on 401"""
    base_url = "https://4083091-sb2.suitetalk.api.netsuite.com"
    url = f"{base_url}{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "transient"
    }
    
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            # Token expired, need to regenerate
            raise Exception("Access token expired. Please regenerate.")
        else:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            print(f"API request failed: {response.status_code} - {error_data}")
            
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise Exception(f"API request failed after {max_retries} attempts")
    
    return None
```

---

## Best Practices

### 1. Token Management

- **Cache Access Tokens**: Access tokens are valid for 1 hour. Cache them and reuse until expiration.
- **JWT Reuse**: JWT tokens can be valid for up to 24 hours. Reuse the same JWT to get new access tokens.
- **Token Refresh**: Implement automatic token refresh before expiration (refresh at 90% of expiration time).

### 2. Error Handling

- Always check response status codes
- Implement retry logic with exponential backoff
- Log errors for debugging
- Handle token expiration gracefully

### 3. Security

- **Never commit private keys to version control**
- Store credentials in environment variables or secure vaults
- Use HTTPS for all API calls
- Rotate credentials regularly

### 4. Rate Limiting

- NetSuite may have rate limits. Implement request throttling if needed.
- Use pagination (`limit` and `offset`) for large datasets
- Batch requests when possible

### 5. Headers

- Always include `Content-Type: application/json`
- Use `Prefer: transient` header for read-only operations
- Include proper `Authorization: Bearer <token>` header

### 6. Testing

- Test with sandbox account first (`4083091-sb2`)
- Verify JWT structure before sending
- Test token expiration handling
- Test error scenarios

---

## Complete Python Implementation Example

```python
import jwt
import requests
import time
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import uuid

class NetSuiteOAuth:
    def __init__(self, private_key_path, private_key_password, kid, client_id, 
                 subject, scope, account_id, token_endpoint):
        self.private_key_path = private_key_path
        self.private_key_password = private_key_password
        self.kid = kid
        self.client_id = client_id
        self.subject = subject
        self.scope = scope
        self.account_id = account_id
        self.token_endpoint = token_endpoint
        self.base_url = f"https://{account_id}.suitetalk.api.netsuite.com"
        self._private_key = None
        self._access_token = None
        self._access_token_expires_at = 0
    
    def _load_private_key(self):
        """Load and cache private key"""
        if self._private_key is None:
            with open(self.private_key_path, "rb") as key_file:
                self._private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=self.private_key_password.encode() if isinstance(self.private_key_password, str) else self.private_key_password,
                    backend=default_backend()
                )
        return self._private_key
    
    def generate_jwt(self, expiration_minutes=5):
        """Generate JWT bearer token"""
        private_key = self._load_private_key()
        now = int(time.time())
        
        header = {
            "typ": "JWT",
            "alg": "PS256",
            "kid": self.kid
        }
        
        payload = {
            "sub": self.subject,
            "aud": self.token_endpoint,
            "scope": [self.scope] if isinstance(self.scope, str) else self.scope,
            "iss": self.client_id,
            "exp": now + (expiration_minutes * 60),
            "iat": now,
            "jti": f"{self.account_id}.a-c.null.{now}{uuid.uuid4().hex[:4]}"
        }
        
        jwt_token = jwt.encode(
            payload,
            private_key,
            algorithm="PS256",
            headers=header
        )
        
        return jwt_token
    
    def get_access_token(self, force_refresh=False):
        """Get access token, using cached token if still valid"""
        # Check if cached token is still valid (with 5 minute buffer)
        if not force_refresh and self._access_token and time.time() < (self._access_token_expires_at - 300):
            return self._access_token
        
        # Generate new JWT and exchange for access token
        jwt_token = self.generate_jwt()
        
        data = {
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": jwt_token
        }
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        response = requests.post(self.token_endpoint, data=data, headers=headers)
        
        if response.status_code == 200:
            token_data = response.json()
            self._access_token = token_data["access_token"]
            expires_in = int(token_data.get("expires_in", 3600))
            self._access_token_expires_at = time.time() + expires_in
            return self._access_token
        else:
            raise Exception(f"Failed to get access token: {response.status_code} - {response.text}")
    
    def make_request(self, method, endpoint, params=None, json_data=None):
        """Make authenticated API request"""
        access_token = self.get_access_token()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Prefer": "transient"
        }
        
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, params=params, json=json_data)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, params=params, json=json_data)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, params=params)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        if response.status_code == 401:
            # Token might have expired, try refreshing
            access_token = self.get_access_token(force_refresh=True)
            headers["Authorization"] = f"Bearer {access_token}"
            response = requests.request(method, url, headers=headers, params=params, json=json_data)
        
        response.raise_for_status()
        return response.json()

# Usage
netsuite = NetSuiteOAuth(
    private_key_path="key.txt",
    private_key_password="cargomatic",
    kid="pvHJZk-siL5h1bm1pqypdH7dblr_ZYCE8gfODaKqAC4",
    client_id="4c063b0929d45ccf25e820e26f6b981f10f6e57960f07c4baa33c69f6fad12d6",
    subject="administrator;Patrick McElroy",
    scope="rest_webservices",
    account_id="4083091-sb2",
    token_endpoint="https://4083091-sb2.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token"
)

# Get contacts
contacts = netsuite.make_request("GET", "/services/rest/record/v1/contact", params={"limit": 10})
print(f"Retrieved {len(contacts['items'])} contacts")
```

---

## Troubleshooting

### Issue: "Invalid JWT token" error

**Check**:
1. JWT hasn't expired (check `exp` claim)
2. `aud` matches token endpoint URL exactly
3. `iss` matches client ID exactly
4. `kid` in header matches certificate Key ID
5. Private key password is correct
6. Algorithm is `PS256` (not `RS256`)

### Issue: "Invalid login" error

**Check**:
1. You're using the **access token** (not JWT) in API requests
2. Access token hasn't expired
3. Subject (role and entity) is correct

### Issue: "Invalid scope" error

**Check**:
1. Scope value is valid: `rest_webservices`, `restlets`, `suite_analytics`, or `mcp`
2. Scope is an array in JWT payload: `["rest_webservices"]`

### Issue: API requests return 404

**Check**:
1. Endpoint URL is correct
2. Account ID in base URL is correct
3. Record type exists in your NetSuite account

---

## Support

For additional help:
- NetSuite REST API Documentation: https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/
- NetSuite Developer Portal: https://www.netsuite.com/portal/developers/resources/apis/rest-api.shtml

---

**Last Updated**: 2025-01-27  
**Token Valid Until**: 1 hour from generation time

