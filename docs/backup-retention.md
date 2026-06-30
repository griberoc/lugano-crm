# Backups e retencao

Este guia define a estrategia de backup e retencao do Lugano CRM.

## Objetivos

- Recuperar o banco em caso de erro operacional, bug ou exclusao acidental.
- Manter uma copia off-site exportavel das tabelas publicas principais.
- Reduzir crescimento de `audit_logs` e `notification_events`.
- Preservar pedidos antigos sem apagamento automatico.

## Backups Supabase

Segundo a documentacao oficial do Supabase, projetos Pro, Team e Enterprise
tem backups diarios automaticos acessiveis em Database > Backups. O periodo
disponivel depende do plano: Pro ate 7 dias, Team ate 14 dias e Enterprise ate
30 dias. Para restauracao com granularidade menor, o Supabase oferece
Point-in-Time Recovery como add-on em planos pagos.

Projetos Free devem exportar dados regularmente com `supabase db dump` ou outro
processo off-site.

Referencias:

- https://supabase.com/docs/guides/platform/backups
- https://supabase.com/docs/reference/cli/supabase-db-dump

## Politica recomendada

### Producao

- Plano Supabase: Pro ou superior.
- Backup nativo: diario automatico.
- PITR: recomendado quando o volume de pedidos reais aumentar.
- Backup off-site: pelo menos 1 vez por dia.
- Teste de restore: mensal em projeto Supabase separado.

### Staging

- Backup nativo: opcional.
- Backup off-site: antes de testar migrations destrutivas.
- Restore: pode ser testado com dados sintéticos.

## Backup logico off-site

Use:

```powershell
.\.venv\Scripts\python.exe scripts\backup_supabase.py --env-file .env.production
```

Por padrao, o backup e salvo em:

```text
backups/supabase-YYYYMMDDTHHMMSSZ/
```

A pasta `backups/` esta no `.gitignore`.

O backup inclui:

```text
profiles
addresses
products
orders
order_items
loyalty_tiers
loyalty_accounts
loyalty_transactions
promotions
promotion_usages
notification_events
audit_logs
admin_users
operational_settings
data_retention_policies
```

Para exportar apenas algumas tabelas:

```powershell
.\.venv\Scripts\python.exe scripts\backup_supabase.py --env-file .env.production --tables products,promotions,orders,order_items
```

## Retencao no banco

A migration `010_data_retention.sql` cria:

- `data_retention_policies`;
- coluna `orders.archived_at`;
- funcao `data_retention_preview()`;
- funcao `apply_data_retention(policy_key, dry_run)`.

Politicas iniciais:

| Tabela | Retencao | Acao |
| --- | ---: | --- |
| `audit_logs` | 730 dias | delete |
| `notification_events` | 180 dias | delete |
| `orders` | 1825 dias | archive |

Pedidos antigos nao sao apagados; recebem `archived_at`.

## Preview de retencao

Antes de aplicar qualquer retencao:

```sql
select * from public.data_retention_preview();
```

Ou:

```sql
select * from public.apply_data_retention(null, true);
```

## Aplicar retencao

Sempre rode backup antes.

Aplicar somente notificacoes:

```sql
select * from public.apply_data_retention('notification_events', false);
```

Aplicar auditoria:

```sql
select * from public.apply_data_retention('audit_logs', false);
```

Arquivar pedidos antigos:

```sql
select * from public.apply_data_retention('orders', false);
```

Aplicar todas as politicas:

```sql
select * from public.apply_data_retention(null, false);
```

As funcoes nao sao concedidas para `anon` nem `authenticated`; execute pelo SQL
Editor ou por uma conexao administrativa.

## Restore

### Restore completo

Use Database > Backups no Supabase ou PITR, se habilitado.

Importante:

- planeje janela de indisponibilidade;
- valide em um projeto novo quando possivel;
- Storage API nao e restaurado junto com objetos apagados, apenas metadados do
  banco podem constar no backup.

### Restore parcial

Use os JSONs gerados por `scripts/backup_supabase.py` como referencia para
recriar registros pontuais via SQL ou script administrativo.

Nao restaure parcialmente em producao sem antes testar em staging.

## Rotina operacional

Semanal:

- Verificar se backups Supabase estao visiveis no dashboard.
- Rodar backup off-site.
- Guardar copia em armazenamento externo seguro.

Mensal:

- Testar restore em projeto separado.
- Rodar `data_retention_preview()`.
- Aplicar retencao somente apos backup recente.

Antes de deploy com migration:

- Rodar backup off-site.
- Confirmar que staging passou no checklist de pre-deploy.
- Aplicar migration em producao.
