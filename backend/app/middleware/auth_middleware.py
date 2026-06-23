import jwt
import httpx
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

settings = get_settings()

# Cache JWKS to avoid fetching on every request
_jwks_cache = None


async def _get_jwks_client():
    """Get a PyJWKClient pointing at Supabase's JWKS endpoint."""
    from jwt import PyJWKClient
    jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url)


async def verify_supabase_token(
    credentials: HTTPAuthorizationCredentials = None,
    request=None,
) -> dict:
    """
    Verify a Supabase JWT token.
    Tries ES256 (new Supabase default with ECC P-256 keys) first,
    then falls back to HS256 with the legacy JWT secret.
    """
    token = credentials.credentials if credentials else None

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Try ES256 first (new Supabase ECC P-256 signing keys)
    try:
        jwks_client = await _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            options={"verify_aud": False},
            leeway=10,
        )
        return payload
    except Exception:
        pass

    # Fallback to HS256 with legacy JWT secret
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
            leeway=10,
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )


def get_user_id(payload: dict) -> str:
    """Extract user ID from a verified JWT payload."""
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing user ID.",
        )
    return user_id