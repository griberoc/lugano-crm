const runtimeConfig = window.LUGANO_CONFIG || {};
const DEFAULT_API_URL =
  runtimeConfig.adminApiBaseUrl || runtimeConfig.apiBaseUrl || "http://127.0.0.1:8000";

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function safeHttpUrl(value) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function loadStoredJson(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || "null");
  } catch {
    return null;
  }
}

function clearLegacyTechnicalConfig() {
  localStorage.removeItem("lugano.apiBaseUrl");
  localStorage.removeItem("lugano.adminKey");
}

clearLegacyTechnicalConfig();

const state = {
  apiBaseUrl: DEFAULT_API_URL,
  adminSession: loadStoredJson("lugano.admin.session"),
  adminUser: loadStoredJson("lugano.admin.user"),
  adminProfile: loadStoredJson("lugano.admin.profile"),
  orders: [],
  products: [],
  customers: [],
  promotions: [],
  reports: null,
  auditLogs: [],
  adminUsers: [],
  selectedOrderId: localStorage.getItem("lugano.admin.selectedOrderId") || null,
  reportDateFrom: localStorage.getItem("lugano.admin.reportDateFrom") || "",
  reportDateTo: localStorage.getItem("lugano.admin.reportDateTo") || "",
  auditEntityType: localStorage.getItem("lugano.admin.auditEntityType") || "",
  auditActorProfileId: localStorage.getItem("lugano.admin.auditActorProfileId") || "",
};

const titles = {
  overview: ["Visao Geral", "Operacao comercial, pedidos e campanhas."],
  orders: ["Pedidos", "Acompanhamento e gestao do delivery."],
  products: ["Produtos", "Catalogo vendido no delivery."],
  customers: ["Clientes", "Base de clientes e historico."],
  promotions: ["Campanhas", "Cupons, descontos e frete gratis."],
  reports: ["Relatorios", "Faturamento, rankings, recorrencia e cupons."],
  audit: ["Auditoria", "Registro de acoes administrativas."],
  team: ["Equipe", "Acessos administrativos e papeis do time."],
  settings: ["Acesso", "Sessao administrativa."],
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const ROLE_LEVELS = { staff: 1, manager: 2, owner: 3 };
const orderStatusLabels = {
  pending: "Pendente",
  confirmed: "Confirmado",
  preparing: "Preparando",
  out_for_delivery: "Saiu para entrega",
  delivered: "Entregue",
  cancelled: "Cancelado",
};
const paymentStatusLabels = {
  pending: "Pendente",
  paid: "Pago",
  failed: "Falhou",
  refunded: "Reembolsado",
};
const paymentMethodLabels = {
  pix: "Pix",
  credit_card: "Cartao de credito",
  debit_card: "Cartao de debito",
  cash: "Dinheiro",
};
const auditActionLabels = {
  "admin_user.create": "Acesso criado",
  "admin_user.update": "Acesso alterado",
  "product.create": "Produto criado",
  "product.update": "Produto alterado",
  "product.delete": "Produto removido",
  "customer.update": "Cliente alterado",
  "promotion.create": "Campanha criada",
  "promotion.update": "Campanha alterada",
  "promotion.delete": "Campanha removida",
  "order.update": "Pedido alterado",
};
const auditEntityLabels = {
  admin_user: "Equipe",
  customer: "Cliente",
  order: "Pedido",
  product: "Produto",
  promotion: "Campanha",
};
const orderFlow = [
  "pending",
  "confirmed",
  "preparing",
  "out_for_delivery",
  "delivered",
];

function currentRole() {
  if (state.adminProfile?.role) return state.adminProfile.role;
  return null;
}

function hasRoleLevel(minRole) {
  const role = currentRole();
  if (!role) return false;
  return ROLE_LEVELS[role] >= ROLE_LEVELS[minRole];
}

function canManageBusiness() {
  return hasRoleLevel("manager");
}

function canManageTeam() {
  return currentRole() === "owner";
}

function money(value) {
  const amount = Number(value || 0);
  return amount.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function shortId(id) {
  return id ? String(id).slice(0, 8) : "-";
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("pt-BR");
}

function formatDateTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("pt-BR");
}

function dateInputValue(date) {
  return date.toISOString().slice(0, 10);
}

function defaultReportStart() {
  const date = new Date();
  date.setDate(date.getDate() - 30);
  return dateInputValue(date);
}

function selectedOrder() {
  return state.orders.find((order) => order.id === state.selectedOrderId) || null;
}

function customerName(order) {
  return order?.customer?.full_name || order?.customer?.email || shortId(order?.profile_id);
}

function customerContact(order) {
  const customer = order?.customer;
  if (!customer) return "Cliente nao encontrado";
  return [customer.email, customer.phone].filter(Boolean).join(" | ") || "Sem contato";
}

function formatAddress(address) {
  if (!address) return "Endereco nao encontrado";
  return `${address.label || "Entrega"}: ${address.street}, ${address.number} - ${address.neighborhood}, ${address.city} (${address.zip_code})${address.complement ? ` - ${address.complement}` : ""}`;
}

function orderItems(order) {
  return order?.order_items || order?.items || [];
}

function orderNextStatus(order) {
  if (!order || ["delivered", "cancelled"].includes(order.status)) return null;
  const currentIndex = orderFlow.indexOf(order.status);
  if (currentIndex === -1 || currentIndex >= orderFlow.length - 1) return null;
  return orderFlow[currentIndex + 1];
}

function orderItemCount(order) {
  return orderItems(order).reduce((total, item) => total + Number(item.quantity || 0), 0);
}

function addressSummary(order) {
  const address = order?.address;
  if (!address) return "Endereco pendente";
  return [address.neighborhood, address.city].filter(Boolean).join(" - ") || formatAddress(address);
}

function paintNotice(notice, message, type = "info") {
  if (!notice) return;
  notice.textContent = message;
  notice.classList.remove("hidden");
  notice.style.borderLeftColor = type === "error" ? "var(--danger)" : "var(--brand-2)";
}

function hideNotice(selector) {
  const notice = $(selector);
  if (notice) notice.classList.add("hidden");
}

function showNotice(message, type = "info") {
  paintNotice($("#notice"), message, type);
  if (!hasAdminCredential()) paintNotice($("#login-notice"), message, type);
}

function renderAdminGate() {
  const loggedIn = hasAdminCredential();
  $("#admin-login-gate")?.classList.toggle("hidden", loggedIn);
  $("#admin-app")?.classList.toggle("hidden", !loggedIn);
  document.body.classList.toggle("admin-locked", !loggedIn);
  if (loggedIn) hideNotice("#login-notice");
}

function renderAuthStatus() {
  if (state.adminProfile?.auth_method === "supabase") {
    $$("#admin-session-label").forEach((label) => {
      label.textContent = state.adminProfile.role;
      label.classList.add("active");
    });
    if ($("#admin-session-email")) {
      $("#admin-session-email").textContent = state.adminUser?.email || "-";
    }
    if ($("#admin-session-role")) {
      $("#admin-session-role").textContent = state.adminProfile.role || "-";
    }
    applyRoleAccess();
    renderAdminGate();
    return;
  }

  $$("#admin-session-label").forEach((label) => {
    label.textContent = "Desconectado";
    label.classList.remove("active");
  });
  if ($("#admin-session-email")) $("#admin-session-email").textContent = "-";
  if ($("#admin-session-role")) $("#admin-session-role").textContent = "-";
  applyRoleAccess();
  renderAdminGate();
}

function setConnectionStatus(message, ok = false) {
  const element = $("#connection-status");
  element.textContent = message;
  element.classList.toggle("ok", ok);
  element.classList.toggle(
    "error",
    !ok && !["Aguardando acesso", "Aguardando login"].includes(message),
  );
}

function applyRoleAccess() {
  $$("[data-min-role]").forEach((element) => {
    element.classList.toggle("hidden", !hasRoleLevel(element.dataset.minRole));
  });

  $("#products-layout")?.classList.toggle("single-column", !canManageBusiness());

  const activeView = $(".view.active");
  if (activeView?.dataset.minRole && !hasRoleLevel(activeView.dataset.minRole)) {
    setView("overview");
  }
}

function headers() {
  const authHeaders = {
    "Content-Type": "application/json",
  };
  if (state.adminSession?.access_token) {
    authHeaders.Authorization = `Bearer ${state.adminSession.access_token}`;
  }
  return authHeaders;
}

function hasAdminCredential() {
  return Boolean(state.adminSession?.access_token && state.adminProfile?.auth_method === "supabase");
}

function persistAdminSession() {
  if (state.adminSession) {
    localStorage.setItem("lugano.admin.session", JSON.stringify(state.adminSession));
  } else {
    localStorage.removeItem("lugano.admin.session");
  }

  if (state.adminUser) {
    localStorage.setItem("lugano.admin.user", JSON.stringify(state.adminUser));
  } else {
    localStorage.removeItem("lugano.admin.user");
  }

  if (state.adminProfile) {
    localStorage.setItem("lugano.admin.profile", JSON.stringify(state.adminProfile));
  } else {
    localStorage.removeItem("lugano.admin.profile");
  }
}

function clearAdminSession() {
  state.adminSession = null;
  state.adminUser = null;
  state.adminProfile = null;
  persistAdminSession();
}

async function api(path, options = {}) {
  const response = await fetch(`${state.apiBaseUrl}${path}`, {
    ...options,
    headers: {
      ...headers(),
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
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }

  if (response.status === 204) return null;
  return response.json();
}

function setView(view) {
  const target = $(`#view-${view}`);
  if (target?.dataset.minRole && !hasRoleLevel(target.dataset.minRole)) {
    view = "overview";
  }

  $$(".nav-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  $$(".view").forEach((section) => {
    section.classList.toggle("active", section.id === `view-${view}`);
  });
  $("#view-title").textContent = titles[view][0];
  $("#view-subtitle").textContent = titles[view][1];
}

function renderMetrics() {
  $("#metric-orders").textContent = state.orders.length;
  $("#metric-products").textContent = state.products.filter((item) => item.available).length;
  $("#metric-customers").textContent = state.customers.length;
  $("#metric-promotions").textContent = state.promotions.filter((item) => item.active).length;
}

function renderOverview() {
  $("#overview-orders").innerHTML = state.orders
    .slice(0, 6)
    .map(
      (order) => `
        <tr>
          <td>#${shortId(order.id)}</td>
          <td><span class="status ${escapeHTML(order.status)}">${escapeHTML(orderStatusLabels[order.status] || order.status)}</span></td>
          <td>${money(order.total)}</td>
        </tr>
      `,
    )
    .join("");

  $("#overview-promotions").innerHTML = state.promotions
    .slice(0, 5)
    .map(
      (promotion) => `
        <article class="list-item">
          <div class="list-item-header">
            <strong>${escapeHTML(promotion.code)}</strong>
            <span class="status ${promotion.active ? "active" : ""}">
              ${promotion.active ? "ativa" : "inativa"}
            </span>
          </div>
          <span class="muted">${escapeHTML(promotion.description || promotion.type)}</span>
        </article>
      `,
    )
    .join("");
}

function renderOrders() {
  const counts = Object.keys(orderStatusLabels).reduce((accumulator, status) => {
    accumulator[status] = state.orders.filter((order) => order.status === status).length;
    return accumulator;
  }, {});

  $("#orders-status-board").innerHTML = Object.entries(orderStatusLabels)
    .map(
      ([status, label]) => `
        <article class="status-tile">
          <span>${label}</span>
          <strong>${counts[status] || 0}</strong>
        </article>
      `,
    )
    .join("");

  $("#orders-queue-count").textContent = `${state.orders.length} ${state.orders.length === 1 ? "pedido" : "pedidos"}`;

  $("#orders-queue").innerHTML = state.orders.length
    ? state.orders
        .map((order) => {
          const next = orderNextStatus(order);
          return `
            <article class="order-queue-card ${order.id === state.selectedOrderId ? "active" : ""}">
              <div class="queue-card-main">
                <div>
                  <span class="queue-id">#${shortId(order.id)}</span>
                  <strong>${escapeHTML(customerName(order))}</strong>
                  <p>${formatDateTime(order.placed_at)}</p>
                </div>
                <span class="status ${escapeHTML(order.status)}">${escapeHTML(orderStatusLabels[order.status] || order.status)}</span>
              </div>
              <div class="queue-meta">
                <span>${orderItemCount(order)} ${orderItemCount(order) === 1 ? "item" : "itens"}</span>
                <span>${escapeHTML(addressSummary(order))}</span>
                <span>${money(order.total)}</span>
              </div>
              <div class="queue-card-footer">
                <span class="status ${escapeHTML(order.payment_status)}">${escapeHTML(paymentStatusLabels[order.payment_status] || order.payment_status)}</span>
                <div class="table-actions">
                  <button class="small-button" data-order-select="${escapeHTML(order.id)}" type="button">Abrir</button>
                  <button class="small-button primary-action" data-order-next="${escapeHTML(order.id)}" type="button" ${!next ? "disabled" : ""}>
                    ${next ? orderStatusLabels[next] : "Concluido"}
                  </button>
                </div>
              </div>
            </article>
          `;
        })
        .join("")
    : `
      <div class="empty-queue">
        <strong>Nenhum pedido nesta fila</strong>
        <span>Use outro filtro ou atualize a lista.</span>
      </div>
    `;

  renderOrderDetail();
}

function renderOrderDetail() {
  const panel = $("#order-detail");
  const order = selectedOrder();
  if (!order) {
    panel.innerHTML = `
      <div class="empty-state">
        <h2>Selecione um pedido</h2>
        <p>Veja itens, cliente, entrega, observacoes e atualize o status.</p>
      </div>
    `;
    return;
  }

  const items = orderItems(order);
  const nextStatus = orderNextStatus(order);
  panel.innerHTML = `
    <div class="order-detail-heading detail-hero">
      <div>
        <span class="muted">Pedido #${shortId(order.id)}</span>
        <h2>${escapeHTML(customerName(order))}</h2>
        <p>${formatDateTime(order.placed_at)}</p>
      </div>
      <div class="detail-hero-actions">
        <span class="status ${escapeHTML(order.status)}">${escapeHTML(orderStatusLabels[order.status] || order.status)}</span>
        <strong>${money(order.total)}</strong>
      </div>
    </div>

    <div class="quick-actions">
      <button class="primary-button" data-order-next="${escapeHTML(order.id)}" type="button" ${!nextStatus ? "disabled" : ""}>
        ${nextStatus ? `Mover para ${orderStatusLabels[nextStatus]}` : "Sem proximo status"}
      </button>
      <span>${escapeHTML(paymentStatusLabels[order.payment_status] || order.payment_status)}</span>
    </div>

    <div class="detail-grid">
      <article>
        <span>Cliente</span>
        <strong>${escapeHTML(customerName(order))}</strong>
        <p>${escapeHTML(customerContact(order))}</p>
      </article>
      <article>
        <span>Entrega</span>
        <strong>${escapeHTML(formatAddress(order.address))}</strong>
        <p>${escapeHTML(order.delivery_instructions || order.notes || "Sem observacoes de entrega")}</p>
      </article>
      <article>
        <span>Pagamento</span>
        <strong>${escapeHTML(paymentMethodLabels[order.payment_method] || order.payment_method)}</strong>
        <p>${escapeHTML(paymentStatusLabels[order.payment_status] || order.payment_status)}</p>
      </article>
      <article>
        <span>Total</span>
        <strong>${money(order.total)}</strong>
        <p>Subtotal ${money(order.subtotal)} | Entrega ${money(order.delivery_fee)} | Desconto ${money(order.discount)}</p>
      </article>
    </div>

    <section class="detail-section">
      <div class="detail-section-heading">
        <h3>Itens do pedido</h3>
        <span>${orderItemCount(order)} ${orderItemCount(order) === 1 ? "item" : "itens"}</span>
      </div>
      <div class="item-list compact-list">
        ${
          items.length
            ? items
                .map(
                  (item) => `
                    <article class="detail-item-row">
                      <div class="list-item-header">
                        <strong>${escapeHTML(item.product?.name || shortId(item.product_id))}</strong>
                        <span>${item.quantity} x ${money(item.unit_price)}</span>
                      </div>
                      <span class="muted">${escapeHTML(item.product?.category || "produto")}${item.customization ? ` - ${escapeHTML(item.customization)}` : ""}</span>
                    </article>
                  `,
                )
                .join("")
            : '<p class="muted">Nenhum item encontrado.</p>'
        }
      </div>
    </section>

    <form class="detail-section order-update-form" id="order-update-form">
      <div class="detail-section-heading">
        <h3>Atualizar operacao</h3>
        <span>Registro auditado</span>
      </div>
      <label>Status
        <select name="status">
          ${Object.entries(orderStatusLabels)
            .map(([value, label]) => `<option value="${value}" ${order.status === value ? "selected" : ""}>${label}</option>`)
            .join("")}
        </select>
      </label>
      <label>Pagamento
        <select name="payment_status">
          ${Object.entries(paymentStatusLabels)
            .map(([value, label]) => `<option value="${value}" ${order.payment_status === value ? "selected" : ""}>${label}</option>`)
            .join("")}
        </select>
      </label>
      <label>Observacoes<textarea name="notes" rows="3">${escapeHTML(order.notes)}</textarea></label>
      <div class="button-row">
        <button class="primary-button" type="submit">Salvar atualizacao</button>
        <button class="ghost-button" data-order-next="${escapeHTML(order.id)}" type="button" ${["delivered", "cancelled"].includes(order.status) ? "disabled" : ""}>Avancar status</button>
      </div>
    </form>
  `;
}

function renderProducts() {
  $("#products-list").innerHTML = state.products
    .map((product) => {
      const initial = String(product.name || "L").trim().slice(0, 1).toUpperCase();
      const imageUrl = safeHttpUrl(product.image_url);
      const thumb = imageUrl
        ? `<img src="${escapeHTML(imageUrl)}" alt="${escapeHTML(product.name)}" loading="lazy" />`
        : `<span>${escapeHTML(initial)}</span>`;

      return `
        <article class="list-item product-list-item">
          <figure class="product-thumb">${thumb}</figure>
          <div class="product-list-content">
            <div class="list-item-header">
              <strong>${escapeHTML(product.name)}</strong>
              <span>${money(product.price)}</span>
            </div>
            <span class="muted">${escapeHTML(product.category)}</span>
            <span class="status ${product.available ? "active" : ""}">
              ${product.available ? "disponivel" : "indisponivel"}
            </span>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderCustomers() {
  $("#customers-table").innerHTML = state.customers
    .map(
      (customer) => `
        <tr>
          <td>${escapeHTML(customer.full_name || "-")}</td>
          <td>${escapeHTML(customer.email || "-")}</td>
          <td>${escapeHTML(customer.phone || "-")}</td>
          <td>${formatDate(customer.created_at)}</td>
        </tr>
      `,
    )
    .join("");
}

function renderPromotions() {
  $("#promotions-list").innerHTML = state.promotions
    .map(
      (promotion) => `
        <article class="list-item">
          <div class="list-item-header">
            <strong>${escapeHTML(promotion.code)}</strong>
            <span class="status ${promotion.active ? "active" : ""}">
              ${promotion.active ? "ativa" : "inativa"}
            </span>
          </div>
          <span class="muted">${escapeHTML(promotion.description || promotion.type)}</span>
          <span>${escapeHTML(promotion.type)} - ${escapeHTML(promotion.value)}</span>
        </article>
      `,
    )
    .join("");
}

function renderReports() {
  const reports = state.reports;
  if (!reports) {
    $("#report-net-revenue").textContent = money(0);
    $("#report-average-ticket").textContent = money(0);
    $("#report-orders-count").textContent = "0";
    $("#report-coupon-uses").textContent = "0";
    $("#report-summary-list").innerHTML = '<p class="muted">Relatorios ainda nao carregados.</p>';
    $("#report-products-table").innerHTML = emptyReportRow(4);
    $("#report-customers-table").innerHTML = emptyReportRow(4);
    $("#report-coupons-table").innerHTML = emptyReportRow(3);
    return;
  }

  const summary = reports.summary;
  const couponUses = reports.coupon_usage.reduce(
    (total, coupon) => total + Number(coupon.uses_count || 0),
    0,
  );

  $("#report-net-revenue").textContent = money(summary.net_revenue);
  $("#report-average-ticket").textContent = money(summary.average_ticket);
  $("#report-orders-count").textContent = summary.orders_count;
  $("#report-coupon-uses").textContent = couponUses;

  $("#report-summary-list").innerHTML = [
    ["Faturamento bruto", money(summary.gross_revenue)],
    ["Faturamento liquido", money(summary.net_revenue)],
    ["Taxas de entrega", money(summary.delivery_fee_total)],
    ["Descontos em cupons", money(summary.coupon_discount_total)],
    ["Pedidos entregues", summary.delivered_orders_count],
    ["Pedidos cancelados", summary.cancelled_orders_count],
  ]
    .map(
      ([label, value]) => `
        <article>
          <span>${label}</span>
          <strong>${value}</strong>
        </article>
      `,
    )
    .join("");

  $("#report-products-table").innerHTML = reports.top_products.length
    ? reports.top_products
        .map(
          (product) => `
            <tr>
              <td>
                <strong>${escapeHTML(product.product_name)}</strong>
                <span class="table-subtitle">${escapeHTML(product.category || "sem categoria")}</span>
              </td>
              <td>${product.quantity_sold}</td>
              <td>${product.orders_count}</td>
              <td>${money(product.revenue)}</td>
            </tr>
          `,
        )
        .join("")
    : emptyReportRow(4);

  $("#report-customers-table").innerHTML = reports.recurring_customers.length
    ? reports.recurring_customers
        .map(
          (customer) => `
            <tr>
              <td>
                <strong>${escapeHTML(customer.full_name || customer.email || shortId(customer.profile_id))}</strong>
                <span class="table-subtitle">${escapeHTML(customer.email || customer.phone || "sem contato")}</span>
              </td>
              <td>${customer.orders_count}</td>
              <td>${money(customer.total_spent)}</td>
              <td>${formatDate(customer.last_order_at)}</td>
            </tr>
          `,
        )
        .join("")
    : emptyReportRow(4);

  $("#report-coupons-table").innerHTML = reports.coupon_usage.length
    ? reports.coupon_usage
        .map(
          (coupon) => `
            <tr>
              <td>
                <strong>${escapeHTML(coupon.code)}</strong>
                <span class="table-subtitle">${escapeHTML(coupon.description || "campanha")}</span>
              </td>
              <td>${coupon.uses_count}</td>
              <td>${money(coupon.total_discount)}</td>
            </tr>
          `,
        )
        .join("")
    : emptyReportRow(3);
}

function emptyReportRow(colspan) {
  return `<tr><td class="muted" colspan="${colspan}">Nenhum dado no periodo.</td></tr>`;
}

function auditDetails(log) {
  const fields = log.metadata?.changed_fields || [];
  const target = shortId(log.entity_id);
  if (fields.length) return `${target} - ${fields.join(", ")}`;
  if (log.metadata?.status_changed) return `${target} - status alterado`;
  return target;
}

function renderAuditLogs() {
  const table = $("#audit-table");
  if (!table) return;

  table.innerHTML = state.auditLogs.length
    ? state.auditLogs
        .map(
          (log) => `
            <tr>
              <td>${formatDateTime(log.created_at)}</td>
              <td>${escapeHTML(auditActionLabels[log.action] || log.action)}</td>
              <td>
                <strong>${escapeHTML(auditEntityLabels[log.entity_type] || log.entity_type)}</strong>
                <span class="table-subtitle">${shortId(log.entity_id)}</span>
              </td>
              <td>
                <strong>${escapeHTML(log.actor_email || log.actor_role || "Sistema")}</strong>
                <span class="table-subtitle">${escapeHTML(log.actor_profile_id ? shortId(log.actor_profile_id) : log.auth_method || "-")}</span>
              </td>
              <td>${escapeHTML(auditDetails(log))}</td>
            </tr>
          `,
        )
        .join("")
    : '<tr><td class="muted" colspan="5">Nenhum evento de auditoria encontrado.</td></tr>';
}

function renderTeam() {
  const table = $("#team-table");
  if (!table) return;

  table.innerHTML = state.adminUsers
    .map(
      (user) => `
        <tr>
          <td>${escapeHTML(user.full_name || shortId(user.profile_id))}</td>
          <td>${escapeHTML(user.email || "-")}</td>
          <td>
            <select class="table-control" data-admin-role="${escapeHTML(user.profile_id)}">
              <option value="staff" ${user.role === "staff" ? "selected" : ""}>Staff</option>
              <option value="manager" ${user.role === "manager" ? "selected" : ""}>Manager</option>
              <option value="owner" ${user.role === "owner" ? "selected" : ""}>Owner</option>
            </select>
          </td>
          <td>
            <label class="check-row table-check">
              <input data-admin-active="${escapeHTML(user.profile_id)}" type="checkbox" ${user.active ? "checked" : ""} />
              ${user.active ? "Ativo" : "Inativo"}
            </label>
          </td>
          <td>
            <div class="table-actions">
              <button class="small-button" data-admin-save="${escapeHTML(user.profile_id)}" type="button">Salvar</button>
              <button class="small-button danger-button" data-admin-disable="${escapeHTML(user.profile_id)}" type="button">Desativar</button>
            </div>
          </td>
        </tr>
      `,
    )
    .join("");
}

function renderAll() {
  renderMetrics();
  renderOverview();
  renderOrders();
  renderProducts();
  renderCustomers();
  renderPromotions();
  renderReports();
  renderAuditLogs();
  renderTeam();
  applyRoleAccess();
}

async function loadOrders() {
  const filter = $("#order-status-filter").value;
  const query = filter ? `?status=${encodeURIComponent(filter)}` : "";
  state.orders = await api(`/api/v1/admin/orders${query}`);
  if (!state.orders.some((order) => order.id === state.selectedOrderId)) {
    state.selectedOrderId = state.orders[0]?.id || null;
  }
  if (state.selectedOrderId) {
    localStorage.setItem("lugano.admin.selectedOrderId", state.selectedOrderId);
  } else {
    localStorage.removeItem("lugano.admin.selectedOrderId");
  }
}

async function loadProducts() {
  state.products = await api("/api/v1/admin/products");
}

async function loadCustomers() {
  state.customers = await api("/api/v1/admin/customers");
}

async function loadPromotions() {
  state.promotions = await api("/api/v1/admin/promotions");
}

async function loadReports() {
  const params = new URLSearchParams();
  if (state.reportDateFrom) params.set("date_from", state.reportDateFrom);
  if (state.reportDateTo) params.set("date_to", state.reportDateTo);
  const query = params.toString() ? `?${params.toString()}` : "";
  state.reports = await api(`/api/v1/admin/reports${query}`);
}

async function loadAdminUsers() {
  state.adminUsers = await api("/api/v1/admin/users");
}

async function loadAuditLogs() {
  const params = new URLSearchParams();
  if (state.auditEntityType) params.set("entity_type", state.auditEntityType);
  if (state.auditActorProfileId) params.set("actor_profile_id", state.auditActorProfileId);
  const query = params.toString() ? `?${params.toString()}` : "";
  state.auditLogs = await api(`/api/v1/admin/audit-logs${query}`);
}

async function loadAuditLogsIfAllowed() {
  if (canManageTeam()) await loadAuditLogs();
}

async function loadDashboard() {
  if (!hasAdminCredential()) {
    setConnectionStatus("Aguardando acesso", false);
    renderAuthStatus();
    return;
  }

  renderAuthStatus();

  try {
    const loaders = [loadOrders(), loadProducts(), loadCustomers()];
    if (canManageBusiness()) {
      loaders.push(loadPromotions());
      loaders.push(loadReports());
    } else {
      state.promotions = [];
      state.reports = null;
    }
    if (canManageTeam()) {
      loaders.push(loadAdminUsers());
      loaders.push(loadAuditLogs());
    } else {
      state.adminUsers = [];
      state.auditLogs = [];
    }

    await Promise.all(loaders);
    renderAll();
    setConnectionStatus("Conectado", true);
  } catch (error) {
    if ([401, 403].includes(error.status)) {
      clearAdminSession();
      setConnectionStatus("Aguardando login", false);
      renderAuthStatus();
      showNotice("Sessao administrativa expirada. Entre novamente.", "error");
      return;
    }

    setConnectionStatus("Falha ao carregar", false);
    showNotice(`Falha ao carregar dados administrativos: ${error.message}`, "error");
  }
}

function formData(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  form.querySelectorAll("input[type='checkbox']").forEach((input) => {
    data[input.name] = input.checked;
  });
  Object.keys(data).forEach((key) => {
    if (data[key] === "") data[key] = null;
  });
  return data;
}

async function createProduct(event) {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    const data = formData(form);
    await api("/api/v1/admin/products", {
      method: "POST",
      body: JSON.stringify(data),
    });
    form.reset();
    await loadProducts();
    await loadAuditLogsIfAllowed();
    renderAll();
    showNotice("Produto criado e listado no catalogo.");
  } catch (error) {
    showNotice(`Nao foi possivel criar o produto: ${error.message}`, "error");
  }
}

async function createPromotion(event) {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    const data = formData(form);
    data.min_order_cents = Number(data.min_order_cents || 0);
    data.max_uses = data.max_uses ? Number(data.max_uses) : null;
    await api("/api/v1/admin/promotions", {
      method: "POST",
      body: JSON.stringify(data),
    });
    form.reset();
    form.elements.active.checked = true;
    form.elements.value.value = 0;
    form.elements.min_order_cents.value = 0;
    await loadPromotions();
    await loadAuditLogsIfAllowed();
    renderAll();
    showNotice("Campanha criada.");
  } catch (error) {
    showNotice(`Nao foi possivel criar a campanha: ${error.message}`, "error");
  }
}

async function refreshReports(event) {
  event.preventDefault();
  const data = formData(event.currentTarget);
  state.reportDateFrom = data.date_from || "";
  state.reportDateTo = data.date_to || "";
  localStorage.setItem("lugano.admin.reportDateFrom", state.reportDateFrom);
  localStorage.setItem("lugano.admin.reportDateTo", state.reportDateTo);

  try {
    await loadReports();
    renderReports();
    showNotice("Relatorios atualizados.");
  } catch (error) {
    showNotice(`Nao foi possivel carregar relatorios: ${error.message}`, "error");
  }
}

async function refreshAuditLogs(event) {
  event.preventDefault();
  const data = formData(event.currentTarget);
  state.auditEntityType = data.entity_type || "";
  state.auditActorProfileId = data.actor_profile_id || "";
  localStorage.setItem("lugano.admin.auditEntityType", state.auditEntityType);
  localStorage.setItem("lugano.admin.auditActorProfileId", state.auditActorProfileId);

  try {
    await loadAuditLogs();
    renderAuditLogs();
    showNotice("Auditoria atualizada.");
  } catch (error) {
    showNotice(`Nao foi possivel carregar auditoria: ${error.message}`, "error");
  }
}

async function createAdminUser(event) {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    const data = formData(form);
    await api("/api/v1/admin/users", {
      method: "POST",
      body: JSON.stringify(data),
    });
    form.reset();
    form.elements.active.checked = true;
    form.elements.role.value = "staff";
    await loadAdminUsers();
    await loadAuditLogsIfAllowed();
    renderAll();
    showNotice("Acesso administrativo salvo.");
  } catch (error) {
    showNotice(`Nao foi possivel salvar o acesso: ${error.message}`, "error");
  }
}

async function updateAdminUser(profileId, updates) {
  try {
    await api(`/api/v1/admin/users/${profileId}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
    await loadAdminUsers();
    await loadAuditLogsIfAllowed();
    renderAll();
    showNotice("Acesso administrativo atualizado.");
  } catch (error) {
    showNotice(`Nao foi possivel atualizar o acesso: ${error.message}`, "error");
  }
}

async function saveAdminUser(profileId) {
  const role = $(`[data-admin-role="${profileId}"]`).value;
  const active = $(`[data-admin-active="${profileId}"]`).checked;
  await updateAdminUser(profileId, { role, active });
}

async function disableAdminUser(profileId) {
  await updateAdminUser(profileId, { active: false });
}

function selectOrder(orderId) {
  state.selectedOrderId = orderId;
  localStorage.setItem("lugano.admin.selectedOrderId", orderId);
  renderOrders();
}

async function updateOrder(orderId, updates) {
  try {
    await api(`/api/v1/admin/orders/${orderId}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
    await loadOrders();
    await loadAuditLogsIfAllowed();
    renderAll();
    showNotice("Pedido atualizado.");
  } catch (error) {
    showNotice(`Nao foi possivel atualizar o pedido: ${error.message}`, "error");
  }
}

async function advanceOrder(orderId) {
  const order = state.orders.find((item) => item.id === orderId);
  if (!order) return;
  const currentIndex = orderFlow.indexOf(order.status);
  if (currentIndex === -1 || currentIndex >= orderFlow.length - 1) return;
  const next = orderFlow[Math.min(currentIndex + 1, orderFlow.length - 1)];
  await updateOrder(orderId, {
    status: next,
    payment_status: next === "delivered" ? "paid" : order.payment_status,
    delivered_at: next === "delivered" ? new Date().toISOString() : null,
  });
}

async function saveSelectedOrder(event) {
  event.preventDefault();
  const order = selectedOrder();
  if (!order) return;
  const data = formData(event.currentTarget);
  await updateOrder(order.id, {
    status: data.status,
    payment_status: data.payment_status,
    delivered_at: data.status === "delivered" ? order.delivered_at || new Date().toISOString() : null,
    notes: data.notes || null,
  });
}

async function loginAdmin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    const data = formData(form);
    const auth = await api("/api/v1/admin/login", {
      method: "POST",
      body: JSON.stringify({
        email: data.email,
        password: data.password,
      }),
    });
    if (!auth.access_token || auth.admin?.auth_method !== "supabase") {
      throw new Error("Usuario sem acesso administrativo ativo.");
    }

    state.adminSession = {
      access_token: auth.access_token,
      refresh_token: auth.refresh_token,
      expires_at: Date.now() + Number(auth.expires_in || 3600) * 1000,
    };
    state.adminUser = auth.user || null;
    state.adminProfile = auth.admin || null;
    persistAdminSession();
    renderAuthStatus();
    form.reset();
    setConnectionStatus(`Admin ${state.adminProfile?.role || "validado"}`, true);
    hideNotice("#login-notice");
    showNotice("Login administrativo validado.");
    await loadDashboard();
  } catch (error) {
    clearAdminSession();
    renderAuthStatus();
    setConnectionStatus("Falha no acesso", false);
    showNotice(`Nao foi possivel entrar no admin: ${error.message}`, "error");
  }
}

function logoutAdmin() {
  clearAdminSession();
  state.orders = [];
  state.products = [];
  state.customers = [];
  state.promotions = [];
  state.auditLogs = [];
  state.adminUsers = [];
  state.selectedOrderId = null;
  localStorage.removeItem("lugano.admin.selectedOrderId");
  renderAll();
  renderAuthStatus();
  setConnectionStatus("Aguardando acesso", false);
  showNotice("Sessao administrativa encerrada.");
}

function bindEvents() {
  $$(".nav-tab").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });

  $$("[data-refresh]").forEach((button) => {
    button.addEventListener("click", loadDashboard);
  });

  $("#refresh-orders").addEventListener("click", async () => {
    await loadOrders();
    renderAll();
  });
  $("#order-status-filter").addEventListener("change", async () => {
    await loadOrders();
    renderAll();
  });
  $("#product-form").addEventListener("submit", createProduct);
  $("#promotion-form").addEventListener("submit", createPromotion);
  $("#reports-filter-form").addEventListener("submit", refreshReports);
  $("#audit-filter-form").addEventListener("submit", refreshAuditLogs);
  $("#team-form").addEventListener("submit", createAdminUser);
  $("#admin-login-form").addEventListener("submit", loginAdmin);
  $("#admin-logout").addEventListener("click", logoutAdmin);

  document.addEventListener("submit", async (event) => {
    if (event.target.matches("#order-update-form")) {
      await saveSelectedOrder(event);
    }
  });

  document.addEventListener("click", async (event) => {
    const selectOrderButton = event.target.closest("[data-order-select]");
    if (selectOrderButton) {
      selectOrder(selectOrderButton.dataset.orderSelect);
      return;
    }

    const orderButton = event.target.closest("[data-order-next]");
    if (orderButton) {
      await advanceOrder(orderButton.dataset.orderNext);
      return;
    }

    const saveAdminButton = event.target.closest("[data-admin-save]");
    if (saveAdminButton) {
      await saveAdminUser(saveAdminButton.dataset.adminSave);
      return;
    }

    const disableAdminButton = event.target.closest("[data-admin-disable]");
    if (disableAdminButton) {
      await disableAdminUser(disableAdminButton.dataset.adminDisable);
    }
  });
}

function hydrateSettings() {
  if (!state.reportDateFrom) state.reportDateFrom = defaultReportStart();
  if (!state.reportDateTo) state.reportDateTo = dateInputValue(new Date());
  $("#reports-filter-form").elements.date_from.value = state.reportDateFrom;
  $("#reports-filter-form").elements.date_to.value = state.reportDateTo;
  $("#audit-filter-form").elements.entity_type.value = state.auditEntityType;
  $("#audit-filter-form").elements.actor_profile_id.value = state.auditActorProfileId;
  renderAuthStatus();
}

bindEvents();
hydrateSettings();
loadDashboard();
