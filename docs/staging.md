# Ambiente de staging

Staging e o ensaio geral de producao. Ele deve usar dominio, API e Supabase
separados para validar releases sem tocar em dados reais.

## Arquitetura recomendada

```text
Frontend staging  ->  API staging  ->  Supabase staging
Frontend producao ->  API producao ->  Supabase producao
```

Nunca aponte frontend staging para Supabase producao, nem API staging para
Supabase producao.

## 1. Supabase staging

1. Crie um novo projeto Supabase chamado `lugano-staging`.
2. Rode todas as migrations em ordem:

```text
001_initial_schema.sql
002_rls_policies.sql
003_profile_auth_metadata.sql
004_admin_roles.sql
005_customer_preferences.sql
006_security_hardening.sql
007_notifications.sql
008_audit_logs.sql
009_operational_settings.sql
010_data_retention.sql
011_payments.sql
```

3. Copie `Project URL`, `anon key` e `service_role key`.
4. Em Authentication > URL Configuration, adicione as URLs do frontend staging:

```text
https://lugano-staging.vercel.app/client/
https://lugano-staging.vercel.app/auth/
https://lugano-staging.vercel.app/admin/
```

5. Crie um usuario owner de staging pelo Supabase Auth.
6. Promova esse usuario no SQL Editor:

```sql
insert into public.admin_users (profile_id, role)
values ('UUID_DO_USUARIO_AUTH_STAGING', 'owner')
on conflict (profile_id) do update
set role = excluded.role,
    active = true,
    updated_at = now();
```

## 2. Backend staging

Use `.env.staging.example` como base.

Variaveis obrigatorias:

```text
APP_ENV=staging
SUPABASE_URL=https://your-staging-project.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SECRET_KEY=...
ADMIN_API_KEY_ENABLED=false
ALLOWED_ORIGINS=https://lugano-staging.vercel.app
```

No Render, use `render.staging.yaml` como blueprint de referencia:

```text
name: lugano-crm-api-staging
healthCheckPath: /health
startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Depois do deploy, valide:

```powershell
Invoke-RestMethod https://lugano-crm-api-staging.onrender.com/health
```

Resposta esperada:

```json
{"status":"ok","env":"staging"}
```

Em `staging`, `/docs` e `/redoc` ficam desativados como em producao.

## 3. Frontend staging

1. Publique a pasta `frontend/` em um site separado, por exemplo
   `lugano-staging`.
2. Antes do deploy, copie o exemplo:

```powershell
Copy-Item frontend\config.staging.example.js frontend\config.js
```

3. Edite `frontend/config.js` com:

```js
window.LUGANO_CONFIG = {
  apiBaseUrl: "https://lugano-crm-api-staging.onrender.com",
  adminApiBaseUrl: "",
  supabaseUrl: "https://your-staging-project.supabase.co",
  supabaseAnonKey: "your-staging-anon-key",
};
```

4. Configure o dominio do frontend staging em `ALLOWED_ORIGINS` da API staging.

## 4. Checklist de isolamento

- Supabase staging tem URL diferente do Supabase producao.
- `SUPABASE_SERVICE_ROLE_KEY` de staging nao e igual ao de producao.
- `ALLOWED_ORIGINS` da API staging contem apenas frontend staging.
- Frontend staging usa `frontend/config.js` apontando para API staging.
- Admin owner de staging nao precisa ser o mesmo usuario da producao.
- Notificacoes externas podem ficar desligadas em staging:
  `NOTIFICATION_EMAIL_ENABLED=false` e `NOTIFICATION_WHATSAPP_ENABLED=false`.

## 5. Fluxo de release

1. Aplique migrations novas no Supabase staging.
2. Rode o seed inicial com `docs/seed-initial-data.md`.
3. Publique backend staging.
4. Publique frontend staging.
5. Rode os smoke tests e teste os fluxos principais.
   Use `docs/pre-deploy-checklist.md` para o checklist automatico.
6. Se tudo passar, aplique as mesmas migrations em producao.
7. Rode o seed inicial em producao.
8. Publique backend producao.
9. Publique frontend producao.

## 6. Dados de teste

Use produtos e clientes claramente marcados como teste. Exemplo:

```text
[STG] Cappuccino Lugano
[STG] Cliente Teste
[STG] Cupom STG10
```

Isso evita confusao em prints, relatorios e auditoria.
