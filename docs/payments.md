# Pagamentos

## Decisao recomendada

Para o primeiro delivery real, use:

```env
PAYMENT_PROVIDER=pix_static
PIX_KEY=sua-chave-pix-da-empresa
```

Esse fluxo gera Pix copia e cola no checkout, mas mantem a confirmacao do
pagamento manual pelo admin. E o melhor equilibrio para comecar porque:

- nao depende de homologacao de gateway;
- nao trava o pedido se o provedor cair;
- permite validar operacao real da cafeteria;
- mantem controle humano sobre fraude, troco e atendimento.

O admin confirma o pagamento atualizando `payment_status` para `paid` na tela de
pedidos.

## Modos suportados

| `PAYMENT_PROVIDER` | Uso |
| --- | --- |
| `manual` | Pix informado pela equipe, dinheiro ou cartao na entrega |
| `pix_static` | Pix copia e cola gerado pelo backend |
| `mercado_pago` | Reservado para integracao com gateway e webhook |

## Pix copia e cola

Variaveis:

```env
PAYMENT_PROVIDER=pix_static
PIX_KEY=sua-chave-pix-da-empresa
PIX_MERCHANT_NAME=Lugano
PIX_MERCHANT_CITY=Gramado
PIX_TXID_PREFIX=LUG
PIX_EXPIRES_MINUTES=30
```

Ao criar um pedido com `payment_method = pix`, a API devolve:

```json
{
  "payment_provider": "pix_static",
  "payment_status": "pending",
  "payment_instructions": {
    "title": "Pix copia e cola",
    "method": "pix",
    "status": "pending",
    "pix_key": "sua-chave-pix-da-empresa",
    "pix_copy_paste": "000201...",
    "txid": "LUG...",
    "expires_at": "..."
  }
}
```

O frontend de delivery exibe o codigo e um botao para copiar.

## Mercado Pago

A integracao Mercado Pago deve ser a segunda fase, quando voce quiser:

- confirmacao automatica do pagamento;
- conciliacao por `payment_reference`;
- webhook para mudar `payment_status` para `paid`;
- suporte a checkout/gateway com cartao.

Documentacao oficial consultada:

- https://www.mercadopago.com.br/developers/pt/docs/checkout-api/payment-methods/pix

Antes de ativar, crie uma conta de vendedor, gere credenciais de producao,
configure URL publica de webhook e valide em sandbox/homologacao.
