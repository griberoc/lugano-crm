# Cardápio São Luís 2026

Fonte: https://docs.google.com/presentation/d/1aPPqLHiuP25wFoteToWcxSQZZOkaOaSVayoh8P6MHKE

Leitura visual das 27 páginas em 08/09/2026. O CSV registra a página de origem de cada item.
121 produtos e adicionais em 16 categorias. Capas e fotografias repetidas não geram produtos.
Os dois fondues para compartilhar recebem os sufixos chocolate e queijo para distinguir as receitas.
Morango e sorvete têm preços diferentes nas páginas 17 e 19; os adicionais indicam seu contexto.
Itens descritos como “consulte opções” mantêm essa orientação. Não foram inventados sabores nem fotos.
As bebidas alcoólicas (incluindo chocolate com licor) não foram cadastradas para venda.
“Sabores especiais da casa” da página de pizzas não tem preço nem opções definidos e não gera SKU.

## Resultado da importação em produção

- 121 produtos ativos, com nomes, categorias e preços comparados ao CSV após a gravação.
- 7 produtos antigos com referências em pedidos preservados com `available=false`.
- 77 produtos sem referências excluídos. Pedidos e itens de pedidos não foram alterados.
- Backup local ignorado pelo Git: `backups/menu-20260908T201013786461Z/before.json`.
- O journal na mesma pasta registra as fases e cada ID excluído.

## Operação do script

`scripts/replace_menu.py` executa somente leitura por padrão. Exige arquivo de ambiente explícito
e valida o hostname contra `--project-ref`. `--apply` prepara os novos itens indisponíveis,
retira os antigos, publica os novos e só então exclui os antigos sem referências.
Não é uma transação única. Falhas interrompem a execução e exigem examinar o journal.
IDs determinísticos impedem reaplicação inadvertida sobre os itens importados.
A chave de serviço não aparece no log nem no CSV.

Antes de uma recuperação, compare o backup com o estado atual e os pedidos criados desde a importação.
Restaure somente os produtos necessários pelos IDs originais; nunca restaure ou apague pedidos para
reverter um cardápio. O backup contém os registros antigos completos e os IDs da importação.
Restaurar o frontend na Vercel não reverte o catálogo do banco.

## Edição rápida no admin

Gestores e proprietários editam o preço na lista de produtos e confirmam em Salvar.
O formulário aceita vírgula ou ponto decimal, exige valor positivo e até duas casas decimais.
Envia exclusivamente `price` ao PATCH autenticado existente, preservando os demais campos e a auditoria.
Tem estado de salvamento, proteção contra envio duplicado e mensagens locais de erro/sucesso.
Uma falha mantém o valor digitado para nova tentativa.

Verificação: 196 testes passaram, incluindo validação, falha/repetição e layout a 390 e 1440 px.
P0-006 e as demais alterações locais anteriores não fazem parte deste commit.
