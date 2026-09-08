# Roadmap UI/UX Premium — Lugano CRM

> Execução integrada em 08/09/2026: [resultado por task, testes e pendências](UI_UX_PREMIUM_EXECUCAO.md).
> Prévia local disponível; commit autorizado, sem push/deploy. UX-002, UX-302,
> UX-303 e UX-304 têm aceites externos pendentes, detalhados no relatório.

Passo a passo para transformar os portais reais da Lugano em uma experiência
mobile-first, clara, confiável e profissional. A prioridade é vender e operar
bem; não criar uma landing page decorativa.

## Como executar

1. Trabalhe a partir da branch `develop`.
2. Escolha a primeira task `Ready` com dependências concluídas.
3. Abra uma conversa Codex separada e use o prompt-base deste documento.
4. Crie uma branch: `feature/<ID>-<nome-curto>`.
5. Implemente somente a task escolhida.
6. Teste primeiro em 390 px; depois em 360, 430, 768 e 1440 px.
7. Valide loading, vazio, erro, sucesso, offline e permissões aplicáveis.
8. Rode testes, registre screenshots e mova a task para `Review`.
9. Faça commit, push ou deploy somente quando solicitado.

Status: `Backlog → Ready → Doing → Review → Staging → Done`.

Prioridades:

- `P0`: bloqueia compra, pagamento, confiança ou uso mobile.
- `P1`: necessário para uma experiência profissional consistente.
- `P2`: melhora retenção, eficiência ou refinamento.

## Direção do produto

- O cardápio e o pedido são a experiência principal.
- O cliente sempre entende preço, próximo passo e resultado de uma ação.
- A interface funciona com uma mão entre 360 e 430 px.
- Desktop amplia o mobile; não define sua arquitetura.
- Sofisticação vem de hierarquia, ritmo, fotografia e precisão — sem excesso de
  efeitos, gradientes, sombras ou animações.
- O admin prioriza velocidade operacional e prevenção de erros.

Preservar:

- paleta de cacau, creme e caramelo;
- `Source Serif 4` como assinatura editorial;
- checkout, conta, fidelidade e admin reais já existentes;
- foco visível, textos alternativos, segurança e testes E2E atuais.

Corrigir:

- narrativa ocupando espaço antes da compra;
- checkout longo e competitivo no mobile;
- cabeçalhos e navegação duplicados por `iframe`;
- fonte editorial usada em controles e textos funcionais;
- ausência de padrão único para loading, erro, retry e estados vazios;
- formulários competindo com pedido, pontos e recompra no painel;
- tabelas e formulários do admin comprimidos no mobile;
- textos sem acentuação ou com terminologia inconsistente.

## Experiência alvo

```text
Cliente: Cardápio → Produto → Carrinho → Entrega → Pagamento → Confirmação
                         ↘ identificação contextual ↗

Admin: Fila → Detalhe do pedido → Próxima ação segura → Confirmação
```

- Login acontece no momento necessário e preserva o carrinho.
- “Minha Lugano” prioriza pedido ativo, recompra, pontos e histórico.
- A confirmação do pedido é persistente e permite acompanhamento.
- No admin, cada pedido apresenta somente ações permitidas e sua consequência.

## Passo 1 — Conhecer e medir

Objetivo: estabelecer baseline antes de alterar a interface.

| ID | Pri. | Status | Task | Entrega e aceite |
| --- | --- | --- | --- | --- |
| `UX-001` | P0 | Ready | Inventário de telas | Mapear todas as rotas e estados em 360, 390, 768 e 1440 px. Registrar objetivo, CTA, problema e severidade. Aceite: 100% das rotas cobertas. |
| `UX-002` | P0 | Ready | Baseline de funil e acessibilidade | Medir funil, Web Vitals, teclado, foco, contraste e zoom. Aceite: baseline reproduzível e top 10 problemas priorizados. |

Ao concluir: congelar métricas e evidências que serão usadas nas comparações.

## Passo 2 — Construir a fundação visual

Objetivo: criar consistência antes de redesenhar fluxos.

| ID | Pri. | Dep. | Task | Entrega e aceite |
| --- | --- | --- | --- | --- |
| `UX-101` | P0 | UX-001 | Tokens e tipografia | Separar `Source Serif 4` editorial de uma sans funcional. Consolidar cor, espaço, tipo, raio, sombra, camada e movimento. Aceite: contraste AA e zoom de 200%. |
| `UX-102` | P0 | UX-101 | Componentes essenciais | Padronizar botões, campos, cards, preço, badges, stepper, avisos, skeleton, vazio, dialog, bottom sheet e status. Aceite: todos cobrem focus, disabled, loading, error e success. |

Regras da fundação:

- corpo e controles usam fonte sans legível; serif fica em marca e títulos;
- campos têm pelo menos 16 px e alvos de toque pelo menos 44 × 44 px;
- creme no fundo, branco quente nas superfícies, cacau no texto/CTA e caramelo
  apenas como acento;
- sucesso, alerta e erro usam texto, ícone e cor;
- movimento dura 120–220 ms e respeita `prefers-reduced-motion`.

## Passo 3 — Simplificar cardápio e carrinho

Objetivo: reduzir o tempo até o primeiro item e manter o carrinho acessível.

| ID | Pri. | Dep. | Task | Entrega e aceite |
| --- | --- | --- | --- | --- |
| `UX-201` | P0 | UX-102 | Entrada orientada à compra | Cardápio vira entrada principal, com status da loja, contexto de entrega, busca, categorias e cards claros. Aceite: produto alcançável rapidamente no mobile. |
| `UX-202` | P1 | UX-201 | Produto e personalização | Detalhe em bottom sheet no mobile e modal/painel no desktop, usando apenas opções reais da API. Aceite: foco correto e seleção preservada em falha. |
| `UX-203` | P0 | UX-201 | Carrinho persistente | Barra inferior com quantidade/total, edição imediata, desfazer e persistência após refresh/login. Aceite: item e carrinho acessíveis em até dois toques. |

Não inventar complementos, disponibilidade ou preços sem suporte do backend.

## Passo 4 — Criar checkout de alta confiança

Objetivo: concluir a compra sem perda de dados ou ambiguidade financeira.

| ID | Pri. | Dep. | Task | Entrega e aceite |
| --- | --- | --- | --- | --- |
| `UX-301` | P0 | UX-203 | Checkout sequencial | Uma etapa ativa por vez no mobile, progresso, voltar/editar e resumo compacto. Aceite: estado preservado em retorno, refresh e login. |
| `UX-302` | P0 | UX-301 | Endereço e entrega | Endereços salvos primeiro, validação progressiva, taxa, prazo e mensagens distintas para timeout/fora de área. Aceite: dados nunca somem em falha. |
| `UX-303` | P0 | UX-302 | Cupom, pagamento e revisão | Feedback local de cupom, revisão final, Pix copiável/rastreável e prevenção de envio duplicado. Aceite: estados pendente, aprovado, recusado e retry validados. |
| `UX-304` | P0 | UX-303 | Confirmação e rastreio | Tela persistente com número, status, previsão e próximos passos. Aceite: falha de consulta nunca incentiva pedido duplicado. |

Ao concluir: checkout completo em 360 px, sem scroll horizontal e com feedback
explícito em toda chamada remota.

## Passo 5 — Tornar “Minha Lugano” útil

Objetivo: priorizar acompanhamento, fidelidade e recompra.

| ID | Pri. | Dep. | Task | Entrega e aceite |
| --- | --- | --- | --- | --- |
| `UX-401` | P1 | UX-102 | Dashboard útil | Pedido ativo, recompra e pontos aparecem antes dos formulários. Benefícios da API viram linguagem humana. Aceite: ação principal e saldo identificáveis em até 5 s. |
| `UX-402` | P2 | UX-401 | Histórico e recompra | Cards de pedidos e recompra com reconciliação de preço e disponibilidade atuais. Aceite: estados vazio, completo e catálogo alterado cobertos. |

## Passo 6 — Acelerar a operação do admin

Objetivo: reduzir tempo e risco na rotina da loja.

| ID | Pri. | Dep. | Task | Entrega e aceite |
| --- | --- | --- | --- | --- |
| `UX-501` | P1 | UX-102 | Fila de pedidos | Ordenação por urgência, filtros rápidos e atualização sem perder seleção. No mobile, usar cards operacionais. Aceite: pedido novo aberto em até 15 s. |
| `UX-502` | P1 | UX-501 | Detalhe e próxima ação | Agrupar cliente, itens, pagamento e entrega; destacar uma ação permitida. Aceite: destrutivos confirmados e papéis respeitados. |
| `UX-503` | P2 | UX-102 | Catálogo, clientes e campanhas | Consulta separada da edição, validação inline, prévia e filtros persistentes. Aceite: formulários preservados em erro e versão mobile funcional. |

## Passo 7 — Fechar performance, arquitetura e qualidade

Objetivo: garantir estabilidade, acessibilidade e acabamento de produção.

| ID | Pri. | Dep. | Task | Entrega e aceite |
| --- | --- | --- | --- | --- |
| `UX-601` | P1 | UX-201 | Mídia e performance | Assets estáveis, imagens responsivas, dimensões explícitas e fallback. Aceite: LCP ≤ 2,5 s e CLS ≤ 0,1 no baseline mobile. |
| `UX-602` | P1 | UX-304, UX-401 | Navegação e arquitetura | Remover `iframes` gradualmente com shell único, começando por rota piloto. Aceite: URL, sessão, carrinho, foco, scroll e back/forward preservados. |
| `UX-603` | P0 | Release atual | Gate visual e conteúdo | Revisar português, responsividade, teclado, leitor de tela, zoom e regressão visual. Aceite: zero quebra crítica nas larguras de referência. |

`UX-603` deve ser executada ao final de toda release, não apenas uma vez.

## Estados obrigatórios

Todo bloco com dados remotos deve tratar:

| Estado | Regra |
| --- | --- |
| Loading | Skeleton proporcional ou spinner local com verbo da ação. |
| Sucesso | Confirmação próxima da ação e atualização imediata. |
| Vazio | Explicação curta e uma ação útil, quando aplicável. |
| Erro recuperável | Linguagem humana, retry e dados preservados. |
| Erro de campo | Mensagem junto ao campo e foco no primeiro erro. |
| Offline/timeout | Diferente de erro de regra de negócio. |
| Sem permissão | Explicação e saída segura; não mostrar ação proibida. |
| Destrutivo | Confirmar objeto e consequência explicitamente. |

Botões assíncronos trocam o rótulo, por exemplo: `Finalizar pedido` →
`Enviando pedido…`. Erros técnicos nunca aparecem diretamente ao cliente.

## Métricas de sucesso

| Métrica | Meta |
| --- | --- |
| Tempo até primeiro item | ≤ 30 s |
| Conclusão do checkout | +20% sobre baseline |
| Abandono carrinho → identificação | -20% sobre baseline |
| Erros de formulário | -30% sobre baseline |
| Tarefas mobile sem ajuda | ≥ 90% |
| LCP mobile 4G | ≤ 2,5 s |
| CLS | ≤ 0,1 |
| Ações com feedback em 100 ms | 100% |

Eventos mínimos: `menu_viewed`, `product_added`, `cart_opened`,
`checkout_step_viewed`, `checkout_error`, `coupon_applied`, `order_submitted`,
`payment_started`, `payment_confirmed` e `reorder_started`.

## Uso de 21st.dev e bibliotecas externas

O frontend atual é HTML/CSS/JavaScript vanilla. Use 21st.dev como referência ou
ponto de partida, não como dependência automática.

Antes de adotar um componente:

1. conferir licença, manutenção, dependências e peso;
2. validar semântica, teclado, leitor de tela e movimento reduzido;
3. adaptar aos tokens Lugano e remover efeitos excessivos;
4. implementar todos os estados obrigatórios;
5. testar em 360 px com conteúdo real em português.

Boas referências: bottom sheet, cart drawer, stepper, combobox, toast acessível,
skeleton, dialog e tabela responsiva. Evitar heroes, bentos decorativos,
carrosséis automáticos e animações que atrasem a compra.

## Prompt-base para executar qualquer task

Copie este prompt em uma nova conversa e substitua os campos entre `< >` com a
linha correspondente do passo a passo.

```text
Estamos no projeto Lugano CRM.

Repo local:
C:\Users\guilh\Documents\Codex\2026-06-17\files-mentioned-by-the-user-cafeteria\outputs\lugano-crm

Branch base: develop
Task: <ID e nome>
Prioridade: <P0, P1 ou P2>
Dependências: <IDs ou nenhuma>

Leia integralmente:
- docs/ROADMAP_UI_UX_PREMIUM.md
- docs/ROADMAP_EXECUTAVEL_LUGANO_CRM.md, somente nas dependências técnicas
- os arquivos atuais relacionados à task

Objetivo e aceite da task:
<copie a coluna “Entrega e aceite” da task>

Atue como designer de produto e engenheiro frontend sênior.
Priorize fluxo mobile-first, clareza de compra, confiança, acessibilidade,
loading, vazio, erro, sucesso e aparência premium de cafeteria/chocolateria.

Execução:
1. Inspecione o estado atual e confirme as dependências.
2. Apresente um plano curto antes de editar.
3. Implemente somente esta task no produto real.
4. Preserve regras de negócio, segurança, sessão, carrinho e integrações.
5. Não simule no frontend uma regra que dependa de API; registre a dependência.
6. Não crie landing explicativa no lugar da experiência real.
7. Se usar 21st.dev, adapte o padrão ao stack vanilla e aos tokens Lugano.
8. Não reverta mudanças que não forem suas e não exponha valores de .env.
9. Valide em 360, 390, 430, 768 e 1440 px quando aplicável.
10. Teste teclado, foco, loading, vazio, erro, sucesso e fluxo principal.
11. Rode testes focados e o conjunto completo se afetar checkout ou sessão.
12. Não faça commit, push ou deploy sem eu pedir.

Ao final, mostre:
1. resultado alcançado;
2. arquivos alterados;
3. testes e validações executados;
4. screenshots ou evidências geradas;
5. riscos e validações manuais pendentes;
6. critérios de aceite atendidos;
7. se a task pode ir para Review.
```

## Definition of Done

Uma task só pode ir para `Review` quando:

- usa tokens e componentes aprovados;
- trata os estados aplicáveis;
- funciona sem overflow em 360, 390, 430, 768 e 1440 px;
- mantém foco, teclado e retorno de modal/erro corretos;
- apresenta português revisado e nenhuma mensagem técnica ao cliente;
- possui testes e screenshots do fluxo alterado;
- não causa regressão em carrinho, login, pagamento ou permissões;
- compara a métrica correspondente quando existe baseline.

Validação padrão:

```powershell
.\.venv\Scripts\python.exe -m pytest
git diff --check
git status --short
```

## Releases

| Release | Passos | Resultado |
| --- | --- | --- |
| R1 — Clareza | 1 e 2 | Baseline e sistema visual consistente |
| R2 — Conversão | 3 e 4 | Cardápio e checkout mobile prontos para venda |
| R3 — Retenção | 5 | Conta útil, fidelidade e recompra |
| R4 — Operação | 6 | Admin rápido e seguro |
| R5 — Excelência | 7 | Performance, acessibilidade e acabamento |

Próxima ação: revisar a implementação integrada em 390 px e desktop. Conferir os
aceites pendentes no relatório de execução antes de homologar ou marcar como Done.
O commit da entrega foi autorizado. O fluxo demonstrável é cardápio → produto → carrinho →
checkout → conta, com admin operacional e modo visual local sem gravações.
