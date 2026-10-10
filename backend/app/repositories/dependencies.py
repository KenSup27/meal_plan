from typing import Annotated

from fastapi import Depends, Header, HTTPException

from backend.app.core.auth import get_current_user_id
from backend.app.core.config import settings
from backend.app.repositories.supabase import SupabaseRepository


def get_business_repository(
    user_id: Annotated[str, Depends(get_current_user_id)],
    authorization: Annotated[str, Header()],
):
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(503, "Supabase 业务存储尚未配置")
    # No shared client carries a user's credentials into a later request.
    with SupabaseRepository(
        settings.supabase_url, settings.supabase_anon_key,
        authorization.partition(" ")[2].strip(), user_id,
        timeout=settings.supabase_auth_timeout_seconds,
    ) as repository:
        yield repository
