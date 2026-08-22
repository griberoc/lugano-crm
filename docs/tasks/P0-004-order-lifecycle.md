# P0-004 - Ciclo correto do pedido

Prioridade: P0
Epic: CORE/PAY/DLV
Status: Done
Branch sugerida: `feature/P0-004-order-lifecycle`

## Objetivo

Garantir que pagamento, fidelidade e entrega acontecam na ordem correta.

## Regra alvo

```text
Pedido criado -> pagamento pendente -> pagamento aprovado -> confirmar pedido
-> preparar -> enviar entrega -> entregue -> fidelidade
```

## Checklist

- [x] Remover credito imediato de pontos na criacao do pedido.
- [x] Creditar pontos apenas apos pagamento aprovado ou entrega.
- [x] Bloquear despacho Machine antes de pagamento/confirmacao.
- [x] Tornar webhook Mercado Pago idempotente.
- [x] Evitar duplicidade de pontos.
- [x] Evitar duplicidade de entrega.
- [x] Atualizar admin para refletir estados corretos.

## Criterios de aceite

- [x] Pedido pendente nao gera pontos.
- [x] Pedido pendente nao solicita entrega.
- [x] Pagamento aprovado atualiza fluxo corretamente.
- [x] Repetir webhook nao duplica efeitos.

## Validacao

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_order_service.py tests\unit\test_payment_service.py tests\unit\test_delivery_service.py
```
