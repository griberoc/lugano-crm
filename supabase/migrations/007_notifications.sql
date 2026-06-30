create table if not exists public.notification_events (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.profiles(id) on delete set null,
  order_id uuid references public.orders(id) on delete set null,
  event_type text not null check (
    event_type in (
      'order_created',
      'order_confirmed',
      'order_out_for_delivery',
      'order_delivered'
    )
  ),
  channel text not null check (channel in ('email', 'whatsapp')),
  recipient text,
  subject text,
  message text not null,
  status text not null default 'queued' check (
    status in ('queued', 'sent', 'skipped', 'failed')
  ),
  provider text,
  provider_response jsonb not null default '{}'::jsonb,
  error text,
  attempts integer not null default 0 check (attempts >= 0),
  sent_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists notification_events_order_id_idx
  on public.notification_events(order_id);

create index if not exists notification_events_profile_id_created_at_idx
  on public.notification_events(profile_id, created_at desc);

create index if not exists notification_events_status_created_at_idx
  on public.notification_events(status, created_at);

alter table public.notification_events enable row level security;

do $$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'notification_events_set_updated_at'
  ) then
    create trigger notification_events_set_updated_at
    before update on public.notification_events
    for each row execute function public.set_updated_at();
  end if;
end $$;
