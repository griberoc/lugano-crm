const routes = {
  inicio: {
    title: "Início",
    description: "Entrada principal do sistema Lugano.",
    frame: null,
  },
  acesso: {
    title: "Acesso",
    description: "Login e criacao de conta do cliente.",
    frame: "../auth/index.html?v=auth-route-20260620-1",
  },
  pedidos: {
    title: "Delivery",
    description: "Cardapio, carrinho, entrega e pagamento do delivery.",
    frame: "../orders/index.html?v=session-20260620-1",
  },
  cliente: {
    title: "Painel do Cliente",
    description: "Fidelidade, ultimos pedidos, promocoes e dados da conta.",
    frame: "../customer/index.html?v=session-20260620-1",
  },
};

const homeView = document.querySelector("#home-view");
const moduleView = document.querySelector("#module-view");
const moduleFrame = document.querySelector("#module-frame");
const routeLinks = [...document.querySelectorAll("[data-route-link]")];

document.querySelector(".module-bar")?.remove();

function currentRoute() {
  const route = window.location.hash.replace("#/", "") || "inicio";
  return routes[route] ? route : "inicio";
}

function setActiveLink(route) {
  routeLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.routeLink === route);
  });
}

function renderRoute() {
  const route = currentRoute();
  const config = routes[route];
  document.title = `Lugano | ${config.title}`;
  setActiveLink(route);

  if (!config.frame) {
    homeView.classList.remove("hidden");
    moduleView.classList.add("hidden");
    moduleFrame.removeAttribute("src");
    return;
  }

  homeView.classList.add("hidden");
  moduleView.classList.remove("hidden");
  moduleFrame.src = config.frame;
}

window.addEventListener("hashchange", renderRoute);
renderRoute();
