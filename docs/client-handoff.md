# Handoff para o cliente

Use este documento no dia da entrega assistida. Preencha os campos finais fora
do Git, em um canal seguro ou documento compartilhado com o cliente.

## URLs de producao

```text
Landing / portal: https://app.seu-dominio.com/landing/
Portal do cliente: https://app.seu-dominio.com/client/
Delivery: https://app.seu-dominio.com/orders/
Admin: https://app.seu-dominio.com/admin/
Healthcheck API: https://api.seu-dominio.com/health
```

## Acessos

Entregar credenciais por canal seguro.

```text
Admin owner:
Email:
Senha:

Conta cliente teste:
Email:
Senha:
```

Nao enviar `SUPABASE_SERVICE_ROLE_KEY`, `SECRET_KEY`, tokens de webhook ou
senhas de banco ao cliente por email aberto.

## Demonstracao guiada

1. Abrir landing page.
2. Criar ou acessar conta cliente.
3. Editar perfil do cliente.
4. Cadastrar endereco.
5. Adicionar produto ao carrinho.
6. Aplicar cupom, se houver.
7. Confirmar pedido.
8. Gerar Pix.
9. Abrir admin.
10. Localizar pedido.
11. Alterar status.
12. Confirmar que o cliente acompanha historico/fidelidade.

## Operacao do dia a dia

- Produtos, clientes, pedidos e campanhas ficam no portal admin.
- Pedidos devem ser acompanhados pelo status no admin.
- Pagamento Pix da primeira entrega e manual: a equipe precisa conferir o
  recebimento antes de confirmar preparo/entrega.
- Campanhas e cupons devem ser revisados antes de publicar.

## Limitacoes da primeira entrega

- Pix estatico/manual, sem conciliacao automatica.
- Email/WhatsApp dependem de webhooks externos se forem ativados.
- Monitoramento depende do webhook ou ferramenta externa definida.
- Backups dependem da rotina em `docs/backup-retention.md`.

## Checklist de aceite do cliente

- Cliente consegue abrir portal.
- Cliente consegue criar/login de conta.
- Cliente consegue fazer pedido.
- Admin consegue ver pedido.
- Admin consegue alterar status.
- Produtos aparecem corretamente.
- Promocoes aparecem corretamente.
- Fidelidade aparece no painel cliente.
- Dados sensiveis nao aparecem para usuario comum.

## Suporte pos-entrega

Registrar qualquer chamado com:

- URL acessada.
- Horario aproximado.
- Email do usuario afetado.
- Print da tela, se possivel.
- `X-Request-ID`, quando o erro vier da API.

