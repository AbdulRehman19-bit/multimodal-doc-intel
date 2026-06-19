from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.middleware.auth_middleware import verify_supabase_token, get_user_id

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()


@router.get("/me")
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Verify the token and return the current user's info.
    Frontend calls this on load to confirm the session is valid.
    """
    payload = await verify_supabase_token(credentials=credentials)
    return {
        "user_id": get_user_id(payload),
        "email": payload.get("email"),
        "role": payload.get("role"),
    }