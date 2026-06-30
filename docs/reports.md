# Relatorios

Os relatorios administrativos ficam em:

```text
GET /api/v1/admin/reports
```

Filtros opcionais:

```text
date_from=YYYY-MM-DD
date_to=YYYY-MM-DD
```

## Permissao

Disponivel para `owner` e `manager`.
Usuarios `staff` nao acessam dados financeiros.

## Criterios

- Faturamento bruto soma `subtotal` de pedidos nao cancelados.
- Faturamento liquido soma `total` de pedidos nao cancelados.
- Ticket medio usa faturamento liquido dividido por pedidos nao cancelados.
- Pedidos cancelados nao entram em faturamento, ticket medio, produtos vendidos ou clientes recorrentes.
- Produtos mais vendidos agregam `order_items`.
- Clientes recorrentes exigem pelo menos 2 pedidos validos no periodo.
- Uso de cupons usa `promotion_usages.used_at`.

## Resposta

O endpoint retorna:

- `summary`
- `top_products`
- `recurring_customers`
- `coupon_usage`
