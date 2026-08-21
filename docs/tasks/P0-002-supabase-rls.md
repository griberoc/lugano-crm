# P0-002 - Validacao Supabase, migrations e RLS

Prioridade: P0
Epic: SEC/OPS
Status: Done
Branch sugerida: `feature/P0-002-supabase-rls`

## Objetivo

Confirmar que o Supabase remoto esta compativel com o codigo e que RLS bloqueia
acesso indevido a dados sensiveis.

## Escopo

- `supabase/migrations/*.sql`
- `supabase/README.md`
- `scripts/final_security_review.py`
- `scripts/pre_deploy_check.py`

## Checklist

- [x] Confirmar migrations `001` a `012`.
- [x] Confirmar colunas novas: `profiles.preferences`, pagamentos e entrega.
- [x] Testar anon em `orders`.
- [x] Testar anon em `audit_logs`.
- [x] Testar cliente lendo proprio pedido.
- [x] Testar cliente tentando ler pedido de outro.
- [x] Validar owner admin ativo.

## Criterios de aceite

- [x] `orders` e `audit_logs` negam leitura anonima.
- [x] Cliente acessa apenas dados proprios.
- [x] Scripts finais passam contra ambiente real.

## Validacao

```powershell
.\.venv\Scripts\python.exe scripts\final_security_review.py --env-file .env.production --require-remote true
.\.venv\Scripts\python.exe scripts\pre_deploy_check.py --env-file .env.production
```
