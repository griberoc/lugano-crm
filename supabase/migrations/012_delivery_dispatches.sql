create table if not exists public.delivery_dispatches (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  provider text not null default 'manual',
  status text not null default 'pending',
  external_delivery_id text,
  external_quote_id text,
  tracking_url text,
  request_payload jsonb not null default '{}'::jsonb,
  response_payload jsonb not null default '{}'::jsonb,
  error text,
  dispatched_at timestamptz,
  cancelled_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists delivery_dispatches_order_id_idx
  on public.delivery_dispatches(order_id);

create index if not exists delivery_dispatches_status_created_at_idx
  on public.delivery_dispatches(status, created_at desc);

alter table public.delivery_dispatches enable row level security;

do $$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'delivery_dispatches_set_updated_at'
  ) then
    create trigger delivery_dispatches_set_updated_at
    before update on public.delivery_dispatches
    for each row execute function public.set_updated_at();
  end if;
end $$;

drop policy if exists "Users can view delivery dispatches from their own orders"
on public.delivery_dispatches;

create policy "Users can view delivery dispatches from their own orders"
on public.delivery_dispatches
for select
to authenticated
using (
  exists (
    select 1
    from public.orders
    where orders.id = delivery_dispatches.order_id
      and orders.profile_id = auth.uid()
  )
);

grant select on public.delivery_dispatches to authenticated;
