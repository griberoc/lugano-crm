# P0-003 - XSS, CSP e headers

Prioridade: P0
Epic: SEC/UX
Status: Done
Branch sugerida: `feature/P0-003-xss-csp`

## Objetivo

Reduzir risco de XSS e endurecer headers de seguranca no frontend e backend.

## Escopo

- `frontend/admin/app.js`
- `frontend/orders/app.js`
- `frontend/customer/app.js`
- `frontend/_headers`
- `app/core/security_headers.py`

## Checklist

- [x] Criar helper seguro para escapar texto dinamico.
- [x] Substituir `innerHTML` inseguro em dados vindos da API.
- [x] Adicionar CSP no frontend estatico.
- [x] Adicionar CSP/HSTS no backend quando aplicavel.
- [x] Garantir que QR Code Mercado Pago continua funcionando.
- [x] Validar landing, delivery, cliente e admin.

## Criterios de aceite

- [x] Dados de produto/cliente/endereco/cupom nao injetam HTML.
- [x] Headers de seguranca aparecem no deploy.
- [x] Fluxos visuais continuam funcionando.

## Validacao

```powershell
rg -n "innerHTML" frontend
.\.venv\Scripts\python.exe -m pytest
```
