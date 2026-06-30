# Monitoramento

Este guia cobre o minimo operacional antes do deploy: logs mais claros,
healthcheck de producao, alerta de API fora do ar e alerta de notificacao
falhando.

## Logs da API

A API registra:

- erros nao tratados com metodo, rota, `request_id`, duracao e cliente;
- respostas HTTP `5xx`;
- falhas de envio de notificacao por email/WhatsApp;
- falhas ao disparar o webhook de alerta.

Toda resposta recebe o header `X-Request-ID`. Use esse valor para procurar a
mesma requisicao nos logs do Render, Railway, Fly.io ou VPS.

## Healthchecks

Existem dois endpoints:

```text
GET /health
GET /health/ready
```

Use `/health` como liveness check da plataforma. Ele confirma que o processo da
API esta no ar.

Use `/health/ready` para monitoramento externo. Ele tambem testa o Supabase
quando `HEALTHCHECK_SUPABASE_ENABLED=true`. Se o Supabase falhar, a resposta
volta com HTTP `503`.

## Webhook de alerta

Configure um webhook generico no `.env.production`:

```env
MONITORING_ALERTS_ENABLED=true
MONITORING_WEBHOOK_URL=https://seu-monitoramento/webhook
MONITORING_WEBHOOK_TOKEN=token-opcional
MONITORING_SERVICE_NAME=lugano-crm
MONITORING_WEBHOOK_TIMEOUT_SECONDS=5
```

Esse webhook pode apontar para Make, Zapier, n8n, Discord, Slack, Better Stack
ou outro provedor.

Payload enviado:

```json
{
  "service": "lugano-crm",
  "environment": "production",
  "severity": "critical",
  "title": "API Lugano indisponivel",
  "message": "API healthcheck returned 503...",
  "metadata": {},
  "created_at": "2026-06-29T12:00:00Z"
}
```

## Alerta se notificacao falhar

Quando o webhook de email/WhatsApp retorna erro ou timeout, o backend:

1. grava `notification_events.status = failed`;
2. grava o erro em `notification_events.error`;
3. registra log de erro;
4. dispara alerta para `MONITORING_WEBHOOK_URL`, se configurado.

## Monitor externo

Para checar a API e notificacoes recentes fora do processo da API, rode:

```powershell
.\.venv\Scripts\python.exe scripts\monitor_api.py --env-file .env.production
```

O script verifica:

- `/health/ready`;
- `notification_events` com `status = failed` nos ultimos 60 minutos.

Se `MONITORING_WEBHOOK_URL` estiver vazio, o alerta e impresso no terminal. Em
producao, agende esse script em um cron, GitHub Actions, Render Cron Job,
Railway cron ou agendador da VPS.

Exemplo com janela de 15 minutos:

```powershell
.\.venv\Scripts\python.exe scripts\monitor_api.py --env-file .env.production --failed-notification-window-minutes 15
```

## Rotina recomendada

- Plataforma de deploy: usar `/health` como health check.
- Monitor externo: usar `/health/ready` a cada 1 ou 5 minutos.
- Notificacoes: investigar qualquer alerta `Notificacoes com falha`.
- Logs: procurar pelo `X-Request-ID` em erros reportados pelo frontend.
