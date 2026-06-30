# Testing real endpoints

Use este roteiro para testar a API local conectada ao Supabase real.

## 1. Deixe a API rodando

Em um terminal:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

## 2. Crie um usuario no Supabase

No painel do Supabase:

1. Va em `Authentication`.
2. Crie um usuario de teste.
3. Gere ou copie um access token desse usuario.

Uma forma pratica e fazer login pelo proprio Supabase Auth usando uma ferramenta como Postman/Insomnia, ou temporariamente usar a aba de docs da API quando ja houver um frontend.

## 3. Rode o smoke test

Em outro terminal, com a API ainda rodando:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\smoke_test_api.py --token "COLE_O_ACCESS_TOKEN_AQUI"
```

O script:

- valida o token no Supabase;
- cria perfil, conta de fidelidade e endereco de teste se faltarem;
- pega um produto real do banco;
- chama `/health`;
- chama `/api/v1/loyalty/`;
- valida o cupom `LUGANO10`;
- cria um pedido real;
- consulta o pedido;
- lista pedidos;
- cancela o pedido.

Se terminar com `Smoke test finished successfully.`, API, Supabase e RLS estao conversando corretamente.
