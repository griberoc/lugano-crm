# Roadmap completo do Lugano CRM

Este documento consolida a documentacao antiga do projeto em um unico roteiro
vivo: estado atual, entrega em producao, operacao, criterios de aceite e
proximas evolucoes.

## 1. Onde estamos

O sistema ja possui:

- backend FastAPI com Supabase;
- portais estaticos para landing, cliente, delivery e admin;
- login cliente via Supabase Auth;
- login admin com papeis `owner`, `manager` e `staff`;
- catalogo, carrinho, enderecos, pedidos, cupons e fidelidade;
- gestao admin de produtos, clientes, campanhas, pedidos, equipe e relatorios;
- auditoria administrativa;
- notificacoes transacionais registradas em `notification_events`;
- Pix estatico/manual para primeira operacao real;
- migrations Supabase `001` ate `011`;
- seed inicial idempotente;
- scripts de backup, monitoramento, pre-deploy e revisao final de seguranca;
- deploy preparado para Render, Railway, Fly.io, VPS, Vercel/Netlify/Cloudflare Pages;
- repositorio GitHub privado `griberoc/lugano-crm`, branch `main`.

Arquitetura alvo para producao real:

```text
Cliente -> Cloudflare Pages -> Render API -> Supabase
                         \-> Supabase Auth
```

Padrao recomendado:

- Frontend: Cloudflare Pages.
- Backend: Render `starter` ou plano pago equivalente.
- Banco/Auth: Supabase producao separado.
- DNS: Cloudflare DNS.
- Pagamento inicial: Pix estatico/manual.

URLs finais sugeridas:

```text
https://app.seu-dominio.com
https://api.seu-dominio.com
```

## 2. Ferramentas necessarias

Contas e paineis:

- GitHub: codigo, deploy trigger e historico.
- Supabase: banco, Auth, SQL Editor, RLS e backups.
- Render: API FastAPI em producao.
- Cloudflare Pages: frontend estatico.
- Cloudflare DNS: registros `app` e `api`.
- Registro de dominio: dominio final do cliente.

Ferramentas locais:

- VS Code.
- PowerShell.
- Python/venv do projeto.
- Git.
- Navegador com DevTools.

Scripts do projeto:

```text
scripts/seed_initial_data.py
scripts/final_security_review.py
scripts/pre_deploy_check.py
scripts/monitor_api.py
scripts/backup_supabase.py
scripts/smoke_test_api.py
```

## 3. Roadmap ate a entrega

### Fase 1: decisoes finais

Definir antes de mexer em producao:

- dominio final;
- URL do frontend: `https://app.seu-dominio.com`;
- URL da API: `https://api.seu-dominio.com`;
- email do owner admin;
- chave Pix, nome comercial e cidade do recebedor;
- se email/WhatsApp entram agora ou ficam desligados na primeira entrega;
- plano Supabase e plano Render.

Criterio de pronto:

- dominio e subdominios definidos;
- conta Render disponivel;
- conta Cloudflare disponivel;
- dados Pix definidos;
- owner admin definido.

### Fase 2: Supabase producao

No Supabase Dashboard:

1. Criar projeto exclusivo de producao.
2. Rodar no SQL Editor as migrations em ordem:

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

3. Criar usuario owner em Authentication > Users.
4. Promover o owner:

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

5. Configurar Supabase Auth URL Configuration:

```text
https://app.seu-dominio.com/auth/
https://app.seu-dominio.com/client/
https://app.seu-dominio.com/admin/
```

Validacoes SQL:

```sql
select column_name
from information_schema.columns
where table_schema = 'public'
  and table_name = 'profiles'
  and column_name = 'preferences';
```

```sql
select tablename, rowsecurity
from pg_tables
where schemaname = 'public'
  and tablename in ('orders', 'audit_logs', 'profiles', 'products');
```

```sql
select p.email, a.role, a.active
from public.admin_users a
join public.profiles p on p.id = a.profile_id
where a.role = 'owner';
```

Criterio de pronto:

- tabelas criadas;
- `profiles.preferences` existe;
- RLS ativo;
- anon nao le `orders` nem `audit_logs`;
- owner ativo com `role = owner`.

### Fase 3: variaveis e configuracoes

Criar `.env.production` local apenas para validacao:

```powershell
Copy-Item .env.production.example .env.production
```

Gerar `SECRET_KEY`:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Variaveis obrigatorias:

```env
APP_ENV=production
SECRET_KEY=<token-forte>
ADMIN_API_KEY_ENABLED=false
ADMIN_API_KEY=
ALLOWED_ORIGINS=https://app.seu-dominio.com
ALLOWED_METHODS=GET,POST,PATCH,DELETE,OPTIONS
ALLOWED_HEADERS=Authorization,Content-Type,X-Admin-Key
LOG_LEVEL=INFO

SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>

RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_EXEMPT_PATHS=/health,/health/ready
RATE_LIMIT_TRUST_PROXY_HEADERS=false

DELIVERY_BASE_FEE=500
DELIVERY_FREE_THRESHOLD=5000
POINTS_PER_REAL=10

PAYMENT_PROVIDER=pix_static
PIX_KEY=<chave-pix>
PIX_MERCHANT_NAME=Lugano
PIX_MERCHANT_CITY=<cidade>
PIX_TXID_PREFIX=LUG
PIX_EXPIRES_MINUTES=30

API_BASE_URL=https://api.seu-dominio.com
PREDEPLOY_EXPECTED_ENV=production
PREDEPLOY_ADMIN_EMAIL=<owner>
PREDEPLOY_ADMIN_PASSWORD=<senha-owner>
PREDEPLOY_CUSTOMER_EMAIL=<cliente-teste>
PREDEPLOY_CUSTOMER_PASSWORD=<senha-cliente-teste>
FINAL_SECURITY_OWNER_EMAIL=<owner>
FINAL_SECURITY_OWNER_PASSWORD=<senha-owner>
FINAL_SECURITY_REQUIRE_REMOTE=true
```

Primeira entrega sem webhooks:

```env
NOTIFICATIONS_ENABLED=false
NOTIFICATION_EMAIL_ENABLED=false
NOTIFICATION_WHATSAPP_ENABLED=false
MONITORING_ALERTS_ENABLED=false
HEALTHCHECK_SUPABASE_ENABLED=true
```

Quando ativar notificacoes:

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

Quando ativar monitoramento:

```env
MONITORING_ALERTS_ENABLED=true
MONITORING_WEBHOOK_URL=https://...
MONITORING_WEBHOOK_TOKEN=<token>
MONITORING_WEBHOOK_TIMEOUT_SECONDS=5
MONITORING_SERVICE_NAME=lugano-crm
MONITORING_HEALTH_PATH=/health/ready
MONITORING_ENVIRONMENT=production
```

Criterio de pronto:

- `.env.production` existe localmente e nao entra no Git;
- Render contem as mesmas variaveis reais;
- `SUPABASE_SERVICE_ROLE_KEY` existe somente no backend/Render;
- `ADMIN_API_KEY_ENABLED=false`;
- `ALLOWED_ORIGINS` contem apenas dominio HTTPS real.

### Fase 4: deploy backend

No Render:

1. Criar Web Service conectado ao GitHub.
2. Usar `render.yaml` como blueprint.
3. Confirmar plano pago `starter` ou equivalente.
4. Confirmar:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

5. Configurar dominio `api.seu-dominio.com`.

Validar:

```powershell
Invoke-RestMethod https://api.seu-dominio.com/health
Invoke-RestMethod https://api.seu-dominio.com/health/ready
```

Criterio de pronto:

- API online com HTTPS;
- `/health` retorna ok;
- `/health/ready` retorna ready;
- logs sem erro de variavel/configuracao.

### Fase 5: deploy frontend

Antes de publicar:

```powershell
Copy-Item frontend\config.production.example.js frontend\config.js
```

Editar `frontend/config.js`:

```js
window.LUGANO_CONFIG = {
  apiBaseUrl: "https://api.seu-dominio.com",
  adminApiBaseUrl: "https://api.seu-dominio.com",
  supabaseUrl: "https://seu-projeto.supabase.co",
  supabaseAnonKey: "sua-chave-anon-publica",
};
```

No Cloudflare Pages:

1. Conectar repo GitHub.
2. Definir publish directory como `frontend`.
3. Nao usar build command.
4. Conectar dominio `app.seu-dominio.com`.

Se usar Vercel em vez de Cloudflare Pages:

- o `vercel.json` na raiz ja pula instalacao/build de Python;
- o `outputDirectory` aponta para `frontend`;
- se criar o projeto manualmente pelo dashboard, tambem pode definir Root
  Directory como `frontend` para evitar autodetectar o backend;
- se aparecer erro de `uv lock` ou `pyproject.toml`, o projeto esta tentando
  buildar a API Python em vez do frontend estatico.

Rotas esperadas:

```text
/landing/
/client/
/admin/
/orders/
/auth/
/customer/
```

Criterio de pronto:

- frontend chama API publica;
- service role nao aparece no frontend;
- login cliente abre;
- login admin abre;
- sem erro de CORS.

### Fase 6: DNS, CORS e Auth

No Cloudflare DNS:

- `app` aponta para Cloudflare Pages;
- `api` aponta para Render.

No Render:

```env
ALLOWED_ORIGINS=https://app.seu-dominio.com
```

No Supabase Auth:

- cadastrar URLs de redirect do frontend;
- confirmar email templates e confirmacao de email conforme regra do cliente.

Criterio de pronto:

- HTTPS ativo no frontend e na API;
- CORS liberado apenas para dominio final;
- login cliente e admin funcionam em producao.

### Fase 7: seed e dados iniciais

Revisar:

```text
supabase/seeds/initial_data.json
```

Rodar dry-run:

```powershell
.\.venv\Scripts\python.exe scripts\seed_initial_data.py --env-file .env.production --dry-run
```

Rodar seed real:

```powershell
.\.venv\Scripts\python.exe scripts\seed_initial_data.py --env-file .env.production
```

O seed cria/atualiza:

- niveis de fidelidade;
- produtos;
- campanhas;
- configuracoes operacionais;
- owner no Auth/perfil/admin, se configurado.

Criterio de pronto:

- produtos aparecem no delivery;
- campanhas aparecem no painel;
- niveis de fidelidade existem;
- owner permanece ativo.

### Fase 8: validacao final

Testes locais:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Revisao final de seguranca:

```powershell
.\.venv\Scripts\python.exe scripts\final_security_review.py --env-file .env.production --require-remote true
```

Checklist automatico:

```powershell
.\.venv\Scripts\python.exe scripts\pre_deploy_check.py --env-file .env.production
```

Smoke test manual ou local com token:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test_api.py --token "ACCESS_TOKEN_DO_USUARIO"
```

Teste manual de ponta a ponta:

- criar conta cliente;
- login cliente;
- editar perfil;
- cadastrar endereco;
- criar pedido delivery;
- aplicar cupom;
- gerar Pix;
- login admin;
- ver pedido;
- alterar status;
- confirmar auditoria;
- confirmar fidelidade/historico do cliente.

Criterio de pronto:

- `pytest` passa;
- `final_security_review.py` passa;
- `pre_deploy_check.py` passa;
- pedido real aparece no admin;
- auditoria gerada;
- cliente comum nao acessa dados administrativos.

### Fase 9: entrega assistida

Entregar ao cliente:

```text
Landing / portal: https://app.seu-dominio.com/landing/
Portal do cliente: https://app.seu-dominio.com/client/
Delivery: https://app.seu-dominio.com/orders/
Admin: https://app.seu-dominio.com/admin/
Healthcheck API: https://api.seu-dominio.com/health
```

Credenciais devem ser enviadas por canal seguro:

```text
Admin owner:
Email:
Senha:

Conta cliente teste:
Email:
Senha:
```

Demonstracao guiada:

1. Abrir landing page.
2. Criar/acessar conta cliente.
3. Editar perfil e endereco.
4. Adicionar produto ao carrinho.
5. Aplicar cupom.
6. Confirmar pedido.
7. Gerar Pix.
8. Abrir admin.
9. Localizar pedido.
10. Alterar status.
11. Mostrar historico/fidelidade do cliente.

Explicar limites da primeira entrega:

- Pix estatico/manual, sem conciliacao automatica;
- email/WhatsApp dependem de webhooks externos;
- monitoramento depende de webhook ou ferramenta externa;
- backups dependem do plano Supabase e rotina off-site.

## 4. Operacao apos entrega

### Monitoramento

Healthchecks:

```text
GET /health
GET /health/ready
```

Rotina recomendada:

- Render usa `/health` como healthcheck.
- Monitor externo usa `/health/ready` a cada 1 ou 5 minutos.
- `HEALTHCHECK_SUPABASE_ENABLED=true` em producao.
- Logs devem ser pesquisados pelo header `X-Request-ID`.

Monitor externo:

```powershell
.\.venv\Scripts\python.exe scripts\monitor_api.py --env-file .env.production
```

### Backups e retencao

Recomendacao para producao real:

- Supabase Pro ou superior;
- backup automatico diario;
- backup off-site diario ou semanal conforme volume;
- teste mensal de restore em projeto separado.

Backup off-site:

```powershell
.\.venv\Scripts\python.exe scripts\backup_supabase.py --env-file .env.production
```

Retencao criada pela migration `010_data_retention.sql`:

- `audit_logs`: 730 dias, delete;
- `notification_events`: 180 dias, delete;
- `orders`: 1825 dias, archive.

Antes de aplicar retencao:

```sql
select * from public.data_retention_preview();
select * from public.apply_data_retention(null, true);
```

Aplicar somente depois de backup recente:

```sql
select * from public.apply_data_retention(null, false);
```

### Suporte

Em todo chamado, coletar:

- URL acessada;
- horario aproximado;
- email do usuario afetado;
- print da tela;
- `X-Request-ID`, quando houver erro de API.

## 5. Referencia funcional do sistema

### Portais

```text
/landing/   Experiencia de marca e entrada do sistema
/client/    Portal cliente consolidado
/orders/    Delivery e checkout
/customer/  Painel de fidelidade/historico
/auth/      Login/criacao de conta
/admin/     Operacao administrativa
```

### Permissoes admin

| Recurso | owner | manager | staff |
| --- | --- | --- | --- |
| Login e proprio perfil | sim | sim | sim |
| Pedidos: listar, ver e atualizar | sim | sim | sim |
| Produtos: listar e ver | sim | sim | sim |
| Produtos: criar, editar e remover | sim | sim | nao |
| Clientes: listar, ver e ver pedidos | sim | sim | sim |
| Clientes: editar cadastro | sim | sim | nao |
| Campanhas: listar, criar, editar e remover | sim | sim | nao |
| Equipe administrativa | sim | nao | nao |
| Relatorios financeiros | sim | sim | nao |

### Endpoints principais

Cliente:

```text
GET /health
GET /health/ready
GET /api/v1/catalog/products
POST /api/v1/orders/quote
POST /api/v1/orders/
GET /api/v1/orders/
GET /api/v1/orders/{order_id}
POST /api/v1/orders/{order_id}/cancel
GET /api/v1/loyalty/
GET /api/v1/loyalty/transactions
POST /api/v1/promotions/validate
GET /api/v1/promotions/available
GET/PATCH /api/v1/profile/
GET/POST/PATCH/DELETE /api/v1/profile/addresses
```

Admin:

```text
POST /api/v1/admin/login
GET /api/v1/admin/me
GET/POST/PATCH/DELETE /api/v1/admin/products
GET/PATCH /api/v1/admin/customers
GET/POST/PATCH/DELETE /api/v1/admin/promotions
GET/PATCH /api/v1/admin/orders
GET /api/v1/admin/reports
GET /api/v1/admin/audit-logs
GET/POST/PATCH /api/v1/admin/users
```

### Pagamentos

Primeira entrega:

```env
PAYMENT_PROVIDER=pix_static
```

O checkout gera Pix copia e cola, mas a confirmacao continua manual pelo admin.

Fase futura:

- Mercado Pago;
- webhook de pagamento;
- atualizacao automatica de `payment_status`;
- conciliacao por `payment_reference`.

### Notificacoes

Eventos cobertos:

```text
order_created
order_confirmed
order_out_for_delivery
order_delivered
```

Estados:

```text
queued
sent
failed
skipped
```

WhatsApp respeita `profiles.preferences.accepts_whatsapp`.

## 6. O que falta para o sistema completo

Obrigatorio antes de entregar:

- Supabase producao criado e migrado;
- dominio final comprado/configurado;
- Render pago ativo;
- Cloudflare Pages ativo;
- `.env.production` preenchido fora do Git;
- `frontend/config.js` apontando para producao;
- owner admin real criado;
- seed inicial revisado e executado;
- validacoes automatizadas passando;
- teste manual aprovado com o cliente.

Melhorias recomendadas pos-entrega:

- Mercado Pago com webhook e conciliacao automatica;
- provedor real de email/WhatsApp;
- dashboard de monitoramento externo;
- rotina automatizada de backup off-site;
- restore testado mensalmente;
- politicas comerciais de cupons e niveis de fidelidade refinadas;
- relatorios exportaveis em CSV/PDF;
- controle de estoque;
- multiunidade, se a operacao crescer;
- painel de configuracoes operacionais sem SQL;
- testes E2E de frontend.

## 7. Criterio final de aceite

O sistema so deve ser considerado entregue quando:

- `pytest` passa;
- API producao responde `/health`;
- API producao responde `/health/ready`;
- `final_security_review.py` passa;
- `pre_deploy_check.py` passa;
- nenhuma chave real aparece no GitHub;
- service role fica somente no backend/Render;
- frontend usa apenas anon key;
- RLS bloqueia anon em `orders` e `audit_logs`;
- cliente cria pedido real;
- admin ve pedido e altera status;
- auditoria registra acao administrativa;
- cliente acompanha historico e fidelidade;
- cliente final recebeu URLs e credenciais por canal seguro.
