# Seed inicial

O script `scripts/seed_initial_data.py` popula dados minimos para staging ou
producao.

Ele e idempotente: pode ser executado mais de uma vez. Quando encontra um item
existente pelo campo de referencia, ele atualiza; quando nao encontra, ele cria.

## O que o seed cria/atualiza

- Niveis de fidelidade em `loyalty_tiers`;
- produtos iniciais em `products`;
- campanhas padrao em `promotions`;
- configuracoes operacionais em `operational_settings`;
- usuario owner no Supabase Auth, se ainda nao existir;
- perfil do owner em `profiles`;
- permissao owner em `admin_users`.

Os dados editaveis ficam em:

```text
supabase/seeds/initial_data.json
```

## Pre-requisitos

Antes de rodar:

1. Aplique as migrations 001-011 no Supabase.
2. Preencha `.env.staging` ou `.env.production`.
3. Tenha a `SUPABASE_SERVICE_ROLE_KEY` correta do ambiente.
4. Defina as variaveis do owner:

```text
SEED_OWNER_EMAIL=owner-staging@lugano.test
SEED_OWNER_PASSWORD=change-this-password
SEED_OWNER_FULL_NAME=Owner Staging Lugano
```

Se o owner ja existir no Supabase Auth, a senha nao e alterada; o script apenas
garante perfil e papel `owner`.

## Dry-run

Use antes de gravar:

```powershell
.\.venv\Scripts\python.exe scripts\seed_initial_data.py --env-file .env.staging --dry-run
```

## Rodar em staging

```powershell
Copy-Item .env.staging.example .env.staging
# preencha as chaves reais
.\.venv\Scripts\python.exe scripts\seed_initial_data.py --env-file .env.staging
```

## Rodar em producao

```powershell
Copy-Item .env.production.example .env.production
# preencha as chaves reais
.\.venv\Scripts\python.exe scripts\seed_initial_data.py --env-file .env.production
```

## Ajustar produtos e campanhas

Edite `supabase/seeds/initial_data.json`.

Campos usados como referencia para atualizar sem duplicar:

```text
loyalty_tiers: name
products: name
promotions: code
operational_settings: key
```

## Observacoes de seguranca

- Nunca coloque `SUPABASE_SERVICE_ROLE_KEY` no frontend.
- Rode o seed de staging contra Supabase staging.
- Rode o seed de producao apenas depois do checklist de staging passar.
- Use owner real em producao e owner de teste em staging.
