# Supabase

Este diretorio guarda o schema inicial do banco da Lugano.

## Como aplicar

No painel do Supabase:

1. Abra o projeto.
2. Va em `SQL Editor`.
3. Crie uma nova query.
4. Execute primeiro `migrations/001_initial_schema.sql`.
5. Em seguida, execute `migrations/002_rls_policies.sql`.

O primeiro script cria tabelas, indices, dados iniciais e funcoes.

O segundo script ativa RLS e cria politicas para:

- cada cliente acessar apenas seus proprios dados;
- qualquer usuario ver produtos e tiers de fidelidade;
- usuarios autenticados verem promocoes ativas;
- pedidos e itens ficarem restritos ao dono do pedido.

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
