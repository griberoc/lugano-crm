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

  insert into public.profiles (id, email, full_name, phone)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'),
    new.raw_user_meta_data->>'phone'
  )
  on conflict (id) do update
  set
    email = excluded.email,
    full_name = coalesce(public.profiles.full_name, excluded.full_name),
    phone = coalesce(public.profiles.phone, excluded.phone);

  if starter_tier_id is not null then
    insert into public.loyalty_accounts (profile_id, tier_id)
    values (new.id, starter_tier_id)
    on conflict (profile_id) do nothing;
  end if;

  return new;
end;
$$;
