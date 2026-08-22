# Mercado Pago Pix - validacao end-to-end

Este guia separa a simulacao local, a homologacao em staging e a ativacao em
producao. Tokens e segredos pertencem exclusivamente ao backend e ao cofre de
segredos do provedor de deploy. Nunca os copie para `frontend/config.js`, para
arquivos versionados ou para capturas de tela.

## Fluxo esperado

```text
checkout -> POST /orders -> Mercado Pago cria Pix -> QR Code/copia-e-cola
-> Mercado Pago chama webhook assinado -> backend consulta o pagamento
-> valida pedido, valor e moeda -> payment_status=paid -> pedido confirmado
```

O checkout consulta o pedido enquanto o pagamento estiver pendente e mostra a
confirmacao sem exigir recarregamento manual. Webhooks repetidos sao seguros e
uma notificacao antiga nao pode regredir um pedido pago.

## Local - sem credencial externa

Use o provedor manual para desenvolvimento comum:

```env
APP_ENV=development
PAYMENT_PROVIDER=manual
```

Os testes automatizados simulam respostas do Mercado Pago e nao fazem chamadas
externas:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_payment_service.py tests\unit\test_payment_endpoints.py tests\unit\test_order_service.py
```

## Staging - credenciais de teste

Use uma aplicacao e usuarios de teste do Mercado Pago. Configure no cofre do
backend, sem preencher valores reais em arquivos do repositorio:

```env
APP_ENV=staging
PAYMENT_PROVIDER=mercado_pago
MERCADO_PAGO_ACCESS_TOKEN=<token-de-teste>
MERCADO_PAGO_NOTIFICATION_URL=https://api-staging.exemplo.com/api/v1/payments/mercado-pago/webhook
MERCADO_PAGO_WEBHOOK_SECRET=<segredo-do-webhook-de-staging>
```

No painel do Mercado Pago, cadastre exatamente a URL HTTPS pública do webhook.
Depois:

1. Entre no checkout com um cliente de teste e endereço de staging.
2. Crie um pedido Pix e confira QR Code, copia-e-cola, valor e status pendente.
3. Pague com uma conta compradora de teste diferente da conta vendedora.
4. Confirme nos logs o processamento, sem conteúdo de token ou assinatura.
5. Confirme `payment_status=paid`, `status=confirmed` e `paid_at` no pedido.
6. Confirme no admin a etiqueta `Pago` e no checkout a atualização automática.
7. Reenvie a notificação e confirme que pontos e efeitos não duplicaram.
8. Simule pagamento rejeitado e confirme a mensagem clara no checkout.

## Producao

Crie credenciais e segredo de webhook próprios de produção; não reutilize os de
staging. Configure as mesmas variáveis no cofre do backend com a URL pública de
produção. Antes de ativar tráfego real:

1. valide HTTPS e assinatura obrigatória do webhook;
2. confirme que `/health` informa `payment_provider=mercado_pago`;
3. faça um pedido de baixo valor autorizado pela operação;
4. concilie valor, moeda, identificador do pagamento e pedido;
5. confirme que nenhum arquivo servido em `frontend/` contém nomes ou valores
   de `MERCADO_PAGO_ACCESS_TOKEN` ou `MERCADO_PAGO_WEBHOOK_SECRET`.

Para voltar temporariamente ao fluxo manual, altere somente no backend:

```env
PAYMENT_PROVIDER=manual
```
