alter table public.profiles enable row level security;
alter table public.addresses enable row level security;
alter table public.products enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;
alter table public.loyalty_tiers enable row level security;
alter table public.loyalty_accounts enable row level security;
alter table public.loyalty_transactions enable row level security;
alter table public.promotions enable row level security;
alter table public.promotion_usages enable row level security;

create policy "Users can view their own profile"
on public.profiles
for select
to authenticated
using (id = auth.uid());

create policy "Users can update their own profile"
on public.profiles
for update
to authenticated
using (id = auth.uid())
with check (id = auth.uid());

create policy "Users can insert their own profile"
on public.profiles
for insert
to authenticated
with check (id = auth.uid());

create policy "Users can manage their own addresses"
on public.addresses
for all
to authenticated
using (profile_id = auth.uid())
with check (profile_id = auth.uid());

create policy "Anyone can view products"
on public.products
for select
to anon, authenticated
using (true);

create policy "Users can view their own orders"
on public.orders
for select
to authenticated
using (profile_id = auth.uid());

create policy "Users can create their own orders"
on public.orders
for insert
to authenticated
with check (profile_id = auth.uid());

create policy "Users can cancel their own open orders"
on public.orders
for update
to authenticated
using (
  profile_id = auth.uid()
  and status in ('pending', 'confirmed')
)
with check (
  profile_id = auth.uid()
  and status in ('pending', 'confirmed', 'cancelled')
);

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

create policy "Users can create items for their own orders"
on public.order_items
for insert
to authenticated
with check (
  exists (
    select 1
    from public.orders
    where orders.id = order_items.order_id
      and orders.profile_id = auth.uid()
  )
);

create policy "Anyone can view loyalty tiers"
on public.loyalty_tiers
for select
to anon, authenticated
using (true);

create policy "Users can view their own loyalty account"
on public.loyalty_accounts
for select
to authenticated
using (profile_id = auth.uid());

create policy "Users can update their own loyalty account"
on public.loyalty_accounts
for update
to authenticated
using (profile_id = auth.uid())
with check (profile_id = auth.uid());

create policy "Users can view their own loyalty transactions"
on public.loyalty_transactions
for select
to authenticated
using (
  exists (
    select 1
    from public.loyalty_accounts
    where loyalty_accounts.id = loyalty_transactions.account_id
      and loyalty_accounts.profile_id = auth.uid()
  )
);

create policy "Users can create loyalty transactions for their account"
on public.loyalty_transactions
for insert
to authenticated
with check (
  exists (
    select 1
    from public.loyalty_accounts
    where loyalty_accounts.id = loyalty_transactions.account_id
      and loyalty_accounts.profile_id = auth.uid()
  )
);

create policy "Authenticated users can view active promotions"
on public.promotions
for select
to authenticated
using (active = true);

create policy "Users can view their own promotion usages"
on public.promotion_usages
for select
to authenticated
using (profile_id = auth.uid());

create policy "Users can register their own promotion usages"
on public.promotion_usages
for insert
to authenticated
with check (profile_id = auth.uid());

grant usage on schema public to anon, authenticated;

grant select on public.products to anon, authenticated;
grant select on public.loyalty_tiers to anon, authenticated;

grant select, insert, update on public.profiles to authenticated;
grant select, insert, update, delete on public.addresses to authenticated;
grant select, insert, update on public.orders to authenticated;
grant select, insert on public.order_items to authenticated;
grant select, update on public.loyalty_accounts to authenticated;
grant select, insert on public.loyalty_transactions to authenticated;
grant select on public.promotions to authenticated;
grant select, insert on public.promotion_usages to authenticated;

grant execute on function public.increment_promotion_uses(uuid) to authenticated;
