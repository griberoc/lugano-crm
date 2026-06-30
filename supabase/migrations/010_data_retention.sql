alter table public.orders
  add column if not exists archived_at timestamptz;

create index if not exists orders_archived_at_idx
  on public.orders(archived_at);

create table if not exists public.data_retention_policies (
  key text primary key,
  table_name text not null,
  date_column text not null,
  retention_days integer check (retention_days is null or retention_days > 0),
  action text not null check (action in ('delete', 'archive', 'retain')),
  enabled boolean not null default true,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.data_retention_policies enable row level security;

do $$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'data_retention_policies_set_updated_at'
  ) then
    create trigger data_retention_policies_set_updated_at
    before update on public.data_retention_policies
    for each row execute function public.set_updated_at();
  end if;
end $$;

insert into public.data_retention_policies (
  key,
  table_name,
  date_column,
  retention_days,
  action,
  enabled,
  description
)
values
  (
    'audit_logs',
    'audit_logs',
    'created_at',
    730,
    'delete',
    true,
    'Remove registros de auditoria com mais de 24 meses apos backup.'
  ),
  (
    'notification_events',
    'notification_events',
    'created_at',
    180,
    'delete',
    true,
    'Remove eventos transacionais antigos de email/WhatsApp apos backup.'
  ),
  (
    'orders',
    'orders',
    'placed_at',
    1825,
    'archive',
    true,
    'Marca pedidos com mais de 5 anos como arquivados; nao apaga dados fiscais.'
  )
on conflict (key) do update
set table_name = excluded.table_name,
    date_column = excluded.date_column,
    retention_days = excluded.retention_days,
    action = excluded.action,
    enabled = excluded.enabled,
    description = excluded.description,
    updated_at = now();

create or replace function public.data_retention_preview()
returns table (
  policy_key text,
  table_name text,
  action text,
  retention_days integer,
  candidate_count bigint
)
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  select
    p.key,
    p.table_name,
    p.action,
    p.retention_days,
    case p.key
      when 'audit_logs' then (
        select count(*)
        from public.audit_logs
        where created_at < now() - make_interval(days => p.retention_days)
      )
      when 'notification_events' then (
        select count(*)
        from public.notification_events
        where created_at < now() - make_interval(days => p.retention_days)
      )
      when 'orders' then (
        select count(*)
        from public.orders
        where placed_at < now() - make_interval(days => p.retention_days)
          and archived_at is null
      )
      else 0
    end as candidate_count
  from public.data_retention_policies p
  where p.enabled = true
  order by p.key;
end;
$$;

create or replace function public.apply_data_retention(
  p_policy_key text default null,
  p_dry_run boolean default true
)
returns table (
  policy_key text,
  table_name text,
  action text,
  affected_count bigint
)
language plpgsql
security definer
set search_path = public
as $$
declare
  policy record;
begin
  for policy in
    select *
    from public.data_retention_policies
    where enabled = true
      and (p_policy_key is null or key = p_policy_key)
    order by key
  loop
    policy_key := policy.key;
    table_name := policy.table_name;
    action := policy.action;

    if p_dry_run then
      select candidate_count into affected_count
      from public.data_retention_preview()
      where data_retention_preview.policy_key = policy.key;
      return next;
    elsif policy.key = 'audit_logs' and policy.action = 'delete' then
      with deleted as (
        delete from public.audit_logs
        where created_at < now() - make_interval(days => policy.retention_days)
        returning 1
      )
      select count(*) into affected_count from deleted;
      return next;
    elsif policy.key = 'notification_events' and policy.action = 'delete' then
      with deleted as (
        delete from public.notification_events
        where created_at < now() - make_interval(days => policy.retention_days)
        returning 1
      )
      select count(*) into affected_count from deleted;
      return next;
    elsif policy.key = 'orders' and policy.action = 'archive' then
      with archived as (
        update public.orders
        set archived_at = now()
        where placed_at < now() - make_interval(days => policy.retention_days)
          and archived_at is null
        returning 1
      )
      select count(*) into affected_count from archived;
      return next;
    else
      affected_count := 0;
      return next;
    end if;
  end loop;
end;
$$;

revoke all on function public.data_retention_preview() from public;
revoke all on function public.data_retention_preview() from anon;
revoke all on function public.data_retention_preview() from authenticated;

revoke all on function public.apply_data_retention(text, boolean) from public;
revoke all on function public.apply_data_retention(text, boolean) from anon;
revoke all on function public.apply_data_retention(text, boolean) from authenticated;
