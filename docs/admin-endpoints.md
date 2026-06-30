# Admin endpoints

Os endpoints administrativos usam a `SUPABASE_SERVICE_ROLE_KEY` no servidor.
O acesso recomendado e por login na API local com um usuario do Supabase Auth
ativo em `public.admin_users`.

O header legado `X-Admin-Key` continua disponivel como fallback tecnico de
desenvolvimento.

## Criar um admin

1. Crie o usuario no Supabase Auth.
2. No SQL Editor, encontre o ID do usuario:

```sql
select id, email
from auth.users
order by created_at desc;
```

3. Promova o usuario:

```sql
insert into public.admin_users (profile_id, role)
values ('UUID_DO_USUARIO', 'owner')
on conflict (profile_id) do update
set role = excluded.role,
    active = true,
    updated_at = now();
```

Os papeis disponiveis sao `owner`, `manager` e `staff`.

## Permissoes por papel

| Recurso | owner | manager | staff |
| --- | --- | --- | --- |
| Login e leitura do proprio perfil admin | sim | sim | sim |
| Pedidos: listar, ver detalhes e atualizar status | sim | sim | sim |
| Produtos: listar e ver detalhes | sim | sim | sim |
| Produtos: criar, editar e remover | sim | sim | nao |
| Clientes: listar, ver detalhes e ver pedidos | sim | sim | sim |
| Clientes: editar cadastro | sim | sim | nao |
| Campanhas/promocoes: listar, criar, editar e remover | sim | sim | nao |
| Equipe administrativa: listar, criar, alterar e desativar admins | sim | nao | nao |

## Login pelo portal admin

No portal `http://127.0.0.1:5176/admin/`, informe apenas:

- `API base URL`: `http://127.0.0.1:8000`
- email do usuario admin
- senha do usuario admin

O backend usa as chaves do `.env` para conversar com o Supabase. A chave anon do
Supabase nao precisa ser colada no portal administrativo.

## Fallback por chave tecnica

Defina no `.env` se quiser manter uma chave local:

```env
ADMIN_API_KEY=uma-chave-admin-forte
```

## Como testar no Swagger

Abra:

```text
http://127.0.0.1:8000/docs
```

Nos endpoints com tag `admin`, clique em `Authorize` e cole o access token do
Supabase no campo do bearer.

Em chamadas manuais, envie:

```text
Authorization: Bearer ACCESS_TOKEN_DO_ADMIN
```

Ou informe o header tecnico:

```text
X-Admin-Key: uma-chave-admin-forte
```

## Endpoints criados

Produtos:

- `GET /api/v1/admin/me`
- `POST /api/v1/admin/products`
- `GET /api/v1/admin/products`
- `GET /api/v1/admin/products/{product_id}`
- `PATCH /api/v1/admin/products/{product_id}`
- `DELETE /api/v1/admin/products/{product_id}`

Clientes:

- `GET /api/v1/admin/customers`
- `GET /api/v1/admin/customers/{customer_id}`
- `PATCH /api/v1/admin/customers/{customer_id}`
- `GET /api/v1/admin/customers/{customer_id}/orders`

Campanhas/promocoes:

- `POST /api/v1/admin/promotions`
- `GET /api/v1/admin/promotions`
- `GET /api/v1/admin/promotions/{promotion_id}`
- `PATCH /api/v1/admin/promotions/{promotion_id}`
- `DELETE /api/v1/admin/promotions/{promotion_id}`

Gestao de pedidos:

- `GET /api/v1/admin/orders`
- `GET /api/v1/admin/orders/{order_id}`
- `PATCH /api/v1/admin/orders/{order_id}`

Equipe administrativa:

- `GET /api/v1/admin/users`
- `POST /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{profile_id}`
