const runtimeConfig = window.LUGANO_CONFIG || {};
const DEFAULT_API_URL = runtimeConfig.apiBaseUrl || "http://127.0.0.1:8000";
const DEFAULT_SUPABASE_URL = runtimeConfig.supabaseUrl || "";
const DEFAULT_SUPABASE_ANON_KEY = runtimeConfig.supabaseAnonKey || "";

function clearLegacyTechnicalConfig() {
  localStorage.removeItem("lugano.customer.apiBaseUrl");
  localStorage.removeItem("lugano.customer.supabaseUrl");
  localStorage.removeItem("lugano.customer.supabaseAnonKey");
}

clearLegacyTechnicalConfig();

const state = {
  apiBaseUrl: DEFAULT_API_URL,
  supabaseUrl: DEFAULT_SUPABASE_URL,
  supabaseAnonKey: DEFAULT_SUPABASE_ANON_KEY,
  session: JSON.parse(localStorage.getItem("lugano.customer.session") || "null"),
  profile: null,
  loyalty: null,
  orders: [],
  promotions: [],
  transactions: [],
  addresses: [],
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function defaultPreferences() {
  return {
    preferred_contact: null,
    favorite_categories: [],
    dietary_restrictions: [],
    accepts_promotions: true,
    accepts_whatsapp: true,
    notes: null,
  };
}

function profilePreferences() {
  return {
    ...defaultPreferences(),
    ...(state.profile?.preferences || {}),
  };
}

function money(value) {
  return Number(value || 0).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function dateLabel(value) {
  if (!value) return "";
  return new Date(value).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function showNotice(message, type = "info") {
  const notice = $("#notice");
  notice.textContent = message;
  notice.classList.remove("hidden", "error", "success");
  if (type === "error") notice.classList.add("error");
  if (type === "success") notice.classList.add("success");
}

function authHeaders() {
  return state.session?.access_token
    ? { Authorization: `Bearer ${state.session.access_token}` }
    : {};
}

async function api(path, options = {}) {
  const response = await fetch(`${state.apiBaseUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail);
  }

  if (response.status === 204) return null;
  return response.json();
}

function formData(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  Object.keys(data).forEach((key) => {
    if (data[key] === "") data[key] = null;
  });
  return data;
}

function saveSession() {
  localStorage.setItem("lugano.customer.session", JSON.stringify(state.session));
}

function notifySessionChanged() {
  if (window.parent && window.parent !== window) {
    window.parent.postMessage({ type: "lugano.customer.session.changed" }, window.location.origin);
  }
}

function splitList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function renderSession() {
  const email = state.session?.user?.email || state.profile?.email;
  const firstName = state.profile?.full_name?.split(" ")[0];
  $("#account-access-panel")?.classList.toggle("hidden", Boolean(state.session));
  $("#session-label").textContent = email || "Visitante";
  $("#logout-button").classList.toggle("hidden", !state.session);
  $("#auth-summary").textContent = email
    ? `Conta conectada: ${email}`
    : "Entre pela rota Acesso para carregar seu painel.";
  $("#customer-greeting").textContent = firstName
    ? `Ola, ${firstName}.`
    : "Seu clube de beneficios.";
  $("#customer-summary").textContent = email
    ? "Acompanhe seus pontos, pedidos recentes e promocoes."
    : "Entre para ver seus pontos, nivel, pedidos e promocoes.";
}

function renderProfile() {
  const form = $("#profile-form");
  form.elements.full_name.value = state.profile?.full_name || "";
  form.elements.phone.value = state.profile?.phone || "";
  form.elements.birth_date.value = state.profile?.birth_date || "";
}

function addressLine(address) {
  const complement = address.complement ? `, ${address.complement}` : "";
  return `${address.street}, ${address.number}${complement} - ${address.neighborhood}, ${address.city}`;
}

function renderAddresses() {
  const list = $("#addresses-list");

  if (!state.session) {
    list.innerHTML = '<p class="muted">Entre para ver seus enderecos salvos.</p>';
    return;
  }

  list.innerHTML = state.addresses.length
    ? state.addresses
        .map(
          (address) => `
            <article class="address-card ${address.is_default ? "selected-address" : ""}">
              <div>
                <strong>${address.label}</strong>
                <span>${addressLine(address)}</span>
                <span>CEP ${address.zip_code}</span>
              </div>
              <div class="address-actions">
                ${address.is_default ? '<span class="mini-badge">Principal</span>' : ""}
                <button class="ghost-button" data-edit-address="${address.id}" type="button">Editar</button>
                <button class="ghost-button" data-default-address="${address.id}" type="button">Padrao</button>
                <button class="ghost-button danger-button" data-delete-address="${address.id}" type="button">Remover</button>
              </div>
            </article>
          `,
        )
        .join("")
    : '<p class="muted">Nenhum endereco cadastrado ainda.</p>';
}

function renderPreferences() {
  const preferences = profilePreferences();
  const favoriteCategories = Array.isArray(preferences.favorite_categories)
    ? preferences.favorite_categories
    : [];
  const dietaryRestrictions = Array.isArray(preferences.dietary_restrictions)
    ? preferences.dietary_restrictions
    : [];
  const form = $("#preferences-form");
  form.elements.preferred_contact.value = preferences.preferred_contact || "";
  form.elements.dietary_restrictions.value = dietaryRestrictions.join(", ");
  form.elements.accepts_promotions.checked = preferences.accepts_promotions;
  form.elements.accepts_whatsapp.checked = preferences.accepts_whatsapp;
  form.elements.notes.value = preferences.notes || "";
  $$('input[name="favorite_categories"]').forEach((input) => {
    input.checked = favoriteCategories.includes(input.value);
  });
}

function renderLoyalty() {
  const loyalty = state.loyalty;
  const tier = loyalty?.tier;
  $("#loyalty-available").textContent = loyalty?.available_points ?? 0;
  $("#loyalty-total").textContent = loyalty?.total_points ?? 0;
  $("#loyalty-tier").textContent = tier?.name || "--";
  $("#tier-badge").textContent = tier?.name || "Visitante";
  $("#loyalty-cashback").textContent = tier ? `${Number(tier.cashback_rate)}%` : "0%";

  if (!loyalty || !tier) {
    $("#loyalty-headline").textContent = "Entre para ativar sua conta Lugano.";
    $("#loyalty-progress-bar").style.width = "0%";
    $("#loyalty-progress-label").textContent = "Entre para ver seu progresso.";
    $("#loyalty-benefits").innerHTML = '<p class="muted">Os beneficios aparecem apos o login.</p>';
    return;
  }

  $("#loyalty-headline").textContent =
    `${loyalty.available_points} pontos disponiveis no nivel ${tier.name}.`;
  $("#loyalty-progress-bar").style.width = "100%";
  $("#loyalty-progress-label").textContent =
    `${loyalty.total_points} pontos acumulados. Nivel ${tier.name} conquistado a partir de ${tier.min_points} pontos.`;

  const benefits = tier.benefits || {};
  $("#loyalty-benefits").innerHTML = Object.keys(benefits).length
    ? Object.entries(benefits)
        .map(
          ([key, value]) => `
            <article>
              <strong>${key}</strong>
              <span>${value}</span>
            </article>
          `,
        )
        .join("")
    : '<p class="muted">Nenhum beneficio cadastrado para este nivel.</p>';
}

function statusLabel(status) {
  const labels = {
    pending: "Pendente",
    confirmed: "Confirmado",
    preparing: "Em preparo",
    out_for_delivery: "Saiu para entrega",
    delivered: "Entregue",
    cancelled: "Cancelado",
  };
  return labels[status] || status;
}

function renderOrders() {
  $("#orders-list").innerHTML = state.orders.length
    ? state.orders
        .slice(0, 6)
        .map(
          (order) => `
            <article class="order-card">
              <div>
                <strong>#${String(order.id).slice(0, 8)}</strong>
                <span>${dateLabel(order.placed_at)} - ${money(order.total)}</span>
              </div>
              <span class="status ${order.status}">${statusLabel(order.status)}</span>
            </article>
          `,
        )
        .join("")
    : '<p class="muted">Nenhum pedido recente encontrado.</p>';
}

function promotionValue(promotion) {
  if (promotion.type === "percentage") return `${Number(promotion.value)}% off`;
  if (promotion.type === "fixed") return `${money(Number(promotion.value))} off`;
  if (promotion.type === "free_delivery") return "Frete gratis";
  return "Beneficio";
}

function renderPromotions() {
  $("#promotions-list").innerHTML = state.promotions.length
    ? state.promotions
        .map(
          (promotion) => `
            <article class="promotion-card">
              <div>
                <strong>${promotion.code}</strong>
                <span>${promotion.description || promotion.audience}</span>
              </div>
              <div class="promotion-meta">
                <span>${promotionValue(promotion)}</span>
                <span>Pedido minimo ${money((promotion.min_order_cents || 0) / 100)}</span>
                ${promotion.expires_at ? `<span>Valido ate ${dateLabel(promotion.expires_at)}</span>` : ""}
              </div>
            </article>
          `,
        )
        .join("")
    : '<p class="muted">Nenhuma promocao disponivel no momento.</p>';
}

function transactionLabel(type) {
  const labels = {
    earn: "Ganho",
    redeem: "Resgate",
    expire: "Expiracao",
    bonus: "Bonus",
  };
  return labels[type] || type;
}

function renderTransactions() {
  $("#transactions-list").innerHTML = state.transactions.length
    ? state.transactions
        .slice(0, 8)
        .map(
          (transaction) => `
            <article class="transaction-card">
              <div>
                <strong>${transactionLabel(transaction.type)}</strong>
                <span>${transaction.description}</span>
              </div>
              <div>
                <strong>${transaction.points} pts</strong>
                <span>${dateLabel(transaction.created_at)}</span>
              </div>
            </article>
          `,
        )
        .join("")
    : '<p class="muted">Nenhum movimento de pontos encontrado.</p>';
}

function renderAll() {
  renderSession();
  renderProfile();
  renderAddresses();
  renderPreferences();
  renderLoyalty();
  renderOrders();
  renderPromotions();
  renderTransactions();
}

async function loadDashboard() {
  if (!state.session) {
    state.addresses = [];
    renderAll();
    return;
  }

  const [profile, loyalty, orders, promotions, transactions, addresses] = await Promise.all([
    api("/api/v1/me/"),
    api("/api/v1/loyalty/"),
    api("/api/v1/orders/"),
    api("/api/v1/promotions/available"),
    api("/api/v1/loyalty/transactions"),
    api("/api/v1/me/addresses"),
  ]);

  state.profile = profile;
  state.loyalty = loyalty;
  state.orders = orders;
  state.promotions = promotions;
  state.transactions = transactions;
  state.addresses = addresses;
  renderAll();
}

async function loadAddresses() {
  state.addresses = await api("/api/v1/me/addresses");
  renderAddresses();
}

function logout() {
  state.session = null;
  state.profile = null;
  state.loyalty = null;
  state.orders = [];
  state.promotions = [];
  state.transactions = [];
  state.addresses = [];
  saveSession();
  notifySessionChanged();
  clearAddressForm();
  renderAll();
}

async function saveProfile(event) {
  event.preventDefault();
  if (!state.session) {
    showNotice("Entre antes de atualizar seus dados.", "error");
    return;
  }

  state.profile = await api("/api/v1/me/", {
    method: "PATCH",
    body: JSON.stringify(formData(event.currentTarget)),
  });
  renderProfile();
  renderSession();
  showNotice("Dados atualizados.", "success");
}

function preferencePayload(form) {
  return {
    preferred_contact: form.elements.preferred_contact.value || null,
    favorite_categories: $$('input[name="favorite_categories"]:checked').map((input) => input.value),
    dietary_restrictions: splitList(form.elements.dietary_restrictions.value),
    accepts_promotions: form.elements.accepts_promotions.checked,
    accepts_whatsapp: form.elements.accepts_whatsapp.checked,
    notes: form.elements.notes.value || null,
  };
}

async function savePreferences(event) {
  event.preventDefault();
  if (!state.session) {
    showNotice("Entre antes de atualizar suas preferencias.", "error");
    return;
  }

  state.profile = await api("/api/v1/me/", {
    method: "PATCH",
    body: JSON.stringify({
      preferences: preferencePayload(event.currentTarget),
    }),
  });
  renderPreferences();
  showNotice("Preferencias salvas.", "success");
}

function addressPayload(form) {
  const data = formData(form);
  delete data.address_id;
  return {
    ...data,
    is_default: form.elements.is_default.checked,
  };
}

function clearAddressForm() {
  const form = $("#address-form");
  form.reset();
  form.elements.address_id.value = "";
  $("#cancel-address-edit").classList.add("hidden");
}

function editAddress(addressId) {
  const address = state.addresses.find((item) => item.id === addressId);
  if (!address) return;

  const form = $("#address-form");
  form.elements.address_id.value = address.id;
  form.elements.label.value = address.label || "";
  form.elements.street.value = address.street || "";
  form.elements.number.value = address.number || "";
  form.elements.complement.value = address.complement || "";
  form.elements.neighborhood.value = address.neighborhood || "";
  form.elements.city.value = address.city || "";
  form.elements.zip_code.value = address.zip_code || "";
  form.elements.is_default.checked = Boolean(address.is_default);
  $("#address-details").open = true;
  $("#cancel-address-edit").classList.remove("hidden");
  form.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function saveAddress(event) {
  event.preventDefault();
  if (!state.session) {
    showNotice("Entre antes de salvar enderecos.", "error");
    return;
  }

  const form = event.currentTarget;
  const addressId = form.elements.address_id.value;
  const path = addressId ? `/api/v1/me/addresses/${addressId}` : "/api/v1/me/addresses";

  await api(path, {
    method: addressId ? "PATCH" : "POST",
    body: JSON.stringify(addressPayload(form)),
  });
  clearAddressForm();
  await loadAddresses();
  showNotice(addressId ? "Endereco atualizado." : "Endereco salvo.", "success");
}

async function setDefaultAddress(addressId) {
  await api(`/api/v1/me/addresses/${addressId}`, {
    method: "PATCH",
    body: JSON.stringify({ is_default: true }),
  });
  await loadAddresses();
  showNotice("Endereco principal atualizado.", "success");
}

async function deleteAddress(addressId) {
  if (!confirm("Remover este endereco salvo?")) return;
  await api(`/api/v1/me/addresses/${addressId}`, { method: "DELETE" });
  clearAddressForm();
  await loadAddresses();
  showNotice("Endereco removido.", "success");
}

function bindEvents() {
  $("#profile-form").addEventListener("submit", saveProfile);
  $("#preferences-form").addEventListener("submit", savePreferences);
  $("#address-form").addEventListener("submit", saveAddress);
  $("#cancel-address-edit").addEventListener("click", clearAddressForm);
  $("#logout-button").addEventListener("click", logout);
  $("#refresh-dashboard").addEventListener("click", () => {
    loadDashboard().catch((error) => showNotice(error.message, "error"));
  });

  document.addEventListener("click", (event) => {
    const editButton = event.target.closest("[data-edit-address]");
    const defaultButton = event.target.closest("[data-default-address]");
    const deleteButton = event.target.closest("[data-delete-address]");

    if (editButton) editAddress(editButton.dataset.editAddress);
    if (defaultButton) {
      setDefaultAddress(defaultButton.dataset.defaultAddress).catch((error) => {
        showNotice(error.message, "error");
      });
    }
    if (deleteButton) {
      deleteAddress(deleteButton.dataset.deleteAddress).catch((error) => {
        showNotice(error.message, "error");
      });
    }
  });
}

bindEvents();
renderAll();
loadDashboard().catch((error) => showNotice(error.message, "error"));
