<!-- e7ef21d5-dd5c-44a5-a2ee-b3a32ecfa49b 6db00fa3-cade-43eb-afe0-4ce87d30c4ec -->
# Secure Okta Integration and Deployment Plan

## Overview

This plan implements Okta OIDC authentication to secure the cash application system, restricts access to authorized users via Okta groups, and provides secure deployment options for internal hosting.

## Architecture Components

### 1. Authentication Flow

- **Frontend**: React app uses Okta Sign-In Widget or React SDK for user authentication
- **Backend**: FastAPI validates Okta access tokens on all protected endpoints
- **Token Flow**: User authenticates with Okta → receives access token → frontend sends token to backend → backend validates token and checks group membership

### 2. Access Control Strategy

- Create Okta group (e.g., "Cash Application Users") with specific members
- Configure Okta app integration to require group membership
- Backend validates both authentication and group membership
- Optional: Enforce MFA via Okta policies

### 3. Deployment Options

#### Option A: On-Premises Internal Network (Recommended for Maximum Security)

- Deploy on internal company servers/network
- Accessible only from company network or VPN
- No external internet exposure
- Use Okta Access Gateway if needed for on-premises SSO

#### Option B: Private Cloud with Network Isolation

- Deploy in private VPC/VNet (AWS, Azure, GCP)
- Restrict network access via security groups/firewalls
- VPN or bastion host required for access
- Okta OIDC for authentication layer

#### Option C: Internal Network with Reverse Proxy

- Deploy internally behind reverse proxy (nginx/traefik)
- Reverse proxy handles SSL/TLS termination
- Network-level access controls
- Okta authentication at application layer

## Implementation Steps

### Phase 1: Okta Configuration

**IMPORTANT: Domain Setup First**

Before configuring Okta, you need to know your app's URL. You have two options:

**Option 1: Use Platform Free Subdomain (Recommended - Easiest)**

- Deploy to Railway/Render/Fly.io first (see Phase 5)
- Platform provides free URL automatically:
  - Railway: `https://cash-app-production.up.railway.app`
  - Render: `https://cash-app.onrender.com`
  - Fly.io: `https://cash-app.fly.dev`
- Use this exact URL in Okta configuration below
- **No DNS setup or domain purchase needed**

**Option 2: Custom Domain (Optional)**

- Purchase domain (e.g., `yourcompany.com` for ~$10-15/year)
- Add CNAME DNS record pointing to platform URL
- Configure custom domain in platform dashboard
- Use custom domain in Okta (e.g., `https://cash-app.yourcompany.com`)

1. **Create Okta Application Integration**

   - Log into Okta Admin Console
   - Create new "Web Application" integration
   - Choose OIDC protocol
   - Configure redirect URIs using your app's URL:
     - Sign-in redirect: `https://your-app-url.railway.app/callback` (or `/login/callback` depending on SDK)
     - Sign-out redirect: `https://your-app-url.railway.app/` or `/logout`
   - Note Client ID and Client Secret (save these for environment variables)

2. **Create Access Group**

   - Create Okta group: "Cash Application Users" (or similar)
   - Add specific users to this group
   - Configure app assignment to require group membership

3. **Configure Access Policies**

   - Set up MFA requirement (if desired)
   - Configure session policies
   - Set token expiration policies

### Phase 2: Backend Authentication (FastAPI)

**Files to modify:**

- `backend/app/main.py` - Add Okta OIDC middleware
- `backend/app/routes/upload.py` - Add authentication dependency
- `backend/app/routes/invoices.py` - Add authentication dependency
- `backend/requirements.txt` - Add Okta/JWT libraries

**Implementation:**

- Install `python-jose[cryptography]` and `httpx` for token validation
- Create Okta token validator service
- Create FastAPI dependency for protected routes
- Validate access tokens and check group claims
- Return 401/403 for unauthorized requests

**Key components:**

```python
# New file: backend/app/services/okta_service.py
- Validates Okta access tokens
- Checks group membership from token claims
- Caches public keys for performance
```

### Phase 3: Frontend Authentication (React)

**Files to modify:**

- `frontend/src/App.jsx` - Add Okta authentication wrapper
- `frontend/src/services/api.js` - Add token to API requests
- `frontend/package.json` - Add `@okta/okta-react` or `@okta/okta-signin-widget`

**Implementation:**

- Install Okta React SDK
- Wrap app with Okta authentication provider
- Implement login/logout flows
- Add token to all API requests via axios interceptors
- Handle token refresh automatically

### Phase 4: Security Hardening

1. **Environment Variables**

   - Store Okta configuration in `.env` files
   - Never commit secrets to version control
   - Use different configs for dev/staging/prod

2. **CORS Configuration**

   - Update CORS to only allow authenticated origins
   - Remove localhost origins in production

3. **Network Security**

   - Configure firewall rules
   - Use HTTPS/TLS for all communications
   - Implement rate limiting on API endpoints

4. **NetSuite Integration Security**

   - Keep NetSuite credentials secure (already using JWT OAuth)
   - Ensure credentials are not exposed in frontend
   - Use backend-only NetSuite API calls

### Phase 5: Deployment Configuration

**Docker Option (Recommended):**

- Create `Dockerfile` for backend
- Create `Dockerfile` for frontend (multi-stage build)
- Create `docker-compose.yml` for local development
- Configure for internal network deployment

**Alternative: Systemd Service (On-Premises):**

- Create systemd service files
- Configure reverse proxy (nginx)
- Set up SSL certificates
- Configure firewall rules

## Security Considerations

1. **Token Validation**: Always validate tokens server-side, never trust client-only validation
2. **Group Claims**: Verify group membership from token claims, not just authentication
3. **Okta-Protected Access**: App is internet-accessible but secured by Okta - only authenticated users can access any endpoint
4. **HTTPS/SSL**: Cloud platform provides automatic SSL certificates (required for Okta OIDC)
5. **Secrets Management**: Store Okta credentials in platform environment variables (never in code)
6. **CORS Configuration**: Restrict CORS to only your app domain
7. **Rate Limiting**: Consider adding rate limiting to prevent abuse
8. **Audit Logging**: Log all authentication attempts and API access
9. **Regular Updates**: Keep dependencies updated for security patches

## Testing Strategy

1. Test authentication flow end-to-end
2. Verify unauthorized users cannot access endpoints
3. Test group membership enforcement
4. Verify token refresh works correctly
5. Test with MFA enabled (if configured)
6. Load testing for token validation performance

## Rollout Plan

1. **Development**: Implement and test in local environment
2. **Staging**: Deploy to internal staging environment with Okta test app
3. **Production**: Deploy to production with production Okta app
4. **Monitoring**: Set up logging and monitoring for authentication events

## Files to Create/Modify

**New Files:**

- `backend/app/services/okta_service.py` - Okta token validation service
- `backend/app/middleware/auth.py` - Authentication middleware/dependencies
- `backend/Dockerfile` - Backend containerization
- `frontend/Dockerfile` - Frontend containerization
- `docker-compose.yml` - Local development setup
- `.env.example` - Example environment variables
- `DEPLOYMENT.md` - Deployment documentation

**Modified Files:**

- `backend/app/main.py` - Add Okta middleware
- `backend/app/routes/upload.py` - Add auth dependency
- `backend/app/routes/invoices.py` - Add auth dependency
- `backend/requirements.txt` - Add Okta/JWT libraries
- `frontend/src/App.jsx` - Add Okta provider
- `frontend/src/services/api.js` - Add token to requests
- `frontend/package.json` - Add Okta dependencies

## Dependencies to Add

**Backend:**

- `python-jose[cryptography]>=3.3.0` - JWT token validation
- `httpx>=0.25.0` - HTTP client for Okta API calls

**Frontend:**

- `@okta/okta-react>=7.0.0` - Okta React SDK (or `@okta/okta-signin-widget`)

## Configuration Required

**Okta Admin Console:**

- Application Client ID
- Application Client Secret
- Okta Domain (e.g., `company.okta.com`)
- Group name for access control

**Environment Variables:**

- `OKTA_DOMAIN` - Your Okta domain
- `OKTA_CLIENT_ID` - Application client ID
- `OKTA_CLIENT_SECRET` - Application client secret (backend only)
- `OKTA_AUDIENCE` - API audience (usually same as client ID)
- `OKTA_REQUIRED_GROUP` - Group name users must belong to

## Next Steps After Implementation

1. Configure Okta application in admin console
2. Create access group and assign users
3. Test authentication flow
4. Deploy to internal network
5. Monitor and audit access logs
6. Train authorized users on system access

### To-dos

- [ ] Configure Okta application integration (OIDC) and create access group in Okta Admin Console
- [ ] Create Okta token validation service (backend/app/services/okta_service.py) to validate access tokens and check group membership
- [ ] Implement FastAPI authentication dependency/middleware to protect routes (backend/app/middleware/auth.py)
- [ ] Add authentication dependencies to upload.py and invoices.py routes
- [ ] Integrate Okta React SDK into frontend App.jsx and configure authentication provider
- [ ] Update frontend API service to include Okta access tokens in all requests
- [ ] Add required Okta/JWT libraries to requirements.txt and package.json
- [ ] Update CORS configuration, add environment variable examples, and document security best practices
- [ ] Create Dockerfiles and deployment documentation for secure internal hosting
- [ ] Test authentication flow, group membership enforcement, and unauthorized access prevention