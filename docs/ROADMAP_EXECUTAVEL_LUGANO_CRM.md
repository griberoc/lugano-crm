# Roadmap executavel do Lugano CRM

Este documento e a fonte da verdade para transformar o Lugano CRM em um
sistema de delivery pronto para cliente real. Ele organiza seguranca, backend,
frontend, operacao e deploy em tasks executaveis.

## Como usar

1. Trabalhe sempre a partir da branch `develop`.
2. Abra uma branch por task: `feature/P0-001-seguranca-segredos`.
3. Abra uma conversa Codex por task grande ou epic.
4. Copie o prompt da task para a nova conversa.
5. Execute a task, rode testes e valide manualmente.
6. So faca commit/push quando a task estiver validada.
7. Depois de aprovado em staging, faca merge para `main`.

## Status

- `Backlog`: mapeada, ainda nao iniciada.
- `Ready`: pronta para executar.
- `Doing`: em execucao.
- `Blocked`: depende de acesso, credencial, suporte externo ou decisao.
- `Review`: implementada, aguardando validacao.
- `Done`: validada e aceita.

## Prioridades

- `P0`: bloqueia producao ou pode causar perda financeira/dados/seguranca.
- `P1`: necessario para operacao profissional.
- `P2`: melhora experiencia, eficiencia ou escalabilidade.
- `P3`: evolucao futura.

## Epics

| Epic | Nome | Objetivo |
| --- | --- | --- |
| SEC | Seguranca | Reduzir risco de vazamento, XSS, abuso e acesso indevido. |
| CORE | Backend e regras | Garantir pedido, pagamento, fidelidade e entrega em ordem correta. |
| UX | Consumidor | Tornar compra simples, bonita, confiavel e mobile-first. |
| ADM | Admin | Operacao diaria clara para equipe Lugano. |
| PAY | Pagamentos | Mercado Pago, Pix e conciliacao automatica. |
| DLV | Entrega | Machine Delivery, cotacao, despacho e rastreio. |
| OPS | Deploy e operacao | Staging, producao, monitoramento, backup e checklist. |
| QA | Qualidade | Testes automatizados, E2E e validacao manual. |

## Ordem executiva recomendada

1. `P0-001` Higiene de segredos e ambientes.
2. `P0-002` Validacao real Supabase, migrations e RLS.
3. `P0-003` Hardening XSS, CSP e headers do frontend.
4. `P0-004` Corrigir ciclo do pedido: pagamento -> fidelidade -> entrega.
5. `P0-005` Mercado Pago end-to-end.
6. `P0-006` Machine Delivery end-to-end.
7. `P0-007` Testes E2E do fluxo critico.
8. `P0-008` Gate final de deploy.
9. `P1-001` Checkout premium e mobile-first.
10. `P1-002` Painel cliente premium.
11. `P1-003` Admin operacional.
12. `P1-004` Observabilidade e alertas.

## Board sugerido no GitHub Projects

Colunas:

```text
Backlog -> Ready -> Doing -> Review -> Staging -> Done
```

Labels:

```text
priority/P0
priority/P1
priority/P2
epic/security
epic/backend
epic/frontend
epic/admin
epic/payment
epic/delivery
epic/ops
epic/qa
needs-manual-validation
needs-external-credentials
blocked
```

## Tasks P0

### P0-001 - Higiene de segredos e ambientes

Status: `Ready`

Branch:

```text
feature/P0-001-seguranca-segredos
```

Objetivo:

- Garantir que nenhum segredo real esteja versionado.
- Rotacionar segredos expostos em prints/conversas.
- Separar local, staging e producao.
- Padronizar variaveis obrigatorias.

Escopo:

- `.gitignore`
- `.env.example`
- `.env.staging.example`
- `.env.production.example`
- `scripts/final_security_review.py`
- `scripts/pre_deploy_check.py`
- documentacao de rotacao.

Checklist:

- [ ] Confirmar que `.env`, `.env.production` e backups nao entram no Git.
- [ ] Rodar busca por possiveis tokens no repo.
- [ ] Listar chaves a rotacionar: Supabase, Machine, Mercado Pago, admin key.
- [ ] Garantir `ADMIN_API_KEY_ENABLED=false` em producao.
- [ ] Garantir `SUPABASE_SERVICE_ROLE_KEY` apenas no backend/Render.
- [ ] Garantir frontend com apenas `SUPABASE_ANON_KEY`.
- [ ] Atualizar guia de variaveis por ambiente.
- [ ] Rodar `final_security_review.py` quando houver `.env.production` real.

Criterios de aceite:

- [ ] Nenhum segredo real aparece em arquivos rastreados.
- [ ] `.env.production.example` tem todas as variaveis necessarias sem valores reais.
- [ ] O deploy de producao nao depende de `X-Admin-Key`.
- [ ] O usuario sabe quais chaves precisa regenerar.

Validacao:

```powershell
git status --short
git diff -- .gitignore .env.example .env.production.example .env.staging.example
.\.venv\Scripts\python.exe -m pytest tests\unit\test_security_config.py
```

Prompt para nova conversa:

```text
Task P0-001 - Higiene de segredos e ambientes.
Projeto: Lugano CRM.
Repo local: C:\Users\guilh\Documents\Codex\2026-06-17\files-mentioned-by-the-user-cafeteria\outputs\lugano-crm
Branch base: develop.
Objetivo: garantir que nenhum segredo real esteja versionado, padronizar variaveis de ambiente e preparar checklist de rotacao.
Nao exponha valores secretos. Nao faca commit sem eu pedir.
```

### P0-002 - Validacao Supabase, migrations e RLS

Status: `Ready`

Branch:

```text
feature/P0-002-supabase-rls
```

Objetivo:

- Confirmar que o banco remoto esta compativel com o codigo.
- Garantir RLS correta em tabelas sensiveis.
- Evitar leitura anonima em `orders`, `audit_logs`, `profiles` e dados internos.

Escopo:

- `supabase/migrations/*.sql`
- `supabase/README.md`
- `scripts/final_security_review.py`
- `scripts/pre_deploy_check.py`

Checklist:

- [ ] Confirmar migrations `001` a `012` rodadas.
- [ ] Confirmar `profiles.preferences`.
- [ ] Confirmar `delivery_dispatches`.
- [ ] Confirmar `payment_provider`, `payment_reference`, `payment_payload`.
- [ ] Testar anon em `orders`: deve negar.
- [ ] Testar anon em `audit_logs`: deve negar.
- [ ] Testar cliente lendo proprio pedido: deve permitir.
- [ ] Testar cliente lendo pedido de outro: deve negar.
- [ ] Documentar queries de verificacao no Supabase.

Criterios de aceite:

- [ ] Scripts de seguranca passam contra ambiente real.
- [ ] RLS bloqueia anon em dados sensiveis.
- [ ] Owner admin existe e esta ativo.

Validacao:

```powershell
.\.venv\Scripts\python.exe scripts\final_security_review.py --env-file .env.production --require-remote true
.\.venv\Scripts\python.exe scripts\pre_deploy_check.py --env-file .env.production
```

### P0-003 - XSS, CSP e headers de seguranca

Status: `Done`

Branch:

```text
feature/P0-003-xss-csp
```

Objetivo:

- Reduzir risco de XSS no frontend.
- Adicionar CSP e headers fortes para paginas estaticas e API.
- Remover renderizacao insegura de dados dinamicos.

Escopo:

- `frontend/admin/app.js`
- `frontend/orders/app.js`
- `frontend/customer/app.js`
- `frontend/auth/app.js`
- `frontend/_headers`
- `app/core/security_headers.py`
- testes unitarios ou utilitarios de escape.

Checklist:

- [x] Criar helper `escapeHTML`.
- [x] Substituir `innerHTML` que renderiza dados vindos do banco/API.
- [x] Manter templates internos seguros quando os dados forem escapados.
- [x] Adicionar CSP em `frontend/_headers`.
- [x] Adicionar CSP basica no backend.
- [x] Validar que QR Code Mercado Pago ainda funciona.
- [x] Validar que imagens do catalogo continuam carregando.
- [x] Validar landing, delivery, cliente e admin no navegador.

Criterios de aceite:

- [x] Produto/cliente/endereco/cupom malicioso nao injeta HTML.
- [x] Headers de seguranca aparecem no frontend publicado.
- [x] Checkout e admin continuam funcionais.

Validacao:

```powershell
rg -n "innerHTML" frontend
.\.venv\Scripts\python.exe -m pytest
```

### P0-004 - Ciclo correto do pedido

Status: `Done`

Branch:

```text
feature/P0-004-order-lifecycle
```

Objetivo:

- Corrigir a ordem de negocio para evitar recompensa/entrega antes de pagamento.

Regra alvo:

```text
Pedido criado -> pagamento pendente -> pagamento aprovado -> confirmar pedido
-> preparar -> enviar entrega -> entregue -> creditar/confirmar fidelidade
```

Decisao recomendada:

- Fidelidade so deve ser creditada quando pagamento estiver `paid` ou pedido
  estiver `delivered`.
- Entrega externa so deve ser solicitada quando pagamento estiver `paid`
  ou admin confirmar manualmente.

Escopo:

- `app/services/order.py`
- `app/services/payment.py`
- `app/services/delivery.py`
- `app/api/v1/endpoints/admin.py`
- `app/api/v1/endpoints/payments.py`
- testes de pedido/pagamento/entrega/fidelidade.

Checklist:

- [x] Criar estados claros para pagamento e pedido.
- [x] Remover credito imediato de pontos na criacao do pedido.
- [x] Mover credito para evento correto.
- [x] Bloquear dispatch Machine antes de pagamento.
- [x] Atualizar webhook Mercado Pago para disparar proxima etapa correta.
- [x] Atualizar admin para acao manual quando necessario.
- [x] Garantir idempotencia para webhook repetido.

Criterios de aceite:

- [x] Pedido Pix pendente nao gera pontos.
- [x] Pedido Pix pendente nao solicita entrega automatica.
- [x] Pagamento aprovado atualiza `payment_status=paid`.
- [x] Pontos nao duplicam em webhook repetido.
- [x] Entrega nao duplica em webhook repetido.

Validacao:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_order_service.py tests\unit\test_payment_service.py tests\unit\test_delivery_service.py
```

### P0-005 - Mercado Pago end-to-end

Status: `Done`

Branch:

```text
feature/P0-005-mercado-pago-e2e
```

Objetivo:

- Validar Pix Mercado Pago do pedido ate confirmacao por webhook.

Escopo:

- `app/services/payment.py`
- `app/api/v1/endpoints/payments.py`
- `frontend/orders/*`
- variaveis `MERCADO_PAGO_*`
- documentacao de teste.

Checklist:

- [x] Configurar access token de teste.
- [x] Configurar URL publica de webhook.
- [x] Criar pedido real de teste.
- [x] Ver QR Code no checkout.
- [x] Ver copia-e-cola.
- [x] Confirmar webhook recebido.
- [x] Confirmar `payment_status` atualizado.
- [x] Confirmar admin exibindo pagamento.
- [x] Documentar como trocar sandbox/producao.

Criterios de aceite:

- [x] Cliente consegue pagar Pix dinamico.
- [x] Sistema atualiza pagamento automaticamente.
- [x] Falha/rejeicao aparece de forma clara.
- [x] Nenhum token Mercado Pago fica no frontend.

### P0-006 - Machine Delivery end-to-end

Status: `Blocked`

Motivo atual:

- API Machine respondeu `403 Forbidden`; depende de credencial/permissao correta.

Branch:

```text
feature/P0-006-machine-delivery-e2e
```

Objetivo:

- Validar cotacao, despacho, rastreio e cancelamento com a Machine.

Escopo:

- `app/services/delivery.py`
- `scripts/test_machine_delivery.py`
- `supabase/migrations/012_delivery_dispatches.sql`
- admin de pedidos.

Checklist:

- [ ] Obter credenciais corretas de homologacao/producao.
- [ ] Validar `POST /entregas/estimativas`.
- [ ] Validar `POST /entregas`.
- [ ] Salvar `external_delivery_id`.
- [ ] Salvar link de rastreio.
- [ ] Permitir cancelamento com motivo.
- [ ] Exibir status no admin.
- [ ] Bloquear despacho antes do pagamento, conforme P0-004.

Criterios de aceite:

- [ ] Cotacao retorna valor/minutos.
- [ ] Entrega de teste e criada no ambiente correto.
- [ ] Admin ve status e rastreio.
- [ ] Erro da Machine e exibido/logado sem expor credenciais.

### P0-007 - Testes E2E do fluxo critico

Status: `Ready`

Branch:

```text
feature/P0-007-e2e-checkout
```

Objetivo:

- Validar o fluxo real que o cliente e a equipe vao usar.

Fluxos:

- Landing abre.
- Cliente cria conta/entra.
- Cliente monta carrinho.
- Cliente retorna ao pedido apos login.
- Cliente cadastra endereco.
- Cliente aplica cupom.
- Cliente gera pagamento.
- Admin ve pedido.
- Admin altera status.
- Cliente acompanha status/fidelidade.

Checklist:

- [ ] Escolher ferramenta: Playwright.
- [ ] Criar fixtures de usuario/produto/cupom.
- [ ] Testar desktop.
- [ ] Testar mobile.
- [ ] Testar erro de login.
- [ ] Testar carrinho persistente.
- [ ] Testar retorno pos-login.

Criterios de aceite:

- [ ] E2E principal passa localmente.
- [ ] Capturas mobile/desktop sem layout quebrado.
- [ ] Fluxo pode ser repetido sem dados duplicados perigosos.

### P0-008 - Gate final de deploy

Status: `Ready`

Branch:

```text
feature/P0-008-deploy-gate
```

Objetivo:

- Criar barreira final antes de entregar ao cliente.

Checklist:

- [ ] `pytest` completo.
- [ ] `final_security_review.py`.
- [ ] `pre_deploy_check.py`.
- [ ] Healthcheck Render.
- [ ] Frontend sem `127.0.0.1`.
- [ ] Supabase Auth URLs corretas.
- [ ] CORS apenas dominio real.
- [ ] Owner admin validado.
- [ ] Pedido real validado ponta a ponta.
- [ ] Backup/retencao documentado.

Criterios de aceite:

- [ ] Nenhum P0 aberto.
- [ ] Deploy staging validado.
- [ ] Cliente consegue operar demo guiada.

## Tasks P1

| ID | Task | Epic | Status | Dependencia |
| --- | --- | --- | --- | --- |
| P1-001 | Checkout premium e mobile-first | UX | Backlog | P0-003, P0-004 |
| P1-002 | Painel cliente premium | UX | Backlog | P0-004 |
| P1-003 | Admin operacional | ADM | Backlog | P0-004, P0-006 |
| P1-004 | Observabilidade e alertas | OPS | Backlog | P0-005, P0-006 |
| P1-005 | Backups e retencao operacional | OPS | Backlog | P0-002 |
| P1-006 | Performance e imagens do cardapio | UX | Backlog | P0-003 |
| P1-007 | Logs/auditoria por pedido | ADM | Backlog | P0-004 |
| P1-008 | Documentacao de operacao para cliente | OPS | Backlog | P0-008 |

## Tasks P2

| ID | Task | Epic | Status |
| --- | --- | --- | --- |
| P2-001 | Cupom fiscal/impressao de pedido | CORE | Backlog |
| P2-002 | Taxa de entrega por bairro/raio | DLV | Backlog |
| P2-003 | Horario de funcionamento e loja fechada | UX | Backlog |
| P2-004 | Recompra rapida e favoritos | UX | Backlog |
| P2-005 | Mercado Pago cartao/Checkout Brick | PAY | Backlog |
| P2-006 | Analytics avancado de campanhas | ADM | Backlog |

## Ritual de execucao

Antes de iniciar uma task:

```powershell
git checkout develop
git status --short
git checkout -b feature/P0-XXX-nome
```

Durante:

- Leia os arquivos afetados.
- Mantenha escopo estreito.
- Rode testes focados.
- Valide no navegador quando afetar frontend.

Antes de concluir:

```powershell
.\.venv\Scripts\python.exe -m pytest
git status --short
```

Ao pedir commit:

```powershell
git add <arquivos-da-task>
git commit -m "P0-XXX: descricao curta"
git push -u origin feature/P0-XXX-nome
```

## Regra de ouro

Uma task so termina quando existe evidencia:

- teste automatizado;
- validacao manual;
- criterio de aceite marcado;
- nenhum segredo exposto;
- nenhum P0 novo criado pela mudanca.
