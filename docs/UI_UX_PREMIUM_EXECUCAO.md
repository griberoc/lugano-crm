# UI/UX Premium — execução integrada

Data: 08/09/2026. Branch: `feature/UX-premium-integrado`, criada a partir de `develop`.
Entrega local revisada; **commit autorizado pelo usuário, sem push, deploy ou transações reais**.

O pedido de executar o roadmap inteiro foi tratado como uma execução integrada,
em vez de abrir uma branch/conversa por task. As alterações anteriores do usuário
foram preservadas, inclusive `frontend/config.js` e os roadmaps técnicos.

## Resultado

- Entrada diretamente no cardápio, busca e categorias; detalhe do produto em dialog/bottom sheet.
- Carrinho persistente, quantidade, observação, desfazer e reconciliação com catálogo atual.
- Checkout em etapas, login contextual, endereço salvo, rascunhos e revisão financeira.
- Confirmação persistente, consulta recuperável, Pix e proteção de reenvio incerto.
- Minha Lugano com pedido ativo, pontos e recompra antes dos formulários.
- Admin com fila, busca/filtros, próxima ação segura, edição em dialogs e tabelas mobile.
- Shell compartilhado sem iframes; tipografia funcional sans e assinatura Source Serif 4 local.
- Estados compartilhados, foco visível, alvos de toque, imagens locais e movimento reduzido.

Não foram inventados produtos, preços, complementos, horários, áreas atendidas ou prazos.
21st.dev não foi incorporado: os padrões necessários foram implementados em HTML/CSS/JS
vanilla e `dialog` nativo, sem novas dependências de execução.

## Como revisar agora

1. Abra [Cardápio local](http://127.0.0.1:5176/orders/).
2. Busque um produto, abra o detalhe, adicione observação/quantidade e monte o carrinho.
3. Avance, volte e atualize a página para conferir persistência.
4. Entre com sua conta existente para revisar endereço, pagamento e Minha Lugano.
5. Abra [Admin local](http://127.0.0.1:5176/admin/) com suas credenciais habituais.
6. Confira primeiro em 390 px, depois desktop; só então aprove ou peça ajustes.

A prévia mostra dados reais, mas injeta `previewReadOnly=true`: a interface bloqueia
criação de conta/pedido, edição e exclusão. Login, consultas, cotação e validação de
cupom continuam disponíveis. O aviso inferior identifica esse modo. É uma proteção
da prévia, não uma nova regra de negócio nem uma barreira de segurança do backend.

O fluxo com gravação foi testado com respostas isoladas de teste, sem cobrança,
mensagens, pontos ou despacho reais. A configuração versionada não foi trocada.
API local: `http://127.0.0.1:8000`; frontend: porta `5176`.

Para reiniciar, em dois terminais do repositório:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe scripts/preview_ui.py
```

## Inventário — UX-001

| Rota | Objetivo / ação principal | Estados e observações |
| --- | --- | --- |
| `/` | Abrir cardápio | Redirect local e regras de hosting apontam para compra. |
| `/orders/` | Escolher e concluir pedido | Loading, vazio, busca sem resultado, erro/retry, carrinho, identificação, entrega, pagamento, confirmação e consulta. |
| `/auth/` | Entrar ou criar conta | Visitante, sessão existente, envio, erro de campo/credencial, confirmação de email. |
| `/customer/` | Acompanhar e comprar novamente | Visitante, carregamento, dados completos/parciais, pontos, pedido ativo, histórico, recompra, dados/endereço/preferências. |
| `/admin/` | Operar pedidos | Gate de login; visão geral, fila/detalhe, produtos, clientes, campanhas, relatórios, auditoria, equipe e acesso. Papéis atendente/gerente/proprietário. |
| `/client/#/...` | Compatibilidade de links | `inicio/delivery` → orders; `acesso` → auth; `painel` → customer. |
| `/app/#/...` | Compatibilidade de links antigos | `inicio/pedidos` → orders; `acesso` → auth; `cliente` → customer. |
| `/landing/` | Institucional existente | Preservada; não é mais a entrada principal nem substitui a experiência de compra. |

Os equivalentes `index.html` usam as mesmas telas. Não há iframe nos templates ativos.

### Top 10 problemas priorizados no inventário

1. P0 — Cardápio precedido por narrativa e navegação redundante.
2. P0 — Etapas do checkout competindo no mobile.
3. P0 — Perda de contexto no login, refresh e consulta posterior.
4. P0 — Resultado incerto de envio podia induzir novo pedido.
5. P0 — Frete desconhecido confundido com entrega gratuita.
6. P0 — Ações operacionais antes de pagamento e confirmações pouco explícitas.
7. P1 — Erros remotos sem padrão, retry ou distinção de estado parcial.
8. P1 — Serif em controles, escala e alvos inconsistentes.
9. P1 — Formulários antes de acompanhamento/fidelidade e ausência de recompra reconciliada.
10. P1 — Admin comprimido no mobile, mídia externa e instabilidade de carregamento.

## Situação de cada task

`Review` significa implementação técnica candidata à revisão, não aprovação visual,
homologação em produção ou autorização de commit. Aceites externos permanecem em `Doing`.

| Task | Status | Implementação / evidência / aceite restante |
| --- | --- | --- |
| UX-001 | Review | Inventário acima, cinco larguras nos módulos transacionais e nove seções do admin. |
| UX-002 | Doing | Baseline de regressão preservado, top 10 e instrumentação local. Não havia baseline histórico de conversão ou Web Vitals de todas as rotas; não foi reconstruído artificialmente. |
| UX-101 | Review | Tokens de cor/espaço/tipo/raio/sombra/camada/movimento, sans funcional, serif local; seis pares de contraste e zoom/refluxo testados. |
| UX-102 | Review | Botões/campos/cards/preço/status/stepper/avisos/skeleton/vazio/dialog/bottom sheet compartilhados. Erro dentro do modal, loading e retorno de foco. |
| UX-201 | Review | Compra na entrada, busca sem acentos, categorias, preço e ação; horários/status da loja aguardam contrato real. |
| UX-202 | Review | Detalhe acessível, quantidade e observação suportadas pela API. Nenhum complemento fictício. |
| UX-203 | Review | Barra mobile, edição, desfazer, refresh/login e catálogo reconciliado. Carrinho inválido em storage não quebra a tela. |
| UX-301 | Review | Etapa ativa, voltar/editar, login contextual e rascunhos. Sessão expirada mantém carrinho e oferece acesso. |
| UX-302 | Doing | Endereço salvo/novo, CEP, seleção correta, rascunho e cotação/retry implementados. Área/prazo/fora de cobertura dependem de API. |
| UX-303 | Doing | Cupom local, revisão, Pix, estados e guarda de envio implementados/testados. Falta contrato de nova tentativa de pagamento no mesmo pedido e idempotência de criação no servidor. |
| UX-304 | Doing | ID e consulta persistentes, atualização manual/automática e falha sem incentivar duplicação. Previsão e rastreio externo dependem de API/Machine. |
| UX-401 | Review | Pedido ativo, pontos e benefícios humanizados; configurações recolhidas. Dados indisponíveis não viram saldo zero. Aceite de identificação em 5 s requer usuários. |
| UX-402 | Review | Histórico em cards, detalhe e recompra explicitamente confirmada com preços/disponibilidade atuais. |
| UX-501 | Review | Fila ativa antes de concluídos, mais antigos primeiro, filtros/busca, seleção persistente, detalhe mobile. Tempo operacional de 15 s requer usuários. |
| UX-502 | Review | Cliente/itens/pagamento/entrega agrupados; preparo bloqueado antes de pagamento, confirmação de ações relevantes e papéis preservados. |
| UX-503 | Review | Consulta separada da edição, busca persistente, dialogs e prévia de imagem; campos preservados em erro e catálogo paginado. |
| UX-601 | Review | Quatro fotos reais em WebP local, srcset, dimensões/fallback e fontes locais. Metas sintéticas mobile atendidas na máquina local. |
| UX-602 | Review | Shell visual único, rotas diretas, compatibilidade de hashes, sem iframes; sessão/carrinho e navegação de retorno testados. |
| UX-603 | Review | Português, cinco larguras, teclado, foco, reduced-motion, zoom e regressão automatizada. Homologação humana descrita abaixo. |

## Evidências e reprodução

Baseline anterior: **146 testes passavam**. As capturas anteriores do fluxo crítico
foram preservadas em `test-results/ux-baseline/` antes das alterações visuais.
Não há capturas antigas de cada rota/estado, nem métricas de produção suficientes
para afirmar aumento de conversão.

Validação final: **179 testes passaram**, incluindo **36 E2E**. Os 168 avisos de
depreciação são das dependências Python/Starlette/pytest-asyncio existentes.
Nenhum erro de JavaScript ou overflow horizontal nos cenários de layout cobertos.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings
.\.venv\Scripts\python.exe scripts/verify_ui_preview.py
git diff --check
```

- `test-results/ui-premium/`: 70 screenshots de layout e seções do admin, conta autenticada e JSONs de Web Vitals.
- `test-results/ui-premium/real-preview/`: cinco capturas com os 80 produtos reais e `metrics.json`.
- `test-results/e2e/critical-flow-{mobile,desktop}.png`: compra/login/admin/conta com fixtures.
- `test-results/ui-premium/token-contrast.json`: texto 14,30:1; secundário 5,68:1; CTA 14,21:1; erro 8,09:1; sucesso 8,21:1; acento textual 5,29:1.

Contraste acima cobre os pares explícitos de tokens, não certifica toda a aplicação
WCAG AA. Zoom foi exercitado por escala CSS de 200% em Chromium; também falta
homologar o zoom nativo dos navegadores e tecnologias assistivas reais.

### Performance

O script abre contexto novo por largura em Chromium, CPU 4× mais lenta,
download de 1,6 Mbps, upload de 750 Kbps e latência de 150 ms. Aguarda o catálogo
real e registra LCP/CLS; não envia mutações. Os valores exatos da última rodada
estão em `real-preview/metrics.json`. Na última rodada, com o aviso de prévia:

| Largura | LCP | CLS |
| --- | --- | --- |
| 360 | 0,960 s | 0 |
| 390 | 0,936 s | 0 |
| 430 | 0,956 s | 0 |
| 768 | 1,628 s | 0 |
| 1440 | 0,948 s | 0 |

É medição sintética local, não p75 de usuários nem garantia de performance em
produção. O observador de CLS soma deslocamentos sem interação durante a sessão
de teste; não é um coletor RUM completo com janelas de sessão.

### Funil e privacidade

Os dez eventos mínimos do roadmap foram ligados às ações correspondentes.
`lugano:analytics` emite eventos no navegador; `lugano.ux.events` guarda no máximo
100 registros locais com nome e horário, sem IDs, email, endereço ou dados de pagamento.
Não foi conectado um serviço externo de analytics.

Não é possível comprovar +20% de conclusão, -20% de abandono, -30% de erros ou
90% de tarefas sem ajuda apenas com E2E. Essas metas exigem baseline real, consentimento/
instrumentação apropriados e estudo comparativo.

## Dependências e limites explícitos

1. `OrderQuoteOut` entrega apenas valores em centavos e limiar de frete grátis.
   Não contém CEP/área atendida, horário da loja, ETA ou previsão.
2. `OrderOut` não expõe previsão nem URL de rastreio da entrega. O roadmap técnico
   registra P0-006 Machine como bloqueado por 403; credenciais/permissões não foram alteradas.
3. Não existe endpoint de renovar/repetir pagamento no mesmo pedido. Pix expirado,
   recusado, pago ou reembolsado não apresenta código/CTA para novo pagamento.
   A interface orienta contato com a loja, sem gerar outro pedido.
4. A trava de envio é persistida antes do POST e mantida em timeout/5xx/resposta
   incompleta. Isso reduz duplicação no navegador, mas não substitui idempotência
   transacional da API entre dispositivos/abas.
5. Fidelidade não oferece o próximo nível completo para calcular progresso com precisão.
   Nenhuma barra de progresso fictícia foi mantida.
6. Listas administrativas carregam páginas de 100, limitadas a 2.000 registros com
   aviso explícito. Auditoria mantém filtros/paginação já oferecidos pelo backend.
7. O catálogo tem apenas quatro URLs de fotos distintas; demais produtos usam marca
   neutra. As imagens não foram inventadas nem ampliadas artificialmente.
8. Safari/iPhone físico, TalkBack/VoiceOver/NVDA, zoom nativo, teste de usabilidade
   e uma compra controlada em staging ainda precisam de homologação.
9. O bloqueio de gravações é específico da prévia visual local. Não é controle de
   autorização do servidor; autenticação, permissões, cálculo e integrações reais
   continuam sob responsabilidade do backend existente.

## Arquivos de implementação

- `frontend/premium.css`, `frontend/ui.js`, `frontend/design-system.css`.
- `frontend/{orders,auth,customer,admin}/{index.html,app.js}`.
- `frontend/{client,app}/{index.html,app.js}`, `frontend/index.html`,
  `frontend/_redirects`, `frontend/vercel.json`.
- `frontend/assets/catalog/`, fontes e `SourceSerif4-OFL.txt`.
- `scripts/preview_ui.py`, `scripts/verify_ui_preview.py`,
  `scripts/cache_catalog_media.py`, dependência de desenvolvimento Pillow.
- `tests/e2e/test_premium_ui.py`, adaptações do fluxo crítico e coleta de pageerror.

Source Serif 4 conserva a licença SIL OFL 1.1 em assets. As fotos são derivadas
das URLs de imagem já publicadas no catálogo Lugano; a marca existente foi preservada.

As skills de verificação orientaram a checagem navegador/API/dados. Como o CLI
agent-browser não estava disponível, foi usado o Playwright do projeto. A automação
do navegador pessoal foi interrompida por limitação de identificação de URL;
nenhuma entrada foi forçada nesse navegador. A verificação visual usou Chromium isolado.

O usuário autorizou o commit da entrega de UI/UX. Isso não encerra os aceites
externos pendentes: nenhuma task foi marcada `Done` nem publicada. Push, merge
e deploy continuam dependendo de autorização específica.
