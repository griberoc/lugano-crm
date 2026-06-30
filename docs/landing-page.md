# Landing page

A landing page da Lugano fica em `frontend/landing`.

## Como rodar

```powershell
cd frontend\landing
..\..\.venv\Scripts\python.exe -m http.server 5172
```

Depois acesse:

```text
http://localhost:5172
```

Ela aponta para:

- `../customer/index.html` para o delivery do cliente;
- `../admin/index.html` para acesso administrativo no rodape.
