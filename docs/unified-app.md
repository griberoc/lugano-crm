# App unificado

O app unificado fica em `frontend/app` e agrupa os módulos existentes em uma
entrada principal.

## Como rodar

Sirva a pasta `frontend` para que o app consiga carregar os módulos irmãos:

```powershell
cd frontend
..\.venv\Scripts\python.exe -m http.server 5176
```

Depois acesse:

```text
http://localhost:5176/app/
```

## Rotas

- `#/inicio`
- `#/pedidos`
- `#/cliente`
- `#/admin`

Depois de adicionar `http://localhost:5176` ao `ALLOWED_ORIGINS`, reinicie o
backend.
