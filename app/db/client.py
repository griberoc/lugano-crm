from functools import lru_cache

from app.core.config import settings
from supabase import Client, ClientOptions, create_client


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Default anon client."""
    return create_client(settings.supabase_url, settings.supabase_anon_key)


@lru_cache(maxsize=1)
def get_supabase_admin() -> Client:
    """Admin client. Bypasses RLS; use only for trusted internal operations."""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_supabase_for_token(access_token: str) -> Client:
    """Client scoped to the authenticated user, so Supabase RLS can apply."""
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=ClientOptions(
            headers={"Authorization": f"Bearer {access_token}"},
            persist_session=False,
        ),
    )
