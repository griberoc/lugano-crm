# Frontend cliente

O painel do cliente fica em `frontend/customer`.

## Como rodar

Com o backend rodando em `http://127.0.0.1:8000`, abra outro terminal:

```powershell
cd frontend\customer
..\..\.venv\Scripts\python.exe -m http.server 5174
```

Depois acesse:

```text
http://localhost:5174
```

## Conexao

No painel, preencha:

- `API base URL`: `http://127.0.0.1:8000`
- `Supabase URL`: URL do projeto Supabase
- `Supabase anon key`: chave anon public do Supabase

Crie um usuario em `Authentication > Users` no Supabase e use email/senha
para entrar no painel.

## Fluxos disponiveis

- Login com Supabase Auth.
- Listagem de produtos disponiveis.
- Carrinho.
- Cadastro de endereco.
- Aplicacao de cupom.
- Criacao de pedido.
- Consulta de pedidos.
- Resumo de fidelidade.
