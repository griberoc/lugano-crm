const routes = {
  inicio: {
    title: "Cliente",
    frame: null,
  },
  acesso: {
    title: "Acesso",
    frame: "../auth/index.html?v=auth-route-20260703-1",
  },
  delivery: {
    title: "Delivery",
    frame: "../orders/index.html?v=checkout-20260703-2",
  },
  painel: {
    title: "Painel",
    frame: "../customer/index.html?v=profile-20260703-1",
  },
};

const homeView = document.querySelector("#home-view");
const moduleView = document.querySelector("#module-view");
const moduleFrame = document.querySelector("#module-frame");
const routeLinks = [...document.querySelectorAll("[data-route-link]")];

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
