# Seguranca

## Supabase

- Rode as migrations em ordem, incluindo `005_customer_preferences.sql` e `006_security_hardening.sql`.
- A chave `service_role` deve ficar somente no backend, no `.env`.
- O frontend pode usar apenas `SUPABASE_URL` e `SUPABASE_ANON_KEY`.
- Clientes autenticados leem seus proprios pedidos, pontos e usos de promocao via RLS.
- Escritas criticas de pedidos, itens, pontos e uso de cupom passam pela API com service role.

## Admin

- Use login administrativo com Supabase Auth e tabela `admin_users`.
- `owner` gerencia equipe.
- `manager` cria/edita produtos, promocoes, clientes e pedidos.
- `staff` le dados operacionais e atualiza pedidos.
- `X-Admin-Key` e fallback tecnico. Em producao, prefira `ADMIN_API_KEY_ENABLED=false`.

## CORS

- Em producao, configure `ALLOWED_ORIGINS` somente com os dominios reais.
- Nao use `*`, `localhost` ou `127.0.0.1` em producao.
- Os metodos e headers permitidos sao controlados por `ALLOWED_METHODS` e `ALLOWED_HEADERS`.

## Rate Limit

- `RATE_LIMIT_ENABLED=true` deve ficar ativo.
- `RATE_LIMIT_TRUST_PROXY_HEADERS=false` e o padrao mais seguro.
- Ative `RATE_LIMIT_TRUST_PROXY_HEADERS=true` somente se estiver atras de proxy confiavel que sobrescreve `X-Forwarded-For`.

## Variaveis sensiveis

- `.env` esta no `.gitignore`.
- Troque `SECRET_KEY` e `ADMIN_API_KEY` por valores fortes antes de producao.
- Em producao, `SECRET_KEY` precisa ter pelo menos 32 caracteres.
- Se `ADMIN_API_KEY_ENABLED=true`, `ADMIN_API_KEY` tambem precisa ter pelo menos 32 caracteres.

## Revisao final

Antes do deploy final, rode:

```powershell
.\.venv\Scripts\python.exe scripts\final_security_review.py --env-file .env.production --require-remote true
```
