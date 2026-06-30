# Revisao final de seguranca

Use este passo antes de subir producao ou antes de apontar usuarios reais para
o sistema.

## O que e conferido

O script `scripts/final_security_review.py` valida:

- `ADMIN_API_KEY_ENABLED=false`;
- `ALLOWED_ORIGINS` somente com dominios reais em HTTPS;
- `SUPABASE_SERVICE_ROLE_KEY` presente apenas no backend/configuracao segura;
- frontend sem `service_role`, usando somente `supabaseAnonKey`;
- arquivos locais das migrations `001` ate `008`;
- tabelas/colunas esperadas das migrations `001` ate `008` no Supabase;
- RLS basico: `anon` le `products`, mas nao le `orders` nem `audit_logs`;
- owner admin ativo em `public.admin_users`;
- login admin retorna papel `owner`, quando `API_BASE_URL` e senha existem.

As migrations `009` e `010` continuam recomendadas porque habilitam
configuracoes operacionais e retencao, mas a revisao final de seguranca cobre o
minimo estrutural `001` ate `008`.

## Variaveis necessarias

No `.env.production`:

```env
APP_ENV=production
ADMIN_API_KEY_ENABLED=false
ALLOWED_ORIGINS=https://seu-dominio-real.com
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=sua-anon-key
SUPABASE_SERVICE_ROLE_KEY=sua-service-role-key
API_BASE_URL=https://sua-api.com
PREDEPLOY_ADMIN_EMAIL=owner@lugano.com
PREDEPLOY_ADMIN_PASSWORD=senha-do-owner
FINAL_SECURITY_REQUIRE_REMOTE=true
```

Se nao quiser deixar a senha no arquivo, passe pela linha de comando:

```powershell
.\.venv\Scripts\python.exe scripts\final_security_review.py --env-file .env.production --admin-password "SENHA_DO_OWNER" --require-remote true
```

## Como rodar

Revisao completa com Supabase/API reais:

```powershell
.\.venv\Scripts\python.exe scripts\final_security_review.py --env-file .env.production --require-remote true
```

Revisao local parcial, sem exigir conexao remota:

```powershell
.\.venv\Scripts\python.exe scripts\final_security_review.py --env-file .env.production
```

Resultado esperado:

```text
[OK] ADMIN_API_KEY_ENABLED: fallback tecnico desligado
[OK] ALLOWED_ORIGINS: 1 dominio(s) real(is) usando HTTPS
[OK] Supabase keys: anon e service role existem e diferem
[OK] Frontend secrets: frontend nao contem service role; use somente anon key publica
[OK] Migration files 001-008: arquivos locais presentes
[OK] Migrations remotas 001-008: tabelas/colunas esperadas respondem no Supabase
[OK] RLS basico: anon le products e nao le orders/audit_logs
[OK] Owner admin: owner ativo encontrado em public.admin_users e login administrativo validado
```

Qualquer `[FAIL]` deve ser resolvido antes do deploy.

## Conferencia manual no Supabase

No SQL Editor, para confirmar o owner:

```sql
select
  p.email,
  a.role,
  a.active
from public.admin_users a
join public.profiles p on p.id = a.profile_id
where a.role = 'owner';
```

Deve existir pelo menos um registro com `active = true`.
