# Rota de entrega em producao

Este runbook leva o Lugano CRM do estado atual ate uma entrega assistida ao
cliente em producao real.

## Estado atual

- Codigo publicado no GitHub privado `griberoc/lugano-crm`.
- Branch principal: `main`.
- Backend FastAPI pronto para deploy.
- Frontend estatico pronto para Cloudflare Pages, Netlify ou Vercel.
- Supabase migrations `001` ate `011` versionadas.
- Scripts de validacao prontos:
  - `scripts/final_security_review.py`
  - `scripts/pre_deploy_check.py`
  - `scripts/seed_initial_data.py`
  - `scripts/monitor_api.py`

## Arquitetura de entrega

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

## 1. Preparar contas e dados finais

Ferramentas:

- GitHub
- Render
- Supabase
- Cloudflare
- Registro de dominio

Checklist:

- Definir dominio final.
- Criar ou confirmar conta Render.
- Criar ou confirmar conta Cloudflare.
- Confirmar acesso ao GitHub `griberoc/lugano-crm`.
- Definir email do owner admin.
- Definir chave Pix, nome comercial e cidade do recebedor.
- Decidir se notificacoes email/WhatsApp entram na primeira entrega.

Saida esperada:

- Dominio comprado ou escolhido.
- Owner admin definido.
- Dados Pix definidos.
- Ambientes externos prontos para configuracao.

## 2. Criar Supabase de producao

Ferramentas:

- Supabase Dashboard
- Supabase SQL Editor
- `supabase/migrations/*.sql`

Passos:

1. Criar um projeto Supabase exclusivo para producao.
2. Rodar migrations `001` ate `011`, em ordem.
3. Criar usuario owner em Authentication > Users.
4. Promover o owner em `public.admin_users`.
5. Configurar Auth URL Configuration com:

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

Saida esperada:

- Coluna `profiles.preferences` existe.
- RLS ligado nas tabelas sensiveis.
- Owner ativo com `role = owner`.

## 3. Configurar ambiente de producao

Ferramentas:

- VS Code
- PowerShell
- Render Environment Variables
- Supabase Project Settings > API

Passos:

1. Criar `.env.production` local a partir de `.env.production.example`.
2. Preencher as chaves reais localmente apenas para validacao.
3. Preencher as mesmas variaveis no Render.
4. Manter `.env.production` fora do Git.

Variaveis obrigatorias:

```env
APP_ENV=production
SECRET_KEY=<token-forte>
ADMIN_API_KEY_ENABLED=false
ALLOWED_ORIGINS=https://app.seu-dominio.com
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
PAYMENT_PROVIDER=pix_static
PIX_KEY=<chave-pix>
PIX_MERCHANT_NAME=Lugano
PIX_MERCHANT_CITY=<cidade>
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_EXEMPT_PATHS=/health,/health/ready
RATE_LIMIT_TRUST_PROXY_HEADERS=false
```

Para primeira entrega sem webhooks:

```env
NOTIFICATIONS_ENABLED=false
NOTIFICATION_EMAIL_ENABLED=false
NOTIFICATION_WHATSAPP_ENABLED=false
MONITORING_ALERTS_ENABLED=false
HEALTHCHECK_SUPABASE_ENABLED=true
```

Saida esperada:

- Render com env vars reais.
- Nenhum segredo no GitHub.
- `ADMIN_API_KEY_ENABLED=false` em producao.

## 4. Publicar backend no Render

Ferramentas:

- Render
- GitHub
- Render Logs
- Endpoints `/health` e `/health/ready`

Passos:

1. Criar Web Service a partir de `griberoc/lugano-crm`.
2. Usar `render.yaml` como base.
3. Confirmar plano pago `starter` ou equivalente.
4. Confirmar comandos:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

5. Configurar dominio `api.seu-dominio.com`.

Validacao:

```powershell
Invoke-RestMethod https://api.seu-dominio.com/health
Invoke-RestMethod https://api.seu-dominio.com/health/ready
```

Saida esperada:

- API online com HTTPS.
- `/health` retorna `ok`.
- `/health/ready` retorna `ready`.
- Logs sem erro de configuracao.

## 5. Publicar frontend no Cloudflare Pages

Ferramentas:

- Cloudflare Pages
- GitHub
- `frontend/config.js`
- `frontend/config.production.example.js`

Passos:

1. Copiar `frontend/config.production.example.js` para `frontend/config.js`.
2. Preencher API publica, Supabase URL e anon key.
3. Fazer commit e push.
4. Criar projeto Cloudflare Pages conectado ao GitHub.
5. Definir pasta publicada como `frontend`.
6. Nao configurar build command.
7. Conectar dominio `app.seu-dominio.com`.

Validacao:

```text
https://app.seu-dominio.com/landing/
https://app.seu-dominio.com/client/
https://app.seu-dominio.com/admin/
https://app.seu-dominio.com/orders/
```

Saida esperada:

- Frontend chama `https://api.seu-dominio.com`.
- `SUPABASE_SERVICE_ROLE_KEY` nao aparece no frontend.
- Login cliente e admin abrem sem erro de CORS.

## 6. Ajustar Auth, CORS e DNS

Ferramentas:

- Supabase Auth URL Configuration
- Render Environment Variables
- Cloudflare DNS

Passos:

- Supabase: cadastrar URLs de redirect do frontend.
- Render: garantir `ALLOWED_ORIGINS=https://app.seu-dominio.com`.
- Cloudflare DNS:
  - `app` aponta para Cloudflare Pages.
  - `api` aponta para Render.

Saida esperada:

- HTTPS ativo em frontend e API.
- Login cliente funciona.
- Login admin funciona.
- Navegador sem erro de CORS.

## 7. Popular dados iniciais

Ferramentas:

- PowerShell
- `scripts/seed_initial_data.py`
- Supabase Table Editor

Passos:

1. Revisar `supabase/seeds/initial_data.json`.
2. Rodar dry-run:

```powershell
.\.venv\Scripts\python.exe scripts\seed_initial_data.py --env-file .env.production --dry-run
```

3. Rodar seed real:

```powershell
.\.venv\Scripts\python.exe scripts\seed_initial_data.py --env-file .env.production
```

Saida esperada:

- Produtos aparecem no delivery.
- Campanhas aparecem no painel.
- Niveis de fidelidade existem.
- Configuracoes operacionais existem.

## 8. Validar seguranca e fluxo completo

Ferramentas:

- PowerShell
- Navegador
- Supabase Dashboard
- Render Logs

Scripts:

```powershell
.\.venv\Scripts\python.exe scripts\final_security_review.py --env-file .env.production --require-remote true
.\.venv\Scripts\python.exe scripts\pre_deploy_check.py --env-file .env.production
```

Teste manual:

- Criar conta cliente.
- Fazer login cliente.
- Editar perfil e endereco.
- Fazer pedido delivery.
- Aplicar cupom.
- Gerar Pix.
- Fazer login admin.
- Ver pedido no admin.
- Alterar status.
- Confirmar auditoria gerada.
- Confirmar que anon nao le `orders` nem `audit_logs`.

Saida esperada:

- Todos os checks automaticos passam.
- Pedido completo funciona de ponta a ponta.
- Admin consegue gerir pedidos.
- Cliente acompanha pedidos e fidelidade.

## 9. Entrega assistida ao cliente

Ferramentas:

- Navegador
- Documento `docs/client-handoff.md`
- Render
- Supabase
- Cloudflare

Passos:

1. Criar conta admin do cliente.
2. Entregar URLs finais.
3. Entregar credenciais por canal seguro.
4. Demonstrar fluxo cliente e admin.
5. Explicar limites da primeira entrega:
   - Pix estatico/manual.
   - Notificacoes dependem de webhooks.
   - Backups e custos dependem dos planos contratados.

Saida esperada:

- Cliente acessa admin.
- Cliente entende operacao basica.
- Sistema operando em dominio final.
- Monitoramento/backups definidos.

## Criterio final de aceite

- `pytest` local passa.
- `/health` e `/health/ready` passam em producao.
- `final_security_review.py` passa.
- `pre_deploy_check.py` passa.
- Nenhuma chave real no GitHub.
- Service role somente no backend/Render.
- Frontend usa apenas anon key.
- Pedido real gera itens, pagamento Pix e auditoria.
- Admin owner altera status do pedido.
- Cliente comum nao acessa dados administrativos.

