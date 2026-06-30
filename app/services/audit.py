import json
from typing import Any

from supabase import Client


def jsonable(value: Any) -> Any:
    if value is None:
        return None
    return json.loads(json.dumps(value, default=str))


class AuditService:
    def __init__(self, db: Client):
        self.db = db

    async def record(
        self,
        *,
        actor: Any,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        before_data: Any = None,
        after_data: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "actor_profile_id": getattr(actor, "profile_id", None),
            "actor_email": getattr(actor, "email", None),
            "actor_role": getattr(actor, "role", None),
            "auth_method": getattr(actor, "auth_method", None),
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id else None,
            "before_data": jsonable(before_data),
            "after_data": jsonable(after_data),
            "metadata": jsonable(metadata or {}),
        }
        self.db.table("audit_logs").insert(payload).execute()

    async def safe_record(self, **kwargs: Any) -> None:
        try:
            await self.record(**kwargs)
        except Exception:
            return
