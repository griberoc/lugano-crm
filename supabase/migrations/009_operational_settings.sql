create table if not exists public.operational_settings (
  key text primary key,
  value jsonb not null,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.operational_settings enable row level security;

do $$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'operational_settings_set_updated_at'
  ) then
    create trigger operational_settings_set_updated_at
    before update on public.operational_settings
    for each row execute function public.set_updated_at();
  end if;
end $$;
