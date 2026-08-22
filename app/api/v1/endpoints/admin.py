from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from secrets import compare_digest
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from postgrest import APIError

from app.core.config import settings
from app.db.client import get_supabase, get_supabase_admin
from app.schemas.admin import (
    AdminLoginRequest,
    AdminOrderUpdate,
    AdminReportsOut,
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    AuditLogOut,
    CustomerOut,
    CustomerUpdate,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    PromotionCreate,
    PromotionOut,
    PromotionUpdate,
)
from app.services.audit import AuditService
from app.services.notification import NotificationService
from app.services.order_lifecycle import OrderLifecycleService
from app.services.reports import ReportService
from supabase import Client

router = APIRouter(prefix="/admin", tags=["admin"])
admin_bearer = HTTPBearer(auto_error=False)
ADMIN_ROLES = {"owner", "manager", "staff"}
ALL_ADMIN_ROLES = ("owner", "manager", "staff")
MANAGER_ROLES = ("owner", "manager")
OWNER_ROLES = ("owner",)


@dataclass(frozen=True)
class AdminContext:
    auth_method: str
    role: str
    profile_id: str | None = None
    email: str | None = None


def require_admin(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    credentials: HTTPAuthorizationCredentials | None = Depends(admin_bearer),
) -> AdminContext:
    if (
        x_admin_key
        and settings.admin_api_key_enabled
        and compare_digest(x_admin_key, settings.admin_api_key)
    ):
        return AdminContext(auth_method="admin_key", role="owner")

    if isinstance(credentials, HTTPAuthorizationCredentials):
        try:
            user_response = get_supabase().auth.get_user(credentials.credentials)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token administrativo invalido ou expirado",
            ) from exc

        if not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token administrativo invalido ou expirado",
            )

        user_id = str(user_response.user.id)
        return get_admin_context_for_user(user_id, user_response.user.email)

    if x_admin_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin key invalida",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Autenticacao administrativa obrigatoria",
    )


def get_admin_db(_: AdminContext = Depends(require_admin)) -> Client:
    return get_supabase_admin()


def require_roles(*allowed_roles: str):
    allowed = set(allowed_roles)

    def role_dependency(admin: AdminContext = Depends(require_admin)) -> AdminContext:
        if admin.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissao administrativa insuficiente",
            )
        return admin

    return role_dependency


def page_range(page: int, page_size: int) -> tuple[int, int]:
    offset = (page - 1) * page_size
    return offset, offset + page_size - 1


def serialize_payload(payload: Any, *, exclude_unset: bool = False) -> dict[str, Any]:
    return payload.model_dump(mode="json", exclude_unset=exclude_unset)


def run_admin_query(query, fallback: str):
    try:
        return query.execute()
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{fallback}: {exc.message}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{fallback}: verifique as chaves do Supabase no .env",
        ) from exc


async def audit_admin_action(
    db: Client,
    admin: AdminContext,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before_data: Any = None,
    after_data: Any = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await AuditService(db).safe_record(
        actor=admin,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=before_data,
        after_data=after_data,
        metadata=metadata,
    )


def get_admin_context_for_user(user_id: str, email: str | None) -> AdminContext:
    response = run_admin_query(
        get_supabase_admin()
        .table("admin_users")
        .select("profile_id, role, active")
        .eq("profile_id", user_id),
        "Falha ao validar permissao administrativa",
    )
    admin_user = response.data[0] if response.data else None
    if (
        not admin_user
        or not admin_user.get("active")
        or admin_user.get("role") not in ADMIN_ROLES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario sem permissao administrativa",
        )

    return AdminContext(
        auth_method="supabase",
        role=admin_user["role"],
        profile_id=user_id,
        email=email,
    )


def serialize_admin_user(db: Client, admin_user: dict[str, Any]) -> dict[str, Any]:
    profile_response = run_admin_query(
        db.table("profiles")
        .select("email, full_name")
        .eq("id", admin_user["profile_id"])
        .single(),
        "Falha ao buscar perfil administrativo",
    )
    profile = profile_response.data or {}
    return {
        **admin_user,
        "email": profile.get("email"),
        "full_name": profile.get("full_name"),
    }


def serialize_admin_order(db: Client, order: dict[str, Any]) -> dict[str, Any]:
    order = order.copy()

    customer_response = run_admin_query(
        db.table("profiles")
        .select("id, full_name, email, phone")
        .eq("id", order.get("profile_id"))
        .single(),
        "Falha ao buscar cliente do pedido",
    )
    address_response = run_admin_query(
        db.table("addresses")
        .select("*")
        .eq("id", order.get("address_id"))
        .single(),
        "Falha ao buscar endereco do pedido",
    )

    items = []
    for item in order.get("order_items") or []:
        item = item.copy()
        product_response = run_admin_query(
            db.table("products")
            .select("id, name, category")
            .eq("id", item.get("product_id"))
            .single(),
            "Falha ao buscar produto do item",
        )
        item["product"] = product_response.data or None
        items.append(item)

    order["customer"] = customer_response.data or None
    order["address"] = address_response.data or None
    order["order_items"] = items
    return order


@router.post("/login")
async def login_admin(payload: AdminLoginRequest):
    try:
        auth_response = get_supabase().auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha invalidos",
        ) from exc

    if not auth_response.user or not auth_response.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha invalidos",
        )

    admin = get_admin_context_for_user(
        str(auth_response.user.id),
        auth_response.user.email,
    )

    return {
        "access_token": auth_response.session.access_token,
        "refresh_token": auth_response.session.refresh_token,
        "expires_in": getattr(auth_response.session, "expires_in", 3600),
        "token_type": "bearer",
        "user": {
            "id": str(auth_response.user.id),
            "email": auth_response.user.email,
        },
        "admin": {
            "auth_method": admin.auth_method,
            "role": admin.role,
            "profile_id": admin.profile_id,
            "email": admin.email,
        },
    }


@router.get("/users", response_model=list[AdminUserOut])
async def list_admin_users(
    _admin: AdminContext = Depends(require_roles(*OWNER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    response = run_admin_query(
        db.table("admin_users").select("*").order("created_at", desc=True),
        "Falha ao listar equipe administrativa",
    )
    return [serialize_admin_user(db, item) for item in response.data]


@router.post("/users", response_model=AdminUserOut, status_code=201)
async def create_admin_user(
    payload: AdminUserCreate,
    admin: AdminContext = Depends(require_roles(*OWNER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    data = serialize_payload(payload)
    existing = run_admin_query(
        db.table("admin_users").select("*").eq("profile_id", data["profile_id"]),
        "Falha ao buscar usuario administrativo",
    )
    previous_admin_user = deepcopy(existing.data[0]) if existing.data else None

    if existing.data:
        response = run_admin_query(
            db.table("admin_users")
            .update({"role": data["role"], "active": data["active"]})
            .eq("profile_id", data["profile_id"]),
            "Falha ao atualizar usuario administrativo",
        )
    else:
        response = run_admin_query(
            db.table("admin_users").insert(data),
            "Falha ao criar usuario administrativo",
        )

    admin_user = serialize_admin_user(db, response.data[0])
    await audit_admin_action(
        db,
        admin,
        action="admin_user.update" if existing.data else "admin_user.create",
        entity_type="admin_user",
        entity_id=data["profile_id"],
        before_data=previous_admin_user,
        after_data=response.data[0],
        metadata={"changed_fields": sorted(data.keys())},
    )
    return admin_user


@router.patch("/users/{profile_id}", response_model=AdminUserOut)
async def update_admin_user(
    profile_id: str,
    payload: AdminUserUpdate,
    admin: AdminContext = Depends(require_roles(*OWNER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    data = serialize_payload(payload, exclude_unset=True)
    if not data:
        response = run_admin_query(
            db.table("admin_users").select("*").eq("profile_id", profile_id),
            "Falha ao buscar usuario administrativo",
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Admin nao encontrado")
        return serialize_admin_user(db, response.data[0])

    if admin.profile_id == profile_id and data.get("active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nao e possivel desativar seu proprio usuario admin",
        )
    if admin.profile_id == profile_id and data.get("role") not in (None, "owner"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nao e possivel remover seu proprio papel de owner",
        )

    current_response = run_admin_query(
        db.table("admin_users").select("*").eq("profile_id", profile_id),
        "Falha ao buscar usuario administrativo",
    )
    if not current_response.data:
        raise HTTPException(status_code=404, detail="Admin nao encontrado")
    previous_admin_user = deepcopy(current_response.data[0])

    response = run_admin_query(
        db.table("admin_users").update(data).eq("profile_id", profile_id),
        "Falha ao atualizar usuario administrativo",
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Admin nao encontrado")
    admin_user = serialize_admin_user(db, response.data[0])
    await audit_admin_action(
        db,
        admin,
        action="admin_user.update",
        entity_type="admin_user",
        entity_id=profile_id,
        before_data=previous_admin_user,
        after_data=response.data[0],
        metadata={"changed_fields": sorted(data.keys())},
    )
    return admin_user


@router.get("/me")
async def get_admin_me(admin: AdminContext = Depends(require_admin)):
    return {
        "auth_method": admin.auth_method,
        "role": admin.role,
        "profile_id": admin.profile_id,
        "email": admin.email,
    }


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(
    payload: ProductCreate,
    admin: AdminContext = Depends(require_roles(*MANAGER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    response = run_admin_query(
        db.table("products").insert(serialize_payload(payload)),
        "Falha ao criar produto",
    )
    await audit_admin_action(
        db,
        admin,
        action="product.create",
        entity_type="product",
        entity_id=response.data[0].get("id"),
        after_data=response.data[0],
        metadata={"changed_fields": sorted(serialize_payload(payload).keys())},
    )
    return response.data[0]


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _admin: AdminContext = Depends(require_roles(*ALL_ADMIN_ROLES)),
    db: Client = Depends(get_admin_db),
):
    start, end = page_range(page, page_size)
    response = run_admin_query(
        db.table("products")
        .select("*")
        .order("created_at", desc=True)
        .range(start, end),
        "Falha ao listar produtos",
    )
    return response.data


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: str,
    _admin: AdminContext = Depends(require_roles(*ALL_ADMIN_ROLES)),
    db: Client = Depends(get_admin_db),
):
    response = run_admin_query(
        db.table("products").select("*").eq("id", product_id).single(),
        "Falha ao buscar produto",
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    return response.data


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    admin: AdminContext = Depends(require_roles(*MANAGER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    data = serialize_payload(payload, exclude_unset=True)
    current_response = run_admin_query(
        db.table("products").select("*").eq("id", product_id).single(),
        "Falha ao buscar produto",
    )
    if not current_response.data:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    previous_product = deepcopy(current_response.data)

    response = run_admin_query(
        db.table("products").update(data).eq("id", product_id),
        "Falha ao atualizar produto",
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    await audit_admin_action(
        db,
        admin,
        action="product.update",
        entity_type="product",
        entity_id=product_id,
        before_data=previous_product,
        after_data=response.data[0],
        metadata={"changed_fields": sorted(data.keys())},
    )
    return response.data[0]


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    admin: AdminContext = Depends(require_roles(*MANAGER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    current_response = run_admin_query(
        db.table("products").select("*").eq("id", product_id).single(),
        "Falha ao buscar produto",
    )
    previous_product = (
        deepcopy(current_response.data) if current_response.data else None
    )
    run_admin_query(
        db.table("products").delete().eq("id", product_id),
        "Falha ao excluir produto",
    )
    if previous_product:
        await audit_admin_action(
            db,
            admin,
            action="product.delete",
            entity_type="product",
            entity_id=product_id,
            before_data=previous_product,
        )
    return None


@router.get("/customers", response_model=list[CustomerOut])
async def list_customers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _admin: AdminContext = Depends(require_roles(*ALL_ADMIN_ROLES)),
    db: Client = Depends(get_admin_db),
):
    start, end = page_range(page, page_size)
    response = run_admin_query(
        db.table("profiles")
        .select("*")
        .order("created_at", desc=True)
        .range(start, end),
        "Falha ao listar clientes",
    )
    return response.data


@router.get("/customers/{customer_id}", response_model=CustomerOut)
async def get_customer(
    customer_id: str,
    _admin: AdminContext = Depends(require_roles(*ALL_ADMIN_ROLES)),
    db: Client = Depends(get_admin_db),
):
    response = run_admin_query(
        db.table("profiles").select("*").eq("id", customer_id).single(),
        "Falha ao buscar cliente",
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    return response.data


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    admin: AdminContext = Depends(require_roles(*MANAGER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    data = serialize_payload(payload, exclude_unset=True)
    current_response = run_admin_query(
        db.table("profiles").select("*").eq("id", customer_id).single(),
        "Falha ao buscar cliente",
    )
    if not current_response.data:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    previous_customer = deepcopy(current_response.data)

    response = run_admin_query(
        db.table("profiles").update(data).eq("id", customer_id),
        "Falha ao atualizar cliente",
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    await audit_admin_action(
        db,
        admin,
        action="customer.update",
        entity_type="customer",
        entity_id=customer_id,
        before_data=previous_customer,
        after_data=response.data[0],
        metadata={"changed_fields": sorted(data.keys())},
    )
    return response.data[0]


@router.get("/customers/{customer_id}/orders")
async def list_customer_orders(
    customer_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _admin: AdminContext = Depends(require_roles(*ALL_ADMIN_ROLES)),
    db: Client = Depends(get_admin_db),
):
    start, end = page_range(page, page_size)
    response = run_admin_query(
        db.table("orders")
        .select("*, order_items(*)")
        .eq("profile_id", customer_id)
        .order("placed_at", desc=True)
        .range(start, end),
        "Falha ao listar pedidos do cliente",
    )
    return [serialize_admin_order(db, order) for order in response.data]


@router.post("/promotions", response_model=PromotionOut, status_code=201)
async def create_promotion(
    payload: PromotionCreate,
    admin: AdminContext = Depends(require_roles(*MANAGER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    response = run_admin_query(
        db.table("promotions").insert(serialize_payload(payload)),
        "Falha ao criar promocao",
    )
    await audit_admin_action(
        db,
        admin,
        action="promotion.create",
        entity_type="promotion",
        entity_id=response.data[0].get("id"),
        after_data=response.data[0],
        metadata={"changed_fields": sorted(serialize_payload(payload).keys())},
    )
    return response.data[0]


@router.get("/promotions", response_model=list[PromotionOut])
async def list_promotions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _admin: AdminContext = Depends(require_roles(*MANAGER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    start, end = page_range(page, page_size)
    response = run_admin_query(
        db.table("promotions")
        .select("*")
        .order("created_at", desc=True)
        .range(start, end),
        "Falha ao listar promocoes",
    )
    return response.data


@router.get("/promotions/{promotion_id}", response_model=PromotionOut)
async def get_promotion(
    promotion_id: str,
    _admin: AdminContext = Depends(require_roles(*MANAGER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    response = run_admin_query(
        db.table("promotions").select("*").eq("id", promotion_id).single(),
        "Falha ao buscar promocao",
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Promocao nao encontrada")
    return response.data


@router.patch("/promotions/{promotion_id}", response_model=PromotionOut)
async def update_promotion(
    promotion_id: str,
    payload: PromotionUpdate,
    admin: AdminContext = Depends(require_roles(*MANAGER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    data = serialize_payload(payload, exclude_unset=True)
    current_response = run_admin_query(
        db.table("promotions").select("*").eq("id", promotion_id).single(),
        "Falha ao buscar promocao",
    )
    if not current_response.data:
        raise HTTPException(status_code=404, detail="Promocao nao encontrada")
    previous_promotion = deepcopy(current_response.data)

    response = run_admin_query(
        db.table("promotions").update(data).eq("id", promotion_id),
        "Falha ao atualizar promocao",
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Promocao nao encontrada")
    await audit_admin_action(
        db,
        admin,
        action="promotion.update",
        entity_type="promotion",
        entity_id=promotion_id,
        before_data=previous_promotion,
        after_data=response.data[0],
        metadata={"changed_fields": sorted(data.keys())},
    )
    return response.data[0]


@router.delete("/promotions/{promotion_id}", status_code=204)
async def delete_promotion(
    promotion_id: str,
    admin: AdminContext = Depends(require_roles(*MANAGER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    current_response = run_admin_query(
        db.table("promotions").select("*").eq("id", promotion_id).single(),
        "Falha ao buscar promocao",
    )
    previous_promotion = (
        deepcopy(current_response.data) if current_response.data else None
    )
    run_admin_query(
        db.table("promotions").delete().eq("id", promotion_id),
        "Falha ao excluir promocao",
    )
    if previous_promotion:
        await audit_admin_action(
            db,
            admin,
            action="promotion.delete",
            entity_type="promotion",
            entity_id=promotion_id,
            before_data=previous_promotion,
        )
    return None


@router.get("/reports", response_model=AdminReportsOut)
async def get_reports(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    _admin: AdminContext = Depends(require_roles(*MANAGER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    return await ReportService(db).get_admin_reports(
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def list_audit_logs(
    entity_type: str | None = Query(default=None),
    actor_profile_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _admin: AdminContext = Depends(require_roles(*OWNER_ROLES)),
    db: Client = Depends(get_admin_db),
):
    start, end = page_range(page, page_size)
    query = db.table("audit_logs").select("*")
    if entity_type:
        query = query.eq("entity_type", entity_type)
    if actor_profile_id:
        query = query.eq("actor_profile_id", actor_profile_id)
    response = run_admin_query(
        query.order("created_at", desc=True).range(start, end),
        "Falha ao listar auditoria",
    )
    return response.data


@router.get("/orders")
async def list_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _admin: AdminContext = Depends(require_roles(*ALL_ADMIN_ROLES)),
    db: Client = Depends(get_admin_db),
):
    start, end = page_range(page, page_size)
    query = db.table("orders").select("*, order_items(*)")
    if status_filter:
        query = query.eq("status", status_filter)
    response = run_admin_query(
        query.order("placed_at", desc=True).range(start, end),
        "Falha ao listar pedidos",
    )
    return [serialize_admin_order(db, order) for order in response.data]


@router.get("/orders/{order_id}")
async def get_order(
    order_id: str,
    _admin: AdminContext = Depends(require_roles(*ALL_ADMIN_ROLES)),
    db: Client = Depends(get_admin_db),
):
    response = run_admin_query(
        db.table("orders").select("*, order_items(*)").eq("id", order_id).single(),
        "Falha ao buscar pedido",
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    return serialize_admin_order(db, response.data)


@router.patch("/orders/{order_id}")
async def update_order(
    order_id: str,
    payload: AdminOrderUpdate,
    admin: AdminContext = Depends(require_roles(*ALL_ADMIN_ROLES)),
    db: Client = Depends(get_admin_db),
):
    data = serialize_payload(payload, exclude_unset=True)
    current_response = run_admin_query(
        db.table("orders").select("*").eq("id", order_id).single(),
        "Falha ao buscar pedido",
    )
    if not current_response.data:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    previous_order = deepcopy(current_response.data)
    previous_status = previous_order.get("status")

    next_status = data.get("status", previous_status)
    next_payment_status = data.get(
        "payment_status", previous_order.get("payment_status")
    )
    paid_required = {
        "preparing",
        "out_for_delivery",
        "delivered",
    }
    if next_status in paid_required and next_payment_status != "paid":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Confirme o pagamento antes de avancar o pedido.",
        )

    response = run_admin_query(
        db.table("orders").update(data).eq("id", order_id),
        "Falha ao atualizar pedido",
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")

    updated_order = response.data[0]
    status_changed = (
        "status" in data
        and updated_order.get("status") != previous_status
    )
    await audit_admin_action(
        db,
        admin,
        action="order.update",
        entity_type="order",
        entity_id=order_id,
        before_data=previous_order,
        after_data=updated_order,
        metadata={
            "changed_fields": sorted(data.keys()),
            "status_changed": status_changed,
        },
    )
    if status_changed:
        await NotificationService(db).safe_notify_order_status(updated_order)
    lifecycle = OrderLifecycleService(db)
    if (
        updated_order.get("payment_status") == "paid"
        and previous_order.get("payment_status") != "paid"
    ):
        await lifecycle.payment_approved(order_id)
        updated_order = lifecycle.get_order(order_id) or updated_order
    if status_changed and updated_order.get("status") == "out_for_delivery":
        await lifecycle.dispatch_paid_order(order_id)
    if status_changed and updated_order.get("status") == "delivered":
        await lifecycle.order_delivered(order_id)
    return serialize_admin_order(db, updated_order)
