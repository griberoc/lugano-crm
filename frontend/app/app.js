// Compatibility for bookmarks from the retired iframe shell.
const routes={inicio:"orders",pedidos:"orders",delivery:"orders",acesso:"auth",cliente:"customer",painel:"customer"};
const route=location.hash.replace(/^#\/?/,"").split("?")[0];
location.replace("../"+(routes[route] || "orders")+"/");
