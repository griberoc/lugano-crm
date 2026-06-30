from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.client import get_supabase
from supabase import Client

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """
    Validate a Supabase Auth JWT and return the authenticated user context.
    The access token is kept so database calls can run with RLS.
    """
    try:
        response = supabase.auth.get_user(credentials.credentials)
        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalido ou expirado",
            )
        return {
            "id": response.user.id,
            "email": response.user.email,
            "access_token": credentials.credentials,
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nao autenticado",
        )


async def get_current_user_id(
    user: dict = Depends(get_current_user),
) -> str:
    return user["id"]
