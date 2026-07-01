# Deploy do Lugano CRM

Este guia cobre Supabase em producao, backend em Render/Fly/Railway/VPS e
frontend estatico em Vercel/Netlify/Supabase Storage.

Para a rota completa de entrega ao cliente, incluindo ferramentas, criterios de
aceite e handoff, use `docs/production-delivery-roadmap.md`.

## 1. Staging antes de producao

Antes do deploy final, suba um ambiente separado de staging:

```text
Frontend staging -> API staging -> Supabase staging
```

Use:

- `.env.staging.example` para variaveis da API;
- `render.staging.yaml` para um servico Render separado;
- `frontend/config.staging.example.js` para o site estatico de staging.

O passo a passo completo fica em `docs/staging.md`.

## 2. Supabase em producao

1. Crie um projeto Supabase novo para producao.
2. Abra SQL Editor e rode as migrations em ordem:

```text
supabase/migrations/001_initial_schema.sql
supabase/migrations/002_rls_policies.sql
supabase/migrations/003_profile_auth_metadata.sql
supabase/migrations/004_admin_roles.sql
supabase/migrations/005_customer_preferences.sql
supabase/migrations/006_security_hardening.sql
supabase/migrations/007_notifications.sql
supabase/migrations/008_audit_logs.sql
supabase/migrations/009_operational_settings.sql
supabase/migrations/010_data_retention.sql
supabase/migrations/011_payments.sql
```

3. Em Project Settings > API, copie:
   - Project URL
   - anon public key
   - service_role key
4. Em Authentication > URL Configuration, cadastre as URLs do frontend:
   - `https://seu-site.com/client/`
   - `https://seu-site.com/auth/`
   - `https://seu-site.com/admin/`
5. Crie o usuario owner no Supabase Auth.
6. Promova o usuario para owner no SQL Editor:

```sql
insert into public.admin_users (profile_id, role)
values ('UUID_DO_USUARIO_AUTH', 'owner')
on conflict (profile_id) do update
set role = excluded.role,
    active = true,
    updated_at = now();
```

## 3. Backend

O backend roda FastAPI com:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Variaveis obrigatorias:

```text
APP_ENV=production
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SECRET_KEY=...
ADMIN_API_KEY_ENABLED=false
ALLOWED_ORIGINS=https://seu-frontend.com
PAYMENT_PROVIDER=pix_static
PIX_KEY=sua-chave-pix-da-empresa
```

Use `.env.production.example` como base.

### Render recomendado

Use uma das duas opcoes:

1. Blueprint com `render.yaml`.
2. Web Service manual:
   - Root Directory: pasta do projeto `lugano-crm`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Health Check Path: `/health`

Depois de publicado, teste:

```powershell
Invoke-RestMethod https://sua-api.onrender.com/health
Invoke-RestMethod https://sua-api.onrender.com/health/ready
```

### Railway

O arquivo `railway.json` define start command e healthcheck. No dashboard:

1. Configure as variaveis de ambiente de producao.
2. Aponte o projeto para a pasta `lugano-crm`.
3. Publique e teste `/health`.

### Fly.io

1. Edite `fly.toml` e troque `app = "lugano-crm-api"` por um nome unico.
2. Configure secrets:

```powershell
fly secrets set SUPABASE_URL="https://..." SUPABASE_ANON_KEY="..." SUPABASE_SERVICE_ROLE_KEY="..." SECRET_KEY="..." ALLOWED_ORIGINS="https://seu-site.com"
```

3. Publique:

```powershell
fly deploy
```

### VPS com Docker

1. Copie `.env.production.example` para `.env.production` e preencha.
2. Rode:

```powershell
docker compose -f docker-compose.prod.yml up -d --build
```

3. Coloque um proxy HTTPS na frente, por exemplo Nginx ou Caddy.

## 4. Frontend estatico

A pasta de publicacao e:

```text
frontend/
```

Antes de publicar, edite `frontend/config.js`:

```js
window.LUGANO_CONFIG = {
  apiBaseUrl: "https://sua-api.com",
  adminApiBaseUrl: "",
  supabaseUrl: "https://seu-projeto.supabase.co",
  supabaseAnonKey: "sua-chave-anon-publica",
};
```

Use `frontend/config.production.example.js` como modelo para producao.

Nao coloque `SUPABASE_SERVICE_ROLE_KEY` no frontend.

Rotas principais:

```text
/landing/
/client/
/admin/
```

### Vercel

1. Defina a pasta `frontend` como Root Directory do projeto.
2. Nao use build command.
3. O `frontend/vercel.json` ja configura rewrites para `/`, `/client` e `/admin`.

### Netlify

1. Defina `frontend` como Publish directory.
2. Nao use build command.
3. `_redirects` e `_headers` ja estao na pasta publicada.

### Supabase Storage

1. Crie um bucket publico para arquivos estaticos.
2. Envie todo o conteudo de `frontend/`.
3. Use a URL publica de `frontend/landing/index.html` ou coloque um dominio/proxy na frente.

Para uma experiencia melhor, Vercel ou Netlify sao mais simples porque tratam
`index.html`, headers e redirects de forma mais natural.

## 5. Checklist final

- `APP_ENV=production`.
- `ADMIN_API_KEY_ENABLED=false`, usando login admin pelo Supabase Auth.
- `ALLOWED_ORIGINS` contem apenas dominios reais do frontend.
- `MONITORING_WEBHOOK_URL` configurado ou monitor externo definido.
- Frontend aponta para a API publica em `frontend/config.js`.
- Supabase Auth tem URLs de redirect corretas.
- Todas as migrations 001-011 foram aplicadas.
- Migration 010 de retencao aplicada e documentada em `docs/backup-retention.md`.
- Migration 011 de pagamentos aplicada e documentada em `docs/payments.md`.
- Seed inicial executado com `docs/seed-initial-data.md`.
- Backup off-site recente executado antes de migrations destrutivas.
- Revisao final de seguranca passou com `docs/final-security-review.md`.
- `/health` da API responde `status=ok`.
- `/health/ready` responde `status=ready`.
- Checklist automatico de pre-deploy passou.
- Login admin owner funciona em `/admin/`.
- Pedido real aparece no admin e registra auditoria.

## Referencias oficiais

- Render FastAPI: https://render.com/docs/deploy-fastapi
- Fly.io Python/FastAPI: https://fly.io/docs/python/
- Vercel rewrites: https://vercel.com/docs/routing/rewrites
- Netlify redirects: https://docs.netlify.com/manage/routing/redirects/overview/
- Supabase Storage assets: https://supabase.com/docs/guides/storage/serving/downloads
