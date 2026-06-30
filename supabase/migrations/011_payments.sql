alter table public.orders
add column if not exists payment_provider text not null default 'manual' check (
  payment_provider in ('manual', 'pix_static', 'mercado_pago')
),
add column if not exists payment_reference text,
add column if not exists payment_payload jsonb not null default '{}'::jsonb,
add column if not exists paid_at timestamptz;

create index if not exists orders_payment_status_idx
  on public.orders(payment_status);

create index if not exists orders_payment_provider_reference_idx
  on public.orders(payment_provider, payment_reference);
