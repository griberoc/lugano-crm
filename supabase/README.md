# Supabase

Este diretorio guarda o schema inicial do banco da Lugano.

## Como aplicar

No painel do Supabase:

1. Abra o projeto.
2. Va em `SQL Editor`.
3. Crie uma nova query.
4. Execute as migrations em ordem, de `001_initial_schema.sql` ate
   `012_delivery_dispatches.sql`.

O primeiro script cria tabelas, indices, dados iniciais e funcoes.

As migrations seguintes ativam RLS e evoluem o sistema com:

- cada cliente acessar apenas seus proprios dados;
- qualquer usuario ver produtos e tiers de fidelidade;
- usuarios autenticados verem promocoes ativas;
- pedidos e itens ficarem restritos ao dono do pedido.
- papeis administrativos;
- preferencias do cliente;
- notificacoes;
- auditoria;
- configuracoes operacionais;
- pagamentos;
- rastreio de despachos de entrega externa.

## Como conferir

No `SQL Editor`, rode:

```sql
select tablename, rowsecurity
from pg_tables
where schemaname = 'public'
order by tablename;
```

Todas as tabelas do CRM devem aparecer com `rowsecurity = true`.

Para ver as politicas criadas:

```sql
select tablename, policyname, cmd
from pg_policies
where schemaname = 'public'
order by tablename, policyname;
```

## Validacao da P0-002

Como estas migrations historicas foram aplicadas manualmente pelo SQL Editor, a
evidencia confiavel e o schema resultante (nao apenas o nome do arquivo). Confira
os artefatos das migrations `001` a `012`:

```sql
with required_columns(table_name, column_name) as (
  values
    ('profiles', 'preferences'),
    ('orders', 'archived_at'),
    ('orders', 'payment_provider'),
    ('orders', 'payment_reference'),
    ('orders', 'payment_payload'),
    ('orders', 'paid_at'),
    ('delivery_dispatches', 'order_id'),
    ('delivery_dispatches', 'provider'),
    ('delivery_dispatches', 'status')
)
select r.table_name, r.column_name,
       (c.column_name is not null) as present
from required_columns r
left join information_schema.columns c
  on c.table_schema = 'public'
 and c.table_name = r.table_name
 and c.column_name = r.column_name
order by r.table_name, r.column_name;
```

Todas as linhas devem retornar `present = true`. Confirme tambem as tabelas mais
recentes:

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in (
    'admin_users', 'notification_events', 'audit_logs',
    'operational_settings', 'data_retention_policies',
    'delivery_dispatches'
  )
order by table_name;
```

Para verificar os acessos sem alterar dados, use uma transacao no SQL Editor.
Substitua os UUIDs de exemplo por dois perfis de teste distintos; nunca use um
cliente real como fixture:

```sql
begin;

set local role authenticated;
select set_config(
  'request.jwt.claims',
  '{"sub":"UUID_CLIENTE_A","role":"authenticated"}',
  true
);

-- Deve retornar somente pedidos do CLIENTE_A.
select id, profile_id from public.orders order by placed_at desc;

-- Deve retornar zero linhas para um pedido pertencente ao CLIENTE_B.
select id, profile_id
from public.orders
where id = 'UUID_PEDIDO_DO_CLIENTE_B';

rollback;
```

O acesso anonimo a `orders` e `audit_logs` deve falhar por falta de permissao:

```sql
begin;
set local role anon;
select id from public.orders limit 1;
select id from public.audit_logs limit 1;
rollback;
```

Confirme por fim que existe ao menos um owner ativo (a consulta nao exibe email):

```sql
select count(*) as active_owner_count
from public.admin_users
where role = 'owner' and active = true;
```

O resultado deve ser maior que zero. O teste automatizado remoto exige ainda um
cliente de teste e ao menos um pedido pertencente a outro perfil, para comprovar
isolamento horizontal sem criar ou alterar usuarios automaticamente.
