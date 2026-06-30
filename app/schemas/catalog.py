from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class CatalogProductOut(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    category: str
    price: Decimal
    available: bool
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime
