# Lugano CRM

Backend em Python para uma cafeteria e chocolateria chamada Lugano.

O projeto usa FastAPI para expor uma API REST com módulos iniciais para:

- pedidos de delivery;
- programa de fidelidade;
- promoções e cupons;
- integração com Supabase para dados e autenticação.

## Stack

- Python 3.11+
- FastAPI
- Supabase
- Pydantic v2
- Poetry
- Pytest
- Ruff

## Estrutura

```text
app/
  api/v1/endpoints/   Rotas HTTP
  core/               Configurações, segurança e exceções
  db/                 Cliente Supabase
  schemas/            Schemas Pydantic
  services/           Regras de negócio
  main.py             Aplicação FastAPI
frontend/
  client/             Portal do cliente final
  admin/              Portal administrativo
  auth/               Tela de acesso usada pelo portal do cliente
  orders/             Tela de delivery usada pelo portal do cliente
  customer/           Painel usado pelo portal do cliente
tests/
  unit/               Testes unitários
```

## Como abrir no VS Code

Abra a pasta `lugano-crm` no VS Code:

```powershell
code .
```

O projeto já inclui configurações em `.vscode/` para depuração, testes e execução da API.

## Setup local

Crie o arquivo `.env` a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

Preencha as variáveis do Supabase no `.env`.

Instale as dependências com Poetry:

```powershell
poetry install
```

Ou, se preferir usar `venv` e `pip`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Suba a API:

```powershell
poetry run uvicorn app.main:app --reload
```

A documentação interativa ficará em:

```text
http://127.0.0.1:8000/docs
```

## Testes

```powershell
poetry run pytest tests -v
```

## Roadmap, seguranca e deploy

Toda a documentacao operacional foi consolidada em:

```text
docs/roadmap-sistema-completo.md
```

Esse roadmap cobre:

- estado atual do sistema;
- rotas e endpoints principais;
- papeis administrativos;
- Supabase, RLS, migrations e seed;
- variaveis de ambiente;
- deploy backend/frontend;
- seguranca, backups, monitoramento e handoff;
- checklist final de aceite.

Smoke test com Supabase real:

```powershell
python scripts\smoke_test_api.py --token "ACCESS_TOKEN_DO_USUARIO"
```

## Artefatos de deploy

O projeto inclui arquivos prontos para deploy:

- `render.yaml` para Render;
- `render.staging.yaml` para Render staging;
- `railway.json` para Railway;
- `fly.toml` e `Dockerfile` para Fly.io;
- `docker-compose.prod.yml` para VPS;
- `frontend/vercel.json`, `frontend/_redirects` e `frontend/_headers` para site estatico.

## Portais frontend

Com o servidor estático rodando a partir de `frontend/`, os portais oficiais são:

```text
http://127.0.0.1:5176/client/
http://127.0.0.1:5176/admin/
```

O portal do cliente final fica em `frontend/client` e agrupa início, acesso,
delivery e painel do cliente.

O portal administrativo fica em `frontend/admin` e concentra produtos, clientes,
pedidos, campanhas e conexão com a API administrativa.

Os módulos `frontend/auth`, `frontend/orders` e `frontend/customer` continuam
existindo como telas internas do portal do cliente.

O antigo `frontend/app` fica apenas como entrada legada de desenvolvimento.

## Endpoints iniciais

- `GET /health`
- `GET /health/ready`
- `POST /api/v1/orders/`
- `GET /api/v1/orders/`
- `GET /api/v1/orders/{order_id}`
- `POST /api/v1/orders/{order_id}/cancel`
- `GET /api/v1/loyalty/`
- `GET /api/v1/loyalty/transactions`
- `POST /api/v1/promotions/validate`

## Variáveis de ambiente

| Variável | Descrição |
| --- | --- |
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_ANON_KEY` | Chave anon do Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | Chave service role do Supabase |
| `APP_ENV` | Ambiente da aplicação |
| `SECRET_KEY` | Chave interna da aplicação |
| `ALLOWED_ORIGINS` | Origens CORS permitidas |
| `LOG_LEVEL` | Nivel de log da API |
| `RATE_LIMIT_ENABLED` | Liga/desliga rate limit global |
| `RATE_LIMIT_REQUESTS` | Número de requisições permitidas por janela |
| `RATE_LIMIT_WINDOW_SECONDS` | Tamanho da janela de rate limit em segundos |
| `RATE_LIMIT_EXEMPT_PATHS` | Rotas sem rate limit, separadas por vírgula |
| `DELIVERY_BASE_FEE` | Frete base em centavos |
| `DELIVERY_FREE_THRESHOLD` | Valor mínimo para frete grátis em centavos |
| `POINTS_PER_REAL` | Pontos por R$ 1,00 gasto |
| `PAYMENT_PROVIDER` | Provedor de pagamento: `manual`, `pix_static` ou `mercado_pago` |
| `PIX_KEY` | Chave Pix usada para Pix copia e cola |
| `MONITORING_WEBHOOK_URL` | Webhook opcional para alertas operacionais |

## Próximos passos sugeridos

- Aplicar migrations `001` ate `011` no Supabase de producao.
- Publicar backend no Render com `render.yaml`.
- Publicar frontend no Cloudflare Pages usando `frontend/config.production.example.js`.
- Rodar `scripts/final_security_review.py` e `scripts/pre_deploy_check.py`.
- Fazer entrega assistida seguindo `docs/roadmap-sistema-completo.md`.
