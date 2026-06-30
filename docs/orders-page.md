# Pagina de pedidos

A pagina dedicada de pedidos fica em `frontend/orders`.

## Como rodar

```powershell
cd frontend\orders
..\..\.venv\Scripts\python.exe -m http.server 5175
```

Depois acesse:

```text
http://localhost:5175
```

## Observacao

Reinicie o backend depois de atualizar o `.env`, porque a pagina usa a origem
`http://localhost:5175` no CORS.

```powershell
uvicorn app.main:app --reload
```
