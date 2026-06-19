from supabase import create_client, Client
from app.config import get_settings
from functools import lru_cache

settings = get_settings()


@lru_cache()
def get_supabase() -> Client:
    """
    Service-role client — has full DB access, bypasses RLS.
    Only used server-side in FastAPI. Never exposed to the frontend.
    """
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )


@lru_cache()
def get_supabase_anon() -> Client:
    """
    Anon client — respects RLS, safe to use for user-scoped operations.
    """
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
    )