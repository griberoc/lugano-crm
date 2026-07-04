-- Trava final de RLS para tabelas sensiveis.
-- O cliente pode ler apenas os proprios pedidos; escrita segue pelo backend.

alter table public.orders enable row level security;
alter table public.order_items enable row level security;
alter table public.audit_logs enable row level security;

alter table public.orders force row level security;
alter table public.order_items force row level security;
alter table public.audit_logs force row level security;

do $$
declare
  policy_record record;
begin
  for policy_record in
    select tablename, policyname
    from pg_policies
    where schemaname = 'public'
      and tablename in ('orders', 'order_items', 'audit_logs')
  loop
    execute format(
      'drop policy if exists %I on public.%I',
      policy_record.policyname,
      policy_record.tablename
    );
  end loop;
end $$;

create policy "Users can view their own orders"
on public.orders
for select
to authenticated
using (profile_id = auth.uid());

create policy "Users can view items from their own orders"
on public.order_items
for select
to authenticated
using (
  exists (
    select 1
    from public.orders
    where orders.id = order_items.order_id
      and orders.profile_id = auth.uid()
  )
);

revoke all on public.orders from anon;
revoke all on public.order_items from anon;
revoke all on public.audit_logs from anon;
revoke all on public.audit_logs from authenticated;

revoke insert, update, delete on public.orders from authenticated;
revoke insert, update, delete on public.order_items from authenticated;

grant select on public.orders to authenticated;
grant select on public.order_items to authenticated;
