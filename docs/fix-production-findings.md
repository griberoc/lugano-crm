# Guia para corrigir os findings de producao

Use este guia como roteiro de fechamento antes do deploy. A ordem importa:
primeiro alinhe o Supabase, depois crie o ambiente de producao, depois valide
frontend, owner admin e scripts automaticos.

## 1. Aplicar migrations que faltam no Supabase

No Supabase Dashboard, abra **SQL Editor** e rode uma migration por vez, nesta
ordem:

```text
supabase/migrations/002_rls_policies.sql
supabase/migrations/005_customer_preferences.sql
supabase/migrations/006_security_hardening.sql
supabase/migrations/007_notifications.sql
supabase/migrations/008_audit_logs.sql
supabase/migrations/009_operational_settings.sql
supabase/migrations/010_data_retention.sql
supabase/migrations/011_payments.sql
```

Se alguma delas ja tiver sido aplicada, ela deve passar sem criar dados
duplicados porque os arquivos usam `if not exists`, `drop policy if exists` ou
`on conflict` onde faz sentido.

Se o Supabase exibir alerta de operacao destrutiva, confira se o SQL e um
destes arquivos do projeto e rode somente se estiver no projeto correto.

### Validacao manual das migrations

Depois de rodar, execute no SQL Editor:

```sql
select column_name
from information_schema.columns
where table_schema = 'public'
  and table_name = 'profiles'
  and column_name = 'preferences';
```

Resultado esperado: uma linha com `preferences`.

Confirme RLS ativo:

```sql
select tablename, rowsecurity
from pg_tables
where schemaname = 'public'
  and tablename in ('orders', 'audit_logs', 'profiles', 'products');
```

Resultado esperado: `rowsecurity = true` para essas tabelas.

Confirme policies:

```sql
select tablename, policyname, roles, cmd
from pg_policies
where schemaname = 'public'
  and tablename in ('orders', 'audit_logs', 'profiles', 'products')
order by tablename, policyname;
```

## 2. Criar o `.env.production`

No terminal, dentro da pasta do projeto:

```powershell
Copy-Item .env.production.example .env.production
```

Preencha `.env.production` com valores reais. Nunca coloque esse arquivo no Git.
O `.gitignore` ja protege `.env.production`.

Valores obrigatorios para producao:

```env
APP_ENV=production
SECRET_KEY=<gere-um-token-forte>
ADMIN_API_KEY_ENABLED=false
ADMIN_API_KEY=
ALLOWED_ORIGINS=https://seu-frontend.com
ALLOWED_METHODS=GET,POST,PUT,PATCH,DELETE,OPTIONS
ALLOWED_HEADERS=Authorization,Content-Type,X-Admin-Key
LOG_LEVEL=INFO

SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>

API_BASE_URL=https://sua-api.com
FINAL_SECURITY_REQUIRE_REMOTE=true
```

Para gerar `SECRET_KEY`:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 3. Configurar rate limit

Use valores conservadores no `.env.production`:

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_EXEMPT_PATHS=/health,/health/ready
RATE_LIMIT_TRUST_PROXY_HEADERS=false
```

Se o backend ficar atras de proxy confiavel e voce precisar identificar IP real,
ative `RATE_LIMIT_TRUST_PROXY_HEADERS=true` somente depois de configurar o proxy
corretamente.

## 4. Configurar pagamento

Para entrega desta semana, o caminho mais simples e Pix estatico:

```env
PAYMENT_PROVIDER=pix_static
PIX_KEY=<chave-pix-da-empresa>
PIX_MERCHANT_NAME=LUGANO
PIX_MERCHANT_CITY=<SUA_CIDADE>
PIX_TXID_PREFIX=LUGANO
PIX_EXPIRES_MINUTES=30
```

Deixe Mercado Pago vazio se nao for usar agora:

```env
MERCADO_PAGO_ACCESS_TOKEN=
MERCADO_PAGO_WEBHOOK_SECRET=
MERCADO_PAGO_NOTIFICATION_URL=
MERCADO_PAGO_TIMEOUT_SECONDS=10
```

## 5. Configurar notificacoes e monitoramento

Escolha explicitamente entre ativar ou deixar desligado.

Se ainda nao houver webhook de email/WhatsApp:

```env
NOTIFICATIONS_ENABLED=false
NOTIFICATION_EMAIL_ENABLED=false
NOTIFICATION_WHATSAPP_ENABLED=false
```

Se for ativar:

```env
NOTIFICATIONS_ENABLED=true
NOTIFICATION_EMAIL_ENABLED=true
NOTIFICATION_WHATSAPP_ENABLED=true
NOTIFICATION_EMAIL_WEBHOOK_URL=https://...
NOTIFICATION_EMAIL_WEBHOOK_TOKEN=<token>
NOTIFICATION_WHATSAPP_WEBHOOK_URL=https://...
NOTIFICATION_WHATSAPP_WEBHOOK_TOKEN=<token>
NOTIFICATION_WEBHOOK_TIMEOUT_SECONDS=5
```

Para monitoramento:

```env
MONITORING_ALERTS_ENABLED=true
MONITORING_WEBHOOK_URL=https://...
MONITORING_WEBHOOK_TOKEN=<token>
MONITORING_WEBHOOK_TIMEOUT_SECONDS=5
MONITORING_SERVICE_NAME=lugano-crm
MONITORING_HEALTH_PATH=/health/ready
MONITORING_ENVIRONMENT=production
HEALTHCHECK_SUPABASE_ENABLED=true
```

Se nao houver webhook ainda, deixe `MONITORING_ALERTS_ENABLED=false` ate
configurar um canal real.

## 6. Ajustar `frontend/config.js` para producao

Edite `frontend/config.js` antes de publicar o frontend:

```js
window.LUGANO_CONFIG = {
  apiBaseUrl: "https://sua-api.com",
  adminApiBaseUrl: "https://sua-api.com",
  supabaseUrl: "https://seu-projeto.supabase.co",
  supabaseAnonKey: "sua-anon-key-publica",
};
```

Nunca coloque `SUPABASE_SERVICE_ROLE_KEY` no frontend.

## 7. Criar e validar owner admin

No Supabase, crie o usuario em **Authentication > Users**. Use email e senha de
owner, confirme o email se necessario.

No SQL Editor, encontre o `id`:

```sql
select id, email
from auth.users
where email = 'owner@lugano.com';
```

Depois promova o usuario:

```sql
insert into public.profiles (id, email, full_name)
values ('UUID_DO_AUTH_USER', 'owner@lugano.com', 'Owner Lugano')
on conflict (id) do update
set email = excluded.email,
    full_name = excluded.full_name,
    updated_at = now();

insert into public.admin_users (profile_id, role, active)
values ('UUID_DO_AUTH_USER', 'owner', true)
on conflict (profile_id) do update
set role = 'owner',
    active = true,
    updated_at = now();
```

No `.env.production`, preencha:

```env
PREDEPLOY_ADMIN_EMAIL=owner@lugano.com
PREDEPLOY_ADMIN_PASSWORD=<senha-do-owner>
FINAL_SECURITY_OWNER_EMAIL=owner@lugano.com
FINAL_SECURITY_OWNER_PASSWORD=<senha-do-owner>
SEED_OWNER_EMAIL=owner@lugano.com
SEED_OWNER_FULL_NAME=Owner Lugano
SEED_OWNER_PASSWORD=<senha-do-owner>
```

Se nao quiser deixar a senha no arquivo, passe a senha pela linha de comando no
script de seguranca.

Validacao manual:

```sql
select p.email, a.role, a.active
from public.admin_users a
join public.profiles p on p.id = a.profile_id
where p.email = 'owner@lugano.com';
```

Resultado esperado: `role = owner` e `active = true`.

## 8. Rodar seed inicial

Se ainda nao houver produtos/campanhas/niveis de fidelidade em producao:

```powershell
.\.venv\Scripts\python.exe scripts\seed_initial_data.py --env-file .env.production --dry-run
.\.venv\Scripts\python.exe scripts\seed_initial_data.py --env-file .env.production
```

Edite `supabase/seeds/initial_data.json` antes se quiser ajustar catalogo,
promocoes ou configuracoes operacionais.

## 9. Rodar revisao final de seguranca

```powershell
.\.venv\Scripts\python.exe scripts\final_security_review.py --env-file .env.production --require-remote true
```

Resultado esperado:

```text
[OK] ADMIN_API_KEY_ENABLED
[OK] ALLOWED_ORIGINS
[OK] Supabase keys
[OK] Frontend secrets
[OK] Migration files 001-008
[OK] Migrations remotas 001-008
[OK] RLS basico
[OK] Owner admin
```

Se `RLS basico` falhar, volte para as migrations 002, 006 e 008.

## 10. Rodar checklist automatico de pre-deploy

Crie tambem um cliente de teste no Supabase Auth e preencha:

```env
PREDEPLOY_EXPECTED_ENV=production
PREDEPLOY_CUSTOMER_EMAIL=cliente-teste@lugano.com
PREDEPLOY_CUSTOMER_PASSWORD=<senha-do-cliente-teste>
```

Depois execute:

```powershell
.\.venv\Scripts\python.exe scripts\pre_deploy_check.py --env-file .env.production
```

Resultado esperado:

```text
[OK] /health
[OK] login admin
[OK] listagem de produtos
[OK] login cliente
[OK] criacao de pedido
[OK] leitura do pedido no admin
[OK] auditoria gerada
[OK] RLS basica
```

## Criterio de pronto para deploy

Considere pronto quando:

- `profiles.preferences` existir no Supabase;
- anon nao conseguir ler `orders` nem `audit_logs`;
- `.env.production` existir e `APP_ENV=production`;
- `ADMIN_API_KEY_ENABLED=false`;
- `ALLOWED_ORIGINS` tiver apenas dominios reais HTTPS;
- frontend usar URL publica da API e anon key do Supabase;
- service role aparecer somente no backend;
- owner admin estiver ativo;
- seed inicial tiver sido executado;
- `final_security_review.py` passar;
- `pre_deploy_check.py` passar.
