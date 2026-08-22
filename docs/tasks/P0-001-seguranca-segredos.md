# P0-001 - Higiene de segredos e ambientes

Prioridade: P0
Epic: SEC
Status: Review
Branch sugerida: `feature/P0-001-seguranca-segredos`

## Objetivo

Garantir que nenhum segredo real esteja versionado, padronizar variaveis de
ambiente e preparar a rotacao de chaves antes de producao.

## Escopo

- `.gitignore`
- `.env.example`
- `.env.staging.example`
- `.env.production.example`
- scripts de seguranca/pre-deploy
- documentacao de rotacao

## Checklist

- [x] Confirmar que `.env` e `.env.production` estao ignorados.
- [x] Buscar possiveis tokens/chaves em arquivos rastreados.
- [x] Listar chaves a rotacionar: Supabase, Machine, Mercado Pago, admin key.
- [x] Garantir `ADMIN_API_KEY_ENABLED=false` em producao.
- [x] Confirmar service role apenas no backend/Render.
- [x] Confirmar anon key apenas no frontend.
- [x] Atualizar docs de variaveis por ambiente.

## Separacao por ambiente

- Local: copie `.env.example` para `.env`; use apenas projetos e credenciais de
  desenvolvimento. O arquivo real permanece fora do Git.
- Staging: use `.env.staging.example` como inventario e configure os valores no
  cofre de segredos do provedor. Nao reutilize chaves de producao.
- Producao: use `.env.production.example` como inventario e configure os valores
  exclusivamente no backend/Render. `ADMIN_API_KEY_ENABLED=false` e
  `ADMIN_API_KEY` vazio sao obrigatorios.
- Frontend: publique somente `SUPABASE_URL` e `SUPABASE_ANON_KEY` por meio de
  `frontend/config.js`. Nunca copie `SUPABASE_SERVICE_ROLE_KEY`, tokens de
  pagamento, Machine, webhooks ou senhas para arquivos estaticos.

Os arquivos `*.example` contem apenas nomes, defaults nao sensiveis e
placeholders. Valores reais devem existir somente no ambiente de execucao ou no
cofre do provedor.

## Rotacao obrigatoria antes de producao

Considere comprometida qualquer credencial que tenha aparecido em print,
conversa, log, arquivo compartilhado ou terminal gravado. Rotacione nesta ordem:

1. Supabase: gere novas chaves secret/service role no painel, atualize apenas o
   backend e revogue a anterior. Confirme que o frontend continua usando anon.
2. Machine Delivery: regenere API key e credenciais de autenticacao, atualize
   staging/producao separadamente e invalide as anteriores.
3. Mercado Pago: regenere access token e segredo de webhook; atualize o backend
   e valide a assinatura de uma notificacao de teste antes de revogar o antigo.
4. Admin: mantenha `ADMIN_API_KEY_ENABLED=false` em producao e remova qualquer
   `X-Admin-Key` do frontend. Se a chave legada foi exposta, regenere-a mesmo
   estando desativada.
5. Aplicacao e integracoes: regenere `SECRET_KEY`, tokens de notificacao e de
   monitoramento que possam ter sido expostos. A troca de `SECRET_KEY` pode
   invalidar sessoes/tokens existentes; programe uma janela controlada.

Registre somente responsavel, data, ambiente, identificador/versao da chave e
confirmacao da revogacao. Nunca registre o valor da credencial.

## Verificacao segura

```powershell
.\.venv\Scripts\python.exe scripts\scan_tracked_secrets.py
git check-ignore .env .env.production .env.staging .env.backup
.\.venv\Scripts\python.exe scripts\final_security_review.py --env-file .env.production
```

O ultimo comando deve ser executado apenas quando o arquivo real existir
localmente. Ele nao deve ser anexado a tickets nem ter sua saida acompanhada de
valores de ambiente.

## Criterios de aceite

- [ ] Nenhum segredo real aparece em arquivos rastreados.
- [ ] Ambiente de producao nao depende de `X-Admin-Key`.
- [ ] Existe lista clara de chaves a regenerar.

## Validacao

```powershell
git status --short
git diff -- .gitignore .env.example .env.production.example .env.staging.example
.\.venv\Scripts\python.exe -m pytest tests\unit\test_security_config.py
.\.venv\Scripts\python.exe -m pytest tests\unit\test_scan_tracked_secrets.py
```
