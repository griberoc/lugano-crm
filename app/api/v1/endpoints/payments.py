import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.core.config import settings
from app.db.client import get_supabase_admin
from app.services.audit import AuditService
from app.services.order_lifecycle import OrderLifecycleService
from app.services.payment import (
    PaymentNotFoundError,
    PaymentProviderError,
    PaymentService,
    verify_mercado_pago_signature,
)
from supabase import Client

router = APIRouter(prefix="/payments", tags=["pagamentos"])
logger = logging.getLogger("lugano.payments")


@router.post("/mercado-pago/webhook")
async def mercado_pago_webhook(
    request: Request,
    data_id: str | None = Query(default=None, alias="data.id"),
    x_signature: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
    db: Client = Depends(get_supabase_admin),
) -> dict[str, Any]:
    """Recebe notificacoes de pagamento do Mercado Pago e atualiza pedidos."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    body_data = body.get("data") if isinstance(body, dict) else {}
    if not isinstance(body_data, dict):
        body_data = {}

    payment_id = data_id or body_data.get("id") or (body or {}).get("id")
    if not payment_id:
        return {"received": True, "ignored": True, "reason": "missing_payment_id"}

    if not verify_mercado_pago_signature(
        x_signature=x_signature,
        x_request_id=x_request_id,
        data_id=str(payment_id),
        secret=settings.mercado_pago_webhook_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Assinatura Mercado Pago invalida",
        )

    try:
        result = PaymentService().sync_mercado_pago_payment(
            db=db,
            payment_id=str(payment_id),
        )
    except PaymentNotFoundError:
        logger.info(
            "Mercado Pago webhook ignored unknown payment_id=%s",
            payment_id,
        )
        return {
            "received": True,
            "ignored": True,
            "reason": "payment_not_found",
            "payment_id": str(payment_id),
        }
    except PaymentProviderError as exc:
        logger.exception("Mercado Pago sync failed payment_id=%s", payment_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel confirmar o pagamento agora. Tente novamente.",
        ) from exc

    logger.info(
        "Mercado Pago webhook processed payment_id=%s order_id=%s status=%s reason=%s",
        payment_id,
        result.get("order_id"),
        result.get("payment_status"),
        result.get("reason"),
    )
    await AuditService(db).safe_record(
        actor=None,
        action="payment.webhook",
        entity_type="order",
        entity_id=result.get("order_id"),
        after_data={"payment_status": result.get("payment_status")},
        metadata={
            "provider": "mercado_pago",
            "payment_id": str(payment_id),
            "updated": result.get("updated", False),
            "reason": result.get("reason"),
        },
    )
    if result.get("payment_status") == "paid" and result.get("order_id"):
        await OrderLifecycleService(db).payment_approved(result["order_id"])
    return {"received": True, **result}
