do $$
begin
  if not exists (
    select 1
    from pg_type
    where typname = 'admin_role'
  ) then
    create type public.admin_role as enum ('owner', 'manager', 'staff');
  end if;
end $$;

create table if not exists public.admin_users (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null unique references public.profiles(id) on delete cascade,
  role public.admin_role not null default 'staff',
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists admin_users_profile_id_idx
  on public.admin_users(profile_id);

alter table public.admin_users enable row level security;

do $$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'admin_users_set_updated_at'
  ) then
    create trigger admin_users_set_updated_at
    before update on public.admin_users
    for each row execute function public.set_updated_at();
  end if;
end $$;

drop policy if exists "Admin users can view their own role"
on public.admin_users;

create policy "Admin users can view their own role"
on public.admin_users
for select
to authenticated
using (profile_id = auth.uid());

grant select on public.admin_users to authenticated;

-- Depois de criar um usuario no Supabase Auth, promova-o pelo SQL Editor:
--
-- insert into public.admin_users (profile_id, role)
-- values ('UUID_DO_USUARIO', 'owner')
-- on conflict (profile_id) do update
-- set role = excluded.role,
--     active = true,
--     updated_at = now();
