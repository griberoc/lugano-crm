# P0-007 - Testes E2E do fluxo critico

Prioridade: P0
Epic: QA/UX
Status: Review
Branch sugerida: `feature/P0-007-e2e-checkout`

## Objetivo

Criar testes ponta a ponta para o fluxo principal do consumidor e admin.

## Fluxos obrigatorios

- [x] Landing abre.
- [x] Cliente entra.
- [x] Cliente monta carrinho.
- [x] Login retorna ao pedido.
- [x] Cliente cadastra endereco.
- [x] Cliente aplica cupom.
- [x] Cliente gera pagamento.
- [x] Admin ve pedido.
- [x] Admin altera status.
- [x] Cliente acompanha pedido/fidelidade.

## Criterios de aceite

- [x] E2E principal e deterministico, com fronteiras externas simuladas.
- [x] Mobile e desktop geram capturas para revisao visual.
- [x] Cada teste usa fixtures isoladas e evita dados remotos/duplicidade.

## Validacao

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest tests\e2e -m e2e
```

Ferramenta recomendada: Playwright.

## Estrategia e fixtures

- O frontend real e servido por HTTP local durante a sessao de testes.
- Usuario, produto, cupom, endereco, pedido e admin usam dados exclusivos de
  teste em memoria.
- Supabase Auth e API sao interceptados na fronteira HTTP; nenhum segredo ou
  dado remoto e necessario.
- O mesmo fluxo roda nos viewports `1440x1000` e `390x844`.
- As capturas ficam em `test-results/e2e/`, ignoradas pelo Git.

## Validacao manual

1. Instale as dependencias de `requirements-dev.txt` e o Chromium do Playwright.
2. Rode o comando E2E acima.
3. Abra `test-results/e2e/critical-flow-desktop.png` e
   `critical-flow-mobile.png`; confira o painel final, textos cortados,
   sobreposicoes e rolagem horizontal.
4. Para revisar visualmente as etapas intermediarias, remova temporariamente o
   modo headless em `tests/e2e/conftest.py` (`launch(headless=False)`) e rode a
   suite focada.
