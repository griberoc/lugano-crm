create extension if not exists "pgcrypto";

create type order_status as enum (
  'pending',
  'confirmed',
  'preparing',
  'out_for_delivery',
  'delivered',
  'cancelled'
);

create type payment_method as enum (
  'credit_card',
  'debit_card',
  'pix',
  'cash'
);

create type payment_status as enum (
  'pending',
  'paid',
  'failed',
  'refunded'
);

create type loyalty_transaction_type as enum (
  'earn',
  'redeem',
  'expire',
  'bonus'
);

create type promotion_type as enum (
  'percentage',
  'fixed',
  'free_delivery'
);

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  phone text,
  email text,
  birth_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.addresses (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  label text not null,
  street text not null,
  number text not null,
  complement text,
  neighborhood text not null,
  city text not null,
  zip_code text not null,
  is_default boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.products (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text,
  category text not null default 'cafeteria',
  price numeric(10, 2) not null check (price >= 0),
  available boolean not null default true,
  image_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.orders (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete restrict,
  address_id uuid not null references public.addresses(id) on delete restrict,
  status order_status not null default 'pending',
  payment_method payment_method not null,
  payment_status payment_status not null default 'pending',
  subtotal numeric(10, 2) not null check (subtotal >= 0),
  delivery_fee numeric(10, 2) not null default 0 check (delivery_fee >= 0),
  discount numeric(10, 2) not null default 0 check (discount >= 0),
  total numeric(10, 2) not null check (total >= 0),
  notes text,
  placed_at timestamptz not null default now(),
  delivered_at timestamptz,
  updated_at timestamptz not null default now()
);

create table public.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete restrict,
  quantity integer not null check (quantity > 0),
  unit_price numeric(10, 2) not null check (unit_price >= 0),
  customization text,
  created_at timestamptz not null default now()
);

create table public.loyalty_tiers (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  min_points integer not null unique check (min_points >= 0),
  cashback_rate numeric(5, 2) not null default 0 check (cashback_rate >= 0),
  benefits jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.loyalty_accounts (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null unique references public.profiles(id) on delete cascade,
  tier_id uuid not null references public.loyalty_tiers(id),
  total_points integer not null default 0 check (total_points >= 0),
  available_points integer not null default 0 check (available_points >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.loyalty_transactions (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.loyalty_accounts(id) on delete cascade,
  order_id uuid references public.orders(id) on delete set null,
  type loyalty_transaction_type not null,
  points integer not null,
  description text not null,
  created_at timestamptz not null default now()
);

create table public.promotions (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  description text,
  type promotion_type not null,
  value numeric(10, 2) not null default 0 check (value >= 0),
  min_order_cents integer not null default 0 check (min_order_cents >= 0),
  max_uses integer check (max_uses is null or max_uses > 0),
  uses_count integer not null default 0 check (uses_count >= 0),
  active boolean not null default true,
  starts_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.promotion_usages (
  id uuid primary key default gen_random_uuid(),
  promotion_id uuid not null references public.promotions(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  order_id uuid not null references public.orders(id) on delete cascade,
  discount_applied numeric(10, 2) not null default 0 check (discount_applied >= 0),
  used_at timestamptz not null default now(),
  unique (promotion_id, profile_id)
);

create index addresses_profile_id_idx on public.addresses(profile_id);
create index products_available_idx on public.products(available);
create index orders_profile_id_placed_at_idx on public.orders(profile_id, placed_at desc);
create index order_items_order_id_idx on public.order_items(order_id);
create index loyalty_transactions_account_id_created_at_idx
  on public.loyalty_transactions(account_id, created_at desc);
create index promotions_active_code_idx on public.promotions(active, code);
create index promotion_usages_profile_id_idx on public.promotion_usages(profile_id);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create trigger addresses_set_updated_at
before update on public.addresses
for each row execute function public.set_updated_at();

create trigger products_set_updated_at
before update on public.products
for each row execute function public.set_updated_at();

create trigger orders_set_updated_at
before update on public.orders
for each row execute function public.set_updated_at();

create trigger loyalty_accounts_set_updated_at
before update on public.loyalty_accounts
for each row execute function public.set_updated_at();

create trigger promotions_set_updated_at
before update on public.promotions
for each row execute function public.set_updated_at();

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  starter_tier_id uuid;
begin
  select id into starter_tier_id
  from public.loyalty_tiers
  order by min_points asc
  limit 1;

  insert into public.profiles (id, email, full_name)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name')
  )
  on conflict (id) do nothing;

  if starter_tier_id is not null then
    insert into public.loyalty_accounts (profile_id, tier_id)
    values (new.id, starter_tier_id)
    on conflict (profile_id) do nothing;
  end if;

  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

create or replace function public.increment_promotion_uses(promo_id uuid)
returns void
language sql
security definer
as $$
  update public.promotions
  set uses_count = uses_count + 1
  where id = promo_id;
$$;

insert into public.loyalty_tiers (name, min_points, cashback_rate, benefits)
values
  ('Bronze', 0, 0.00, '{"description": "Entrada no programa Lugano Rewards"}'),
  ('Prata', 1000, 2.00, '{"description": "Beneficios intermediarios e campanhas exclusivas"}'),
  ('Ouro', 3000, 5.00, '{"description": "Melhor cashback e prioridade em promocoes"}')
on conflict (name) do nothing;

insert into public.products (name, description, category, price, available)
values
  ('Cappuccino Lugano', 'Cappuccino cremoso da casa', 'cafeteria', 16.90, true),
  ('Chocolate Quente Lugano', 'Chocolate quente especial', 'chocolateria', 19.90, true),
  ('Brownie de Chocolate', 'Brownie artesanal de chocolate', 'chocolateria', 14.90, true)
on conflict do nothing;

insert into public.promotions (
  code,
  description,
  type,
  value,
  min_order_cents,
  max_uses,
  active
)
values
  ('LUGANO10', '10% de desconto no pedido', 'percentage', 10, 3000, 500, true),
  ('FRETEGRATIS', 'Frete gratis em pedidos selecionados', 'free_delivery', 0, 4000, 300, true)
on conflict (code) do nothing;
