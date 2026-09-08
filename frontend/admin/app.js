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
  overview: ["Visão Geral", "Operação comercial, pedidos e campanhas."],
  orders: ["Pedidos", "Acompanhamento e gestão do delivery."],
  products: ["Produtos", "Catálogo vendido no delivery."],
  customers: ["Clientes", "Base de clientes e histórico."],
  promotions: ["Campanhas", "Cupons, descontos e frete grátis."],
  reports: ["Relatórios", "Faturamento, rankings, recorrência e cupons."],
  audit: ["Auditoria", "Registro de ações administrativas."],
  team: ["Equipe", "Acessos administrativos e papéis do time."],
  settings: ["Acesso", "Sessão administrativa."],
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
  credit_card: "Cartão de crédito",
  debit_card: "Cartão de débito",
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
  if (!customer) return "Cliente não encontrado";
  return [customer.email, customer.phone].filter(Boolean).join(" | ") || "Sem contato";
}

function formatAddress(address) {
  if (!address) return "Endereço não encontrado";
  return `${address.label || "Entrega"}: ${address.street}, ${address.number} - ${address.neighborhood}, ${address.city} (${address.zip_code})${address.complement ? ` - ${address.complement}` : ""}`;
}

function orderItems(order) {
  return order?.order_items || order?.items || [];
}

function orderNextStatus(order) {
 if(!order || ["delivered","cancelled"].includes(order.status))return null;
 const index=orderFlow.indexOf(order.status), next=orderFlow[index+1];
 if(index<0 || !next)return null;
 if(["preparing","out_for_delivery","delivered"].includes(next) && order.payment_status!=="paid")return null;
 return next;
}

function orderItemCount(order) {
  return orderItems(order).reduce((total, item) => total + Number(item.quantity || 0), 0);
}

function addressSummary(order) {
  const address = order?.address;
  if (!address) return "Endereço pendente";
  return [address.neighborhood, address.city].filter(Boolean).join(" - ") || formatAddress(address);
}

function paintNotice(node,message,type="info") { LuganoUI.notice(node,message,type); LuganoUI.toast(message,type); }

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

async function api(path, options = {}) { return LuganoUI.request(state.apiBaseUrl + path,{...options, headers:{"Content-Type":"application/json",...headers(),...(options.headers || {})}}); }

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
  localStorage.setItem("lugano.admin.view",view);
  document.body.classList.remove("admin-detail-open");
  $$(".nav-tab").forEach(b=>b.setAttribute("aria-current",b.dataset.view===view?"page":"false"));
  if(innerWidth<=1000) $('.nav-tab.active')?.scrollIntoView({block:"nearest",inline:"center",behavior:"instant"});
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
        <button type="button" class="status-tile" data-status-filter="${escapeHTML(status)}" aria-label="Filtrar ${escapeHTML(label)}">
          <span>${label}</span>
          <strong>${counts[status] || 0}</strong>
        </button>
      `,
    )
    .join("");

  $("#orders-queue-count").textContent = `${state.orders.length} ${state.orders.length === 1 ? "pedido" : "pedidos"}`;

  const visibleOrders=state.orders.filter(o=>(!$("#order-status-filter").value || o.status===$("#order-status-filter").value) && (customerName(o)+" "+o.id).toLowerCase().includes(($("#order-search")?.value || "").toLowerCase()));
  $("#orders-queue").innerHTML = visibleOrders.length
    ? visibleOrders
        .map((order) => {
          const next = orderNextStatus(order);
          return `
            <article class="order-queue-card ${order.id === state.selectedOrderId ? "active" : ""}">
              <div class="queue-card-main">
                <div>
                  <span class="queue-id">#${shortId(order.id)}</span>
                  <strong>${escapeHTML(customerName(order))}</strong>
                  <p>${formatDateTime(order.placed_at)} · ${orderAge(order)}</p>
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
                    ${next ? orderStatusLabels[next] : "Concluído"}
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
        <p>Veja itens, cliente, entrega, observações e atualize o status.</p>
      </div>
    `;
    return;
  }

  const items = orderItems(order);
  const nextStatus = orderNextStatus(order);
  panel.innerHTML = `
    <button id="back-to-queue" class="ghost-button" type="button">Voltar à fila</button><div class="order-detail-heading detail-hero">
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
        ${nextStatus ? `Mover para ${orderStatusLabels[nextStatus]}` : "Sem próximo status"}
      </button>
      <span>${order.payment_status !== "paid" ? "Confirme o pagamento antes de iniciar o preparo." : "Pagamento confirmado"}</span>
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
        <p>${escapeHTML(order.delivery_instructions || order.notes || "Sem observações de entrega")}</p>
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
        <h3>Atualizar operação</h3>
        <span>Registro auditado</span>
      </div>
      <label>Status
        <select name="status">
          ${Object.entries(orderStatusLabels)
            .filter(([value]) => value === order.status || value === nextStatus || (!["delivered","cancelled"].includes(order.status) && value === "cancelled"))
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
      <label>Observações<textarea name="notes" rows="3">${escapeHTML(order.notes)}</textarea></label>
      <div class="button-row">
        <button class="primary-button" type="submit">Salvar atualização</button>

      </div>
    </form>
  `;
}

function renderProducts() {
  $("#products-list").innerHTML = filteredCollection("products",state.products)
    .map((product) => {
      const initial = String(product.name || "L").trim().slice(0, 1).toUpperCase();
      const imageUrl = LuganoUI.media(safeHttpUrl(product.image_url));
      const thumb = imageUrl
        ? `<img src="${escapeHTML(imageUrl)}" alt="${escapeHTML(product.name)}" width="64" height="64" loading="lazy" />`
        : `<span>${escapeHTML(initial)}</span>`;

      return `
        <article class="list-item product-list-item">
          <figure class="product-thumb">${thumb}</figure>
          <div class="product-list-content">
            <div class="list-item-header">
              <strong>${escapeHTML(product.name)}</strong>
              <span data-product-price-display>${money(product.price)}</span>
            </div>
            <span class="muted">${escapeHTML(product.category)}</span>
            <span class="status ${product.available ? "active" : ""}">
              ${product.available ? "disponível" : "indisponível"}
            </span>
          </div>
          ${canManageBusiness() ? `<form class="inline-price-form" data-price-product="${escapeHTML(product.id)}" novalidate>
            <label for="price-${escapeHTML(product.id)}">Preço (R$)</label>
            <div class="inline-price-controls"><input id="price-${escapeHTML(product.id)}" name="price" type="text" inputmode="decimal" autocomplete="off" value="${Number(product.price).toFixed(2).replace('.', ',')}" aria-label="Preço de ${escapeHTML(product.name)}" aria-describedby="price-status-${escapeHTML(product.id)}" />
            <button class="primary-button" type="submit">Salvar</button></div>
            <small id="price-status-${escapeHTML(product.id)}" role="status" aria-live="polite"></small>
          </form><button class="ghost-button" data-edit-product="${escapeHTML(product.id)}">Editar</button>` : ""}
        </article>
      `;
    })
    .join("") || LuganoUI.empty("Seu catálogo está vazio","Cadastre o primeiro produto para começar.");
}

function parseProductPrice(value) {
  const text = String(value).trim();
  if (!/^\d{1,6}([,.]\d{1,2})?$/.test(text)) return null;
  const cents = Math.round(Number(text.replace(',', '.')) * 100);
  return cents > 0 && cents <= 99999999 ? cents : null;
}

async function saveInlineProductPrice(event) {
  const form = event.target.closest('[data-price-product]');
  if (!form) return;
  event.preventDefault();
  if (form.dataset.saving || !canManageBusiness()) return;
  const input = form.elements.price;
  const status = form.querySelector('[role="status"]');
  const cents = parseProductPrice(input.value);
  input.setAttribute('aria-invalid', String(cents === null));
  status.className = cents === null ? 'price-error' : '';
  if (cents === null) {
    status.textContent = 'Informe um preço maior que zero, com até 2 casas decimais (ex.: 19,90).';
    input.focus();
    return;
  }
  const product = state.products.find(item => item.id === form.dataset.priceProduct);
  if (!product) return;
  if (cents === Math.round(Number(product.price) * 100)) {
    status.textContent = 'Este preço já está salvo.';
    return;
  }
  form.dataset.saving = 'true';
  form.setAttribute('aria-busy', 'true');
  input.disabled = true;
  status.textContent = 'Salvando preço…';
  try {
    await LuganoUI.busy(form.querySelector('button'), 'Salvando…', async () => {
      const updated = await api('/api/v1/admin/products/' + encodeURIComponent(product.id), {
        method: 'PATCH', body: JSON.stringify({price: (cents / 100).toFixed(2)})
      });
      product.price = updated.price;
      input.value = Number(updated.price).toFixed(2).replace('.', ',');
      form.closest('article').querySelector('[data-product-price-display]').textContent = money(updated.price);
      status.textContent = 'Preço atualizado com sucesso.';
      status.className = 'price-success';
    });
  } catch (error) {
    status.className = 'price-error';
    status.textContent = 'Não foi possível confirmar o preço. ' + error.message + ' Você pode tentar novamente.';
  } finally {
    delete form.dataset.saving;
    form.removeAttribute('aria-busy');
    input.disabled = false;
  }
}

function renderCustomers() {
  $("#customers-table").innerHTML = filteredCollection("customers",state.customers)
    .map(
      (customer) => `
        <tr>
          <td>${escapeHTML(customer.full_name || "-")}${canManageBusiness() ? `<button class="ghost-button" data-edit-customer="${escapeHTML(customer.id)}">Editar</button>` : ""}</td>
          <td>${escapeHTML(customer.email || "-")}</td>
          <td>${escapeHTML(customer.phone || "-")}</td>
          <td>${formatDate(customer.created_at)}</td>
        </tr>
      `,
    )
    .join("");
}

function renderPromotions() {
  $("#promotions-list").innerHTML = filteredCollection("promotions",state.promotions)
    .map(
      (promotion) => `
        <article class="list-item">
          <div class="list-item-header">
            <strong>${escapeHTML(promotion.code)}</strong>${canManageBusiness() ? `<button class="ghost-button" data-edit-promotion="${escapeHTML(promotion.id)}">Editar</button>` : ""}
            <span class="status ${promotion.active ? "active" : ""}">
              ${promotion.active ? "ativa" : "inativa"}
            </span>
          </div>
          <span class="muted">${escapeHTML(promotion.description || promotion.type)}</span>
          <span>${escapeHTML(({percentage:"Desconto percentual",fixed:"Desconto em reais",free_delivery:"Entrega grátis"})[promotion.type] || "Benefício")} · ${escapeHTML(promotion.value)}</span>
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
    $("#report-summary-list").innerHTML = '<p class="muted">Relatórios ainda não carregados.</p>';
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
    ["Faturamento líquido", money(summary.net_revenue)],
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
  return `<tr><td class="muted" colspan="${colspan}">Nenhum dado no período.</td></tr>`;
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
            <select class="table-control" data-admin-role="${escapeHTML(user.profile_id)}" aria-label="Papel de ${escapeHTML(user.full_name || user.email)}">
              <option value="staff" ${user.role === "staff" ? "selected" : ""}>Atendente</option>
              <option value="manager" ${user.role === "manager" ? "selected" : ""}>Gerente</option>
              <option value="owner" ${user.role === "owner" ? "selected" : ""}>Proprietário</option>
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
  labelTables();
}

async function collection(path) {
 const items=[];let batch;
 for(let page=1;page<=20;page++) {
   batch=await api(path+(path.includes("?")?"&":"?")+"page="+page+"&page_size=100");
   items.push(...batch);if(batch.length<100)return items;
 }
 showNotice("Exibindo os 2.000 registros mais recentes desta lista. Consulte os relatórios para o histórico completo.");
 return items;
}
async function loadOrders() {
  state.orders = await collection("/api/v1/admin/orders");
  state.orders.sort((a,b)=>{ const done=o=>["delivered","cancelled"].includes(o.status)?1:0;return done(a)-done(b) || new Date(a.placed_at)-new Date(b.placed_at); });
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
  state.products = await collection("/api/v1/admin/products");
}

async function loadCustomers() {
  state.customers = await collection("/api/v1/admin/customers");
}

async function loadPromotions() {
  state.promotions = await collection("/api/v1/admin/promotions");
}

async function loadReports() {
  const params = new URLSearchParams();
  if (state.reportDateFrom) params.set("date_from", state.reportDateFrom);
  if (state.reportDateTo) params.set("date_to", state.reportDateTo);
  const query = params.toString() ? `?${params.toString()}` : "";
  state.reports = await api(`/api/v1/admin/reports${query}`);
}

async function loadAdminUsers() {
  state.adminUsers = await collection("/api/v1/admin/users");
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
  if(!hasAdminCredential()) {setConnectionStatus("Aguardando acesso",false);renderAuthStatus();return;}
  renderAuthStatus();
  setConnectionStatus("Carregando operação…",false);
  const tasks=[["orders",loadOrders],["products",loadProducts],["customers",loadCustomers]];
  if(canManageBusiness())tasks.push(["promotions",loadPromotions],["reports",loadReports]);
  if(canManageTeam())tasks.push(["team",loadAdminUsers],["audit",loadAuditLogs]);
  document.querySelectorAll(".admin-load-notice").forEach(node=>node.remove());
  for(const [name] of tasks) $("#view-"+name).setAttribute("aria-busy","true");
  if(!state.orders.length) $("#orders-queue").innerHTML=LuganoUI.skeleton(2);
  for(const [name,id] of [["products","#products-list"],["promotions","#promotions-list"]]) if(!state[name].length)$(id).innerHTML=LuganoUI.skeleton(2);
  const results=await Promise.allSettled(tasks.map(([,load])=>load()));
  for(const [name] of tasks) $("#view-"+name).removeAttribute("aria-busy");
  if(results.some(r=>r.status==="rejected" && r.reason.status===401)) {
    clearAdminSession();renderAuthStatus();setConnectionStatus("Aguardando login",false);
    showNotice("Sessão administrativa expirada. Entre novamente.","error");return;
  }
  renderAll();
  let failures=0;
  results.forEach((result,i)=>{
    if(result.status!=="rejected")return;failures++;
    const node=document.createElement("div");node.className="notice error admin-load-notice";node.setAttribute("role","alert");
    node.innerHTML='<span>'+escapeHTML(result.reason.message)+'</span> <button class="ghost-button" data-retry-admin>Tentar novamente</button>';
    $("#view-"+tasks[i][0]).prepend(node);
  });
  setConnectionStatus(failures?"Atualização parcial":"Atualizado às "+new Date().toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"}),!failures);
  if(failures)showNotice("Algumas seções não puderam ser atualizadas. Os dados anteriores foram mantidos.","error");
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
    await api("/api/v1/admin/products" + (form.dataset.editId ? "/" + encodeURIComponent(form.dataset.editId) : ""), {
      method: form.dataset.editId ? "PATCH" : "POST",
      body: JSON.stringify(data),
    });
    form.reset();form.closest("dialog")?.close();delete form.dataset.editId;
    showNotice("Produto salvo no catálogo.","success");
    await loadDashboard();
  } catch (error) {
    showNotice(`Não foi possível criar o produto: ${error.message}`, "error");
  }
}

async function createPromotion(event) {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    const data = formData(form);
    data.min_order_cents = Number(data.min_order_cents || 0);
    data.max_uses = data.max_uses ? Number(data.max_uses) : null;
    await api("/api/v1/admin/promotions" + (form.dataset.editId ? "/" + encodeURIComponent(form.dataset.editId) : ""), {
      method: form.dataset.editId ? "PATCH" : "POST",
      body: JSON.stringify(data),
    });
    form.reset();
    form.elements.active.checked = true;
    form.elements.value.value = 0;
    form.elements.min_order_cents.value = 0;
    form.closest("dialog")?.close();delete form.dataset.editId;
    showNotice("Campanha salva.","success");
    await loadDashboard();
  } catch (error) {
    showNotice(`Não foi possível criar a campanha: ${error.message}`, "error");
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
    showNotice("Relatórios atualizados.");
  } catch (error) {
    showNotice(`Não foi possível carregar relatórios: ${error.message}`, "error");
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
    showNotice(`Não foi possível carregar auditoria: ${error.message}`, "error");
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
    showNotice(`Não foi possível salvar o acesso: ${error.message}`, "error");
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
    showNotice(`Não foi possível atualizar o acesso: ${error.message}`, "error");
  }
}

async function saveAdminUser(profileId) {
  const role = $(`[data-admin-role="${profileId}"]`).value;
  const active = $(`[data-admin-active="${profileId}"]`).checked;
  await updateAdminUser(profileId, { role, active });
}

async function disableAdminUser(profileId) {
  if(confirm("Desativar o acesso deste integrante da equipe?")) await updateAdminUser(profileId, { active: false });
}

function selectOrder(orderId) {
  state.selectedOrderId = orderId;
  localStorage.setItem("lugano.admin.selectedOrderId", orderId);
  renderOrders();
  document.body.classList.add("admin-detail-open");
  $("#order-detail").scrollIntoView({block:"start",behavior:"smooth"});
}

async function updateOrder(orderId, updates) {
  try {
    const previous=state.orders.find(o=>o.id===orderId);
    if((updates.status==="cancelled" || (updates.payment_status==="paid" && previous?.payment_status!=="paid") || updates.status==="out_for_delivery" || updates.status==="delivered") && !confirm("Confirmar alteração do pedido #"+shortId(orderId)+"? "+(updates.status==="cancelled" ? "O pedido será cancelado." : updates.payment_status==="paid" && previous?.payment_status!=="paid" ? "Confirme que o pagamento foi recebido. Isso pode acionar preparo e entrega." : "O status de entrega será atualizado.")))return;
    await api(`/api/v1/admin/orders/${orderId}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
    await loadOrders();
    await loadAuditLogsIfAllowed();
    renderAll();
    showNotice("Pedido atualizado.");
  } catch (error) {
    showNotice(`Não foi possível atualizar o pedido: ${error.message}`, "error");
  }
}

async function advanceOrder(orderId) {
 const order=state.orders.find(o=>o.id===orderId),next=orderNextStatus(order);if(!next)return;
 await updateOrder(orderId,{status:next,payment_status:order.payment_status,delivered_at:next==="delivered"?new Date().toISOString():null});
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
      throw new Error("Usuário sem acesso administrativo ativo.");
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
    showNotice(`Não foi possível entrar no admin: ${error.message}`, "error");
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
  showNotice("Sessão administrativa encerrada.");
}

function bindEvents() {
  $$(".nav-tab").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });

  $$("[data-refresh]").forEach((button) => {
    button.addEventListener("click", () => LuganoUI.busy(button,"Atualizando…",loadDashboard));
  });

  $("#refresh-orders").addEventListener("click", async () => {
    await LuganoUI.busy($("#refresh-orders"),"Atualizando…",async()=>{try { await loadOrders(); renderAll(); } catch(error) { showNotice(error.message,"error"); }});
  });
  $("#order-status-filter").addEventListener("change", () => renderOrders());
  $("#product-form").addEventListener("submit", event=>{ event.preventDefault(); LuganoUI.busy(event.currentTarget.querySelector('button[type="submit"]'),"Salvando…",()=>createProduct(event)).catch(error=>showNotice(error.message,"error")); });
  $("#promotion-form").addEventListener("submit", event=>{ event.preventDefault(); LuganoUI.busy(event.currentTarget.querySelector('button[type="submit"]'),"Salvando…",()=>createPromotion(event)).catch(error=>showNotice(error.message,"error")); });
  $("#reports-filter-form").addEventListener("submit", event=>{ event.preventDefault(); LuganoUI.busy(event.currentTarget.querySelector('button[type="submit"]'),"Atualizando…",()=>refreshReports(event)).catch(error=>showNotice(error.message,"error")); });
  $("#audit-filter-form").addEventListener("submit", event=>{ event.preventDefault(); LuganoUI.busy(event.currentTarget.querySelector('button[type="submit"]'),"Atualizando…",()=>refreshAuditLogs(event)).catch(error=>showNotice(error.message,"error")); });
  $("#team-form").addEventListener("submit", event=>{ event.preventDefault(); LuganoUI.busy(event.currentTarget.querySelector('button[type="submit"]'),"Salvando…",()=>createAdminUser(event)).catch(error=>showNotice(error.message,"error")); });
  $("#admin-login-form").addEventListener("submit", event=>{ event.preventDefault(); LuganoUI.busy(event.currentTarget.querySelector('button[type="submit"]'),"Entrando…",()=>loginAdmin(event)).catch(error=>showNotice(error.message,"error")); });
  $("#admin-logout").addEventListener("click", logoutAdmin);

  document.addEventListener("submit", async (event) => {
    if (event.target.matches("#order-update-form")) {
      await LuganoUI.busy(event.target.querySelector('button[type="submit"]'),"Salvando…",()=>saveSelectedOrder(event));
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
      await LuganoUI.busy(orderButton,"Atualizando…",()=>advanceOrder(orderButton.dataset.orderNext));
      return;
    }

    const saveAdminButton = event.target.closest("[data-admin-save]");
    if (saveAdminButton) {
      await LuganoUI.busy(saveAdminButton,"Salvando…",()=>saveAdminUser(saveAdminButton.dataset.adminSave));
      return;
    }

    const disableAdminButton = event.target.closest("[data-admin-disable]");
    if (disableAdminButton) {
      await LuganoUI.busy(disableAdminButton,"Desativando…",()=>disableAdminUser(disableAdminButton.dataset.adminDisable));
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


function orderAge(order) {
 if(["delivered","cancelled"].includes(order.status))return "Concluído";
 const minutes=Math.max(0,Math.floor((Date.now()-new Date(order.placed_at))/60000));
 return minutes<60 ? minutes+" min na fila" : Math.floor(minutes/60)+" h na fila";
}
function labelTables() {
 document.querySelectorAll("table").forEach(table=>{
 const labels=[...table.querySelectorAll("thead th")].map(th=>th.textContent);
 table.querySelectorAll("tbody tr").forEach(row=>[...row.cells].forEach((cell,i)=>cell.dataset.label=labels[i] || ""));
 });
}
function openEditor(kind,id,trigger) {
 if(!canManageBusiness())return;
 const form=$("#"+(kind==="product"?"product":"promotion")+"-form");
 form.reset();delete form.dataset.editId;
 const item=(kind==="product"?state.products:state.promotions).find(p=>p.id===id);
 if(item){form.dataset.editId=id;for(const input of form.elements){if(!input.name)continue;if(input.type==="checkbox")input.checked=Boolean(item[input.name]);else input.value=item[input.name] ?? "";}}
 if(kind==="product") {const preview=form.querySelector('img[alt="Prévia da imagem"]'),url=safeHttpUrl(form.elements.image_url.value);preview.hidden=!url;if(url)preview.src=LuganoUI.media(url);}
 form.querySelector("h2").textContent=(item?"Editar ":"Novo ")+(kind==="product"?"produto":"campanha");
 LuganoUI.openDialog(form.closest("dialog"),trigger);
}
function filteredCollection(kind,items) {
 const q=($("#"+kind+"-search")?.value || "").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
 return items.filter(item=>[item.name,item.code,item.full_name,item.email,item.category,item.description].join(" ").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().includes(q));
}
function setupAdminUX() {
 document.addEventListener('submit', saveInlineProductPrice);
 for(const [kind,container,render] of [["products","#products-list",renderProducts],["customers","#customers-table",renderCustomers],["promotions","#promotions-list",renderPromotions]]) {
 const input=document.createElement("input"); input.id=kind+"-search";input.type="search";input.className="admin-collection-search";input.placeholder="Buscar nesta lista";input.setAttribute("aria-label","Buscar nesta lista");
 input.value=localStorage.getItem("lugano.admin.search."+kind) || "";
 const host=$(container); (host.closest(".table-wrap") || host).before(input);
 input.oninput=()=>{localStorage.setItem("lugano.admin.search."+kind,input.value);render();labelTables();};
 }

 const status=$("#order-status-filter");status.value=localStorage.getItem("lugano.admin.orderFilter") || "";
 status.addEventListener("change",()=>localStorage.setItem("lugano.admin.orderFilter",status.value));
 const search=document.createElement("input");search.id="order-search";search.type="search";search.placeholder="Buscar pedido ou cliente";search.setAttribute("aria-label","Buscar pedido ou cliente");search.className="admin-search";
 $(".orders-workbench").before(search);search.addEventListener("input",renderOrders);
 for(const kind of ["product","promotion"]) {
 const form=$("#"+kind+"-form"), dialog=document.createElement("dialog");
 dialog.setAttribute("aria-label",kind==="product"?"Editar produto":"Editar campanha");
 const button=document.createElement("button");button.type="button";button.className="primary-button editor-toggle";button.dataset.minRole="manager";button.textContent=kind==="product"?"Novo produto":"Nova campanha";
 form.before(button);button.onclick=()=>openEditor(kind,null,button);
 const close=document.createElement("button");close.type="button";close.className="ghost-button";close.textContent="Fechar";close.onclick=()=>dialog.close();
 dialog.append(close,form);document.body.append(dialog);dialog.addEventListener("close",()=>dialog._trigger?.focus());
 }
 const imageInput=$("#product-form").elements.image_url, preview=document.createElement("img");
 preview.width=120;preview.height=90;preview.alt="Prévia da imagem";preview.hidden=true;imageInput.after(preview);
 imageInput.addEventListener("input",()=>{const url=safeHttpUrl(imageInput.value);preview.hidden=!url;if(url)preview.src=url;});
 document.addEventListener("click",event=>{
 const b=event.target.closest("button");if(!b)return;
 if(b.hasAttribute("data-retry-admin")){LuganoUI.busy(b,"Atualizando…",loadDashboard);return;}
 if(b.id==="back-to-queue"){document.body.classList.remove("admin-detail-open");return;}
 if(b.dataset.statusFilter){status.value=b.dataset.statusFilter;status.dispatchEvent(new Event("change"));return;}
 if(b.hasAttribute("data-edit-product"))openEditor("product",b.dataset.editProduct,b);
 if(b.hasAttribute("data-edit-promotion"))openEditor("promotion",b.dataset.editPromotion,b);
 if(b.hasAttribute("data-edit-customer"))editCustomer(b.dataset.editCustomer,b);
 });
 setView(localStorage.getItem("lugano.admin.view") in titles ? localStorage.getItem("lugano.admin.view") : "orders");
}
async function editCustomer(id,trigger) {
 if(!canManageBusiness())return;
 const customer=state.customers.find(c=>c.id===id);if(!customer)return;
 const dialog=document.createElement("dialog");dialog.setAttribute("aria-label","Editar cliente");
 dialog.innerHTML='<form><h2>Editar cliente</h2><label>Nome<input name="full_name" value="'+escapeHTML(customer.full_name)+'"></label><label>Email<input name="email" type="email" value="'+escapeHTML(customer.email)+'"></label><label>Telefone<input name="phone" type="tel" value="'+escapeHTML(customer.phone)+'"></label><div class="dialog-actions"><button class="ghost-button" type="button">Cancelar</button><button class="primary-button" type="submit">Salvar</button></div></form>';
 document.body.append(dialog);dialog.querySelector('[type="button"]').onclick=()=>dialog.close();
 dialog.addEventListener("close",()=>{trigger.focus();dialog.remove();});
 dialog.querySelector("form").onsubmit=event=>{event.preventDefault();const form=event.currentTarget;LuganoUI.busy(form.querySelector('[type="submit"]'),"Salvando…",async()=>{try{await api("/api/v1/admin/customers/"+encodeURIComponent(id),{method:"PATCH",body:JSON.stringify(formData(form))});await loadCustomers();renderCustomers();labelTables();dialog.close();showNotice("Cliente atualizado.","success");}catch(error){showNotice(error.message,"error");}});};
 LuganoUI.openDialog(dialog,trigger);
}

setupAdminUX();
bindEvents();
hydrateSettings();
loadDashboard();
