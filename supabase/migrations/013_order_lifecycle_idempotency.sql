create unique index if not exists loyalty_transactions_one_earn_per_order_idx
  on public.loyalty_transactions(order_id)
  where order_id is not null and type = 'earn';

create unique index if not exists delivery_dispatches_one_active_per_order_idx
  on public.delivery_dispatches(order_id)
  where status not in ('failed', 'cancelled');
