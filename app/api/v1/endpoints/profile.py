from fastapi import APIRouter, Depends, HTTPException, Response, status
from supabase import Client

from app.core.security import get_current_user
from app.db.client import get_supabase_for_token
from app.schemas.profile import (
    AddressCreate,
    AddressOut,
    AddressUpdate,
    ProfileOut,
    ProfileUpdate,
)

router = APIRouter(prefix="/me", tags=["cliente"])


def get_authenticated_db(user: dict = Depends(get_current_user)) -> Client:
    return get_supabase_for_token(user["access_token"])


def unset_other_default_addresses(db: Client, profile_id: str) -> None:
    db.table("addresses").update({"is_default": False}).eq(
        "profile_id",
        profile_id,
    ).execute()


@router.get("/", response_model=ProfileOut)
async def get_my_profile(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_authenticated_db),
):
    response = db.table("profiles").select("*").eq("id", user["id"]).single().execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Perfil nao encontrado")
    return response.data


@router.patch("/", response_model=ProfileOut)
async def update_my_profile(
    payload: ProfileUpdate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_authenticated_db),
):
    data = payload.model_dump(mode="json", exclude_unset=True)
    response = db.table("profiles").update(data).eq("id", user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Perfil nao encontrado")
    return response.data[0]


@router.get("/addresses", response_model=list[AddressOut])
async def list_my_addresses(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_authenticated_db),
):
    response = (
        db.table("addresses")
        .select("*")
        .eq("profile_id", user["id"])
        .order("is_default", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data


@router.post("/addresses", response_model=AddressOut, status_code=201)
async def create_my_address(
    payload: AddressCreate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_authenticated_db),
):
    data = payload.model_dump(mode="json")
    data["profile_id"] = user["id"]
    existing = db.table("addresses").select("id").eq("profile_id", user["id"]).execute()
    if data["is_default"] or not existing.data:
        unset_other_default_addresses(db, user["id"])
        data["is_default"] = True
    response = db.table("addresses").insert(data).execute()
    return response.data[0]


@router.patch("/addresses/{address_id}", response_model=AddressOut)
async def update_my_address(
    address_id: str,
    payload: AddressUpdate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_authenticated_db),
):
    data = payload.model_dump(mode="json", exclude_unset=True)
    if not data:
        response = (
            db.table("addresses")
            .select("*")
            .eq("id", address_id)
            .eq("profile_id", user["id"])
            .single()
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Endereco nao encontrado")
        return response.data

    if data.get("is_default") is True:
        unset_other_default_addresses(db, user["id"])

    response = (
        db.table("addresses")
        .update(data)
        .eq("id", address_id)
        .eq("profile_id", user["id"])
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Endereco nao encontrado")
    return response.data[0]


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_address(
    address_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_authenticated_db),
):
    existing = (
        db.table("addresses")
        .select("*")
        .eq("id", address_id)
        .eq("profile_id", user["id"])
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Endereco nao encontrado")

    db.table("addresses").delete().eq("id", address_id).eq(
        "profile_id",
        user["id"],
    ).execute()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
