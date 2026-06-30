# Frontend admin

O painel admin fica em `frontend/admin`.

## Como rodar

Com o backend rodando em `http://127.0.0.1:8000`, abra outro terminal:

```powershell
cd frontend\admin
..\..\.venv\Scripts\python.exe -m http.server 5173
```

Depois acesse:

```text
http://localhost:5173
```

## Conexao

No painel, abra a aba `Conexao` e preencha:

- `API base URL`: `http://127.0.0.1:8000`
- `Admin key`: o mesmo valor de `ADMIN_API_KEY` no `.env`

Depois de alterar o `.env`, reinicie o backend:

```powershell
Ctrl+C
uvicorn app.main:app --reload
```

Clique em `Salvar` e depois em `Testar conexao`.

O teste de conexao valida `/health` e tambem `/api/v1/admin/products`.
Se a chave admin estiver errada, o painel deve mostrar erro de permissao.

## Modulos

- Visao Geral
- Pedidos
- Produtos
- Clientes
- Campanhas
- Conexao
