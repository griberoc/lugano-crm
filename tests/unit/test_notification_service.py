from app.core.config import settings
from app.services.notification import NotificationService


def configure_notifications():
    previous = {
        "notifications_enabled": settings.notifications_enabled,
        "notification_email_enabled": settings.notification_email_enabled,
        "notification_whatsapp_enabled": settings.notification_whatsapp_enabled,
        "notification_email_webhook_url": settings.notification_email_webhook_url,
        "notification_whatsapp_webhook_url": settings.notification_whatsapp_webhook_url,
    }
    settings.notifications_enabled = True
    settings.notification_email_enabled = True
    settings.notification_whatsapp_enabled = True
    settings.notification_email_webhook_url = None
    settings.notification_whatsapp_webhook_url = None
    return previous


def restore_notifications(previous):
    for key, value in previous.items():
        setattr(settings, key, value)


def add_profile(fake_db, *, accepts_whatsapp=True):
    fake_db.tables["profiles"].append(
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "full_name": "Cliente Lugano",
            "email": "cliente@lugano.test",
            "phone": "11999999999",
            "preferences": {"accepts_whatsapp": accepts_whatsapp},
        }
    )


def make_order(status="pending"):
    return {
        "id": "22222222-2222-2222-2222-222222222222",
        "profile_id": "11111111-1111-1111-1111-111111111111",
        "status": status,
        "total": "24.90",
    }


async def test_notification_service_queues_email_and_whatsapp(fake_db):
    previous = configure_notifications()
    add_profile(fake_db)

    try:
        events = await NotificationService(fake_db).notify_order_status(make_order())
    finally:
        restore_notifications(previous)

    assert len(events) == 2
    assert {event["channel"] for event in events} == {"email", "whatsapp"}
    assert {event["status"] for event in events} == {"queued"}
    assert fake_db.tables["notification_events"][0]["event_type"] == "order_created"


async def test_notification_service_respects_whatsapp_preference(fake_db):
    previous = configure_notifications()
    add_profile(fake_db, accepts_whatsapp=False)

    try:
        events = await NotificationService(fake_db).notify_order_status(
            make_order(status="confirmed")
        )
    finally:
        restore_notifications(previous)

    assert len(events) == 1
    assert events[0]["channel"] == "email"
    assert events[0]["event_type"] == "order_confirmed"


async def test_safe_notify_alerts_dispatch_exception(fake_db, monkeypatch):
    alerts = []

    async def broken_notify(_self, _order):
        raise RuntimeError("boom")

    async def fake_alert(**kwargs):
        alerts.append(kwargs)
        return True

    monkeypatch.setattr(NotificationService, "notify_order_status", broken_notify)
    monkeypatch.setattr(
        "app.services.notification.send_monitoring_alert",
        fake_alert,
    )

    events = await NotificationService(fake_db).safe_notify_order_status(make_order())

    assert events == []
    assert alerts[0]["title"] == "Falha geral de notificacao"
    assert alerts[0]["metadata"]["check"] == "notification_dispatch"
