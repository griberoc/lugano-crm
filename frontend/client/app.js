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
    frame: "../orders/index.html?v=checkout-20260805-1",
  },
  painel: {
    title: "Painel",
    frame: "../customer/index.html?v=profile-20260703-2",
  },
};

const RETURN_AFTER_LOGIN_KEY = "lugano.customer.returnAfterLogin";

const homeView = document.querySelector("#home-view");
const moduleView = document.querySelector("#module-view");
const moduleFrame = document.querySelector("#module-frame");
const portalHeader = document.querySelector(".portal-header");
const menuToggle = document.querySelector("#client-menu-toggle");
const routeLinks = [...document.querySelectorAll("[data-route-link]")];
const guestOnlyElements = [...document.querySelectorAll("[data-guest-only]")];

function customerSession() {
  try {
    return JSON.parse(localStorage.getItem("lugano.customer.session") || "null");
  } catch {
    return null;
  }
}

function isCustomerLoggedIn() {
  return Boolean(customerSession()?.access_token);
}

function consumeReturnAfterLogin() {
  const route = localStorage.getItem(RETURN_AFTER_LOGIN_KEY);
  localStorage.removeItem(RETURN_AFTER_LOGIN_KEY);
  return route && routes[route] && route !== "acesso" ? route : "painel";
}

function currentRoute() {
  const route = window.location.hash.replace("#/", "") || "inicio";
  return routes[route] ? route : "inicio";
}

function setActiveLink(route) {
  routeLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.routeLink === route);
  });
}

function closeMenu() {
  portalHeader?.classList.remove("nav-open");
  menuToggle?.setAttribute("aria-expanded", "false");
}

function renderAuthVisibility() {
  const loggedIn = isCustomerLoggedIn();
  guestOnlyElements.forEach((element) => {
    element.classList.toggle("hidden", loggedIn);
    element.setAttribute("aria-hidden", String(loggedIn));
  });
}

function renderRoute() {
  const route = currentRoute();
  if (route === "acesso" && isCustomerLoggedIn()) {
    window.location.hash = `#/${consumeReturnAfterLogin()}`;
    return;
  }

  const config = routes[route];
  document.title = `Lugano | ${config.title}`;
  renderAuthVisibility();
  setActiveLink(route);
  closeMenu();

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

menuToggle?.addEventListener("click", () => {
  const isOpen = portalHeader.classList.toggle("nav-open");
  menuToggle.setAttribute("aria-expanded", String(isOpen));
});

routeLinks.forEach((link) => {
  link.addEventListener("click", closeMenu);
});

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeMenu();
});

window.addEventListener("storage", (event) => {
  if (event.key === "lugano.customer.session") renderRoute();
});

window.addEventListener("message", (event) => {
  if (event.origin !== window.location.origin) return;
  if (event.data?.type === "lugano.customer.session.changed") renderRoute();
});

window.addEventListener("hashchange", renderRoute);
renderRoute();
