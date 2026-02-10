from fastapi import Security, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
import os

# For a real implementation, we would use python-jose to decode 
# the JWT and verify it against https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys
# For MVP, we will assume a middleware or basic validation.

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID')}/oauth2/v2.0/authorize",
    tokenUrl=f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID')}/oauth2/v2.0/token",
)

def validate_token(token: str = Security(oauth2_scheme)):
    """
    Placeholder for Azure AD Token Validation.
    In production, verify signature, audience, and issuer.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Mock user for now
    return {
        "sub": "mock_user_id",
        "name": "Mock Administrator",
        "roles": ["Reader"] 
    }
