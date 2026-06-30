# Notificacoes

O sistema registra notificacoes transacionais em `public.notification_events`.
Os eventos cobertos sao:

- `order_created`
- `order_confirmed`
- `order_out_for_delivery`
- `order_delivered`

## Como ativar no Supabase

Rode a migration:

```sql
supabase/migrations/007_notifications.sql
```

A tabela fica com RLS ligada e sem acesso direto para `anon` ou `authenticated`.
O backend grava os eventos usando `SUPABASE_SERVICE_ROLE_KEY`.

## Funcionamento local

Com os webhooks vazios, o backend cria os eventos com status `queued`.
Isso permite testar o fluxo e auditar o que seria enviado sem contratar um
provedor ainda.

## Envio por webhook

Configure no `.env`:

```env
NOTIFICATIONS_ENABLED=true
NOTIFICATION_EMAIL_ENABLED=true
NOTIFICATION_WHATSAPP_ENABLED=true
NOTIFICATION_EMAIL_WEBHOOK_URL=https://seu-provedor/email
NOTIFICATION_EMAIL_WEBHOOK_TOKEN=token-opcional
NOTIFICATION_WHATSAPP_WEBHOOK_URL=https://seu-provedor/whatsapp
NOTIFICATION_WHATSAPP_WEBHOOK_TOKEN=token-opcional
```

O payload enviado ao webhook:

```json
{
  "event_type": "order_confirmed",
  "channel": "email",
  "recipient": "cliente@email.com",
  "subject": "Pedido confirmado",
  "message": "Ola, Cliente! Seu pedido #12345678 foi confirmado...",
  "order_id": "uuid-do-pedido",
  "profile_id": "uuid-do-cliente"
}
```

## WhatsApp

O envio por WhatsApp respeita `profiles.preferences.accepts_whatsapp`.
Se o cliente nao tiver telefone, o evento fica como `skipped`.

## Status dos eventos

- `queued`: evento criado, mas sem webhook configurado.
- `sent`: webhook respondeu com sucesso.
- `failed`: webhook retornou erro ou timeout.
- `skipped`: faltou destinatario ou canal nao aplicavel.

Quando um envio fica como `failed`, a API tambem registra log de erro e tenta
disparar alerta para `MONITORING_WEBHOOK_URL`, se configurado.
