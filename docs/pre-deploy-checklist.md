# Checklist automatico de pre-deploy

O script `scripts/pre_deploy_check.py` valida os fluxos minimos antes de
publicar uma versao em producao.

Para a revisao focada em seguranca final, use tambem
`scripts/final_security_review.py`, documentado em
`docs/final-security-review.md`.

Ele testa:

- `/health`;
- login administrativo;
- listagem de produtos no admin;
- login do cliente teste;
- criacao de pedido;
- leitura do pedido no admin;
- auditoria gerada por alteracao administrativa;
- RLS basica no Supabase REST.

## Pre-requisitos

No ambiente testado, ja devem existir:

- migrations 001-008 aplicadas;
- se usar configuracoes operacionais no banco, migration 009 aplicada;
- se usar retencao/backups operacionais, migration 010 aplicada;
- se usar Pix copia e cola, migration 011 aplicada;
- um usuario admin `owner` cadastrado em `public.admin_users`;
- um usuario cliente de teste no Supabase Auth;
- pelo menos um produto disponivel;
- API publicada e respondendo;
- `ALLOWED_ORIGINS` apontando para o frontend correto.

O script cria ou atualiza automaticamente o perfil, endereco e conta de
fidelidade do cliente de teste, mas nao cria produto.

## Variaveis

Use `.env.staging.example` ou `.env.production.example` como base.

Variaveis principais:

```text
API_BASE_URL=https://lugano-crm-api-staging.onrender.com
SUPABASE_URL=https://your-staging-project.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
PREDEPLOY_EXPECTED_ENV=staging
PREDEPLOY_ADMIN_EMAIL=owner-staging@lugano.test
PREDEPLOY_ADMIN_PASSWORD=...
PREDEPLOY_CUSTOMER_EMAIL=cliente-staging@lugano.test
PREDEPLOY_CUSTOMER_PASSWORD=...
```

Tambem e possivel usar `PREDEPLOY_CUSTOMER_ACCESS_TOKEN` no lugar de email e
senha do cliente.

## Como rodar em staging

```powershell
Copy-Item .env.staging.example .env.staging
# preencha .env.staging com as chaves reais
.\.venv\Scripts\python.exe scripts\pre_deploy_check.py --env-file .env.staging
```

## Como rodar em producao

```powershell
Copy-Item .env.production.example .env.production
# preencha .env.production com as chaves reais
.\.venv\Scripts\python.exe scripts\pre_deploy_check.py --env-file .env.production
```

## Saida esperada

```text
[OK] /health
[OK] login admin
[OK] listagem de produtos
[OK] login cliente
[OK] dados do cliente preparados
[OK] criacao de pedido
[OK] leitura do pedido no admin
[OK] alteracao administrativa
[OK] auditoria gerada
[OK] RLS basica
[OK] limpeza do pedido de teste

Pre-deploy checklist finished successfully.
```

## RLS validado

O script verifica:

- anon consegue ler `products`;
- anon nao consegue ler `orders`;
- cliente autenticado consegue ler o proprio pedido criado;
- cliente autenticado nao consegue ler `audit_logs`.

## Observacoes

Por padrao, o pedido de teste e cancelado no final. Use `--keep-order` se quiser
mantelo para inspecao manual.

Nao rode esse script com usuario cliente real. Use uma conta de teste clara,
por exemplo `cliente-staging@lugano.test`.
