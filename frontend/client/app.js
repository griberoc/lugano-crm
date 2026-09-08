// Compatibility routes now open documents sharing one navigation; no iframes.
(() => { const route = location.hash.replace("#/", "") || "delivery"; const destinations = { inicio: "../orders/", delivery: "../orders/", acesso: "../auth/", painel: "../customer/" }; location.replace(destinations[route] || destinations.delivery); })();
