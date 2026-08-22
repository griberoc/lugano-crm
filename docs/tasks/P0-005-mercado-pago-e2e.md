# P0-005 - Mercado Pago end-to-end

Prioridade: P0
Epic: PAY
Status: Done
Branch sugerida: `feature/P0-005-mercado-pago-e2e`

## Objetivo

Validar Pix dinamico Mercado Pago do pedido ate atualizacao automatica por
webhook.

## Checklist

- [x] Configurar `PAYMENT_PROVIDER=mercado_pago`.
- [x] Configurar token de teste no backend.
- [x] Configurar URL publica de webhook.
- [x] Criar pedido real de teste.
- [x] Ver QR Code no checkout.
- [x] Ver copia-e-cola.
- [x] Validar webhook recebido.
- [x] Validar `payment_status=paid`.
- [x] Confirmar admin exibindo status correto.

## Criterios de aceite

- [x] Cliente consegue gerar Pix dinamico.
- [x] Webhook atualiza pedido automaticamente.
- [x] Token Mercado Pago nunca aparece no frontend.
- [x] Falha de pagamento aparece de forma clara.

## Validacao

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_payment_service.py
```

Procedimento local, staging e producao: `docs/mercado-pago-e2e.md`.
