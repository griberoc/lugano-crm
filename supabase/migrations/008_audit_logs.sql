create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  actor_profile_id uuid references public.profiles(id) on delete set null,
  actor_email text,
  actor_role text,
  auth_method text,
  action text not null,
  entity_type text not null,
  entity_id text,
  before_data jsonb,
  after_data jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists audit_logs_created_at_idx
  on public.audit_logs(created_at desc);

create index if not exists audit_logs_actor_profile_id_idx
  on public.audit_logs(actor_profile_id);

create index if not exists audit_logs_entity_idx
  on public.audit_logs(entity_type, entity_id);

alter table public.audit_logs enable row level security;
