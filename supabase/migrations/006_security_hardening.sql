-- Endurecimento de acesso direto pelo cliente Supabase.
-- Escritas criticas passam pelo backend com service role.

drop policy if exists "Anyone can view products"
on public.products;

drop policy if exists "Anyone can view available products"
on public.products;

create policy "Anyone can view available products"
on public.products
for select
to anon, authenticated
using (available = true);

drop policy if exists "Authenticated users can view active promotions"
on public.promotions;

drop policy if exists "Authenticated users can view usable promotions"
on public.promotions;

create policy "Authenticated users can view usable promotions"
on public.promotions
for select
to authenticated
using (
  active = true
  and (starts_at is null or starts_at <= now())
  and (expires_at is null or expires_at >= now())
  and (max_uses is null or uses_count < max_uses)
);

drop policy if exists "Users can create their own orders"
on public.orders;

drop policy if exists "Users can cancel their own open orders"
on public.orders;

drop policy if exists "Users can create items for their own orders"
on public.order_items;

drop policy if exists "Users can update their own loyalty account"
on public.loyalty_accounts;

drop policy if exists "Users can create loyalty transactions for their account"
on public.loyalty_transactions;

drop policy if exists "Users can register their own promotion usages"
on public.promotion_usages;

revoke insert, update on public.orders from authenticated;
revoke insert on public.order_items from authenticated;
revoke update on public.loyalty_accounts from authenticated;
revoke insert on public.loyalty_transactions from authenticated;
revoke insert on public.promotion_usages from authenticated;

grant select on public.orders to authenticated;
grant select on public.order_items to authenticated;
grant select on public.loyalty_accounts to authenticated;
grant select on public.loyalty_transactions to authenticated;
grant select on public.promotion_usages to authenticated;
