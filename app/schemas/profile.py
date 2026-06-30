from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProfilePreferences(BaseModel):
    preferred_contact: Literal["email", "whatsapp", "phone"] | None = None
    favorite_categories: list[str] = Field(default_factory=list)
    dietary_restrictions: list[str] = Field(default_factory=list)
    accepts_promotions: bool = True
    accepts_whatsapp: bool = True
    notes: str | None = None


class AddressBase(BaseModel):
    label: str
    street: str
    number: str
    complement: str | None = None
    neighborhood: str
    city: str
    zip_code: str
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    label: str | None = None
    street: str | None = None
    number: str | None = None
    complement: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    zip_code: str | None = None
    is_default: bool | None = None


class AddressOut(AddressBase):
    id: UUID
    profile_id: UUID


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    birth_date: date | None = None
    preferences: ProfilePreferences | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        digits = "".join(filter(str.isdigit, v))
        if len(digits) not in (10, 11):
            raise ValueError("Telefone deve ter 10 ou 11 digitos")
        return digits


class ProfileOut(BaseModel):
    id: UUID
    full_name: str | None
    phone: str | None
    email: str | None
    birth_date: date | None
    preferences: ProfilePreferences = Field(default_factory=ProfilePreferences)
    created_at: datetime
    updated_at: datetime | None = None
