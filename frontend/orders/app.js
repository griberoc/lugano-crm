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
  products: [],
  cart: JSON.parse(localStorage.getItem("lugano.customer.cart") || "[]"),
  addresses: [],
  promotion: null,
  quote: null,
  lastOrder: null,
  isSubmitting: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const paymentLabels = {
  pix: "Pix",
  credit_card: "Cartao de credito",
  debit_card: "Cartao de debito",
  cash: "Dinheiro",
};

const orderStatusLabels = {
  pending: "Pedido recebido",
  confirmed: "Confirmado",
  preparing: "Em preparo",
  out_for_delivery: "Saiu para entrega",
  delivered: "Entregue",
  cancelled: "Cancelado",
};

const paymentStatusLabels = {
  pending: "Pagamento pendente",
  paid: "Pago",
  failed: "Falhou",
  refunded: "Reembolsado",
};

function money(value) {
  return Number(value || 0).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function moneyCents(value) {
  return money(Number(value || 0) / 100);
}

function cartSubtotalCents() {
  return Math.round(cartSubtotal() * 100);
}

function promotionDiscountCents() {
  return state.promotion?.discount || 0;
}

function deliveryFeeCents() {
  return state.quote?.delivery_fee_cents || 0;
}

function orderTotalCents() {
  return Math.max(0, cartSubtotalCents() + deliveryFeeCents() - promotionDiscountCents());
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

function saveState() {
  localStorage.setItem("lugano.customer.cart", JSON.stringify(state.cart));
  localStorage.setItem("lugano.customer.session", JSON.stringify(state.session));
}

function cartSubtotal() {
  return state.cart.reduce((total, item) => total + item.price * item.quantity, 0);
}

function cartQuantity() {
  return state.cart.reduce((total, item) => total + item.quantity, 0);
}

function categories() {
  return [...new Set(state.products.map((product) => product.category))].sort();
}

function selectedAddress() {
  const addressId = $("#address-select")?.value;
  return state.addresses.find((address) => address.id === addressId) || null;
}

function formatAddress(address) {
  if (!address) return "Selecione ou cadastre um endereco para entrega.";
  return `${address.label}: ${address.street}, ${address.number} - ${address.neighborhood}, ${address.city} (${address.zip_code})`;
}

function selectedPaymentLabel() {
  return paymentLabels[$("#payment-method")?.value] || "Pix";
}

function shortId(id) {
  return id ? String(id).slice(0, 8) : "-";
}

function renderSession() {
  const email = state.session?.user?.email;
  $("#session-label").textContent = email || "Visitante";
  $("#logout-button").classList.toggle("hidden", !state.session);
  $("#auth-summary").textContent = email
    ? `Conta conectada: ${email}`
    : "Entre pela rota Acesso antes de finalizar o pedido.";
}

function renderCategoryFilter() {
  const current = $("#category-filter").value;
  $("#category-filter").innerHTML = [
    '<option value="">Todas as categorias</option>',
    ...categories().map((category) => `<option value="${category}">${category}</option>`),
  ].join("");
  $("#category-filter").value = current;
}

function renderProducts() {
  const category = $("#category-filter").value;
  const products = category
    ? state.products.filter((product) => product.category === category)
    : state.products;

  $("#product-grid").innerHTML = products
    .map(
      (product) => `
        <article class="product-card">
          <span class="muted">${product.category}</span>
          <strong>${product.name}</strong>
          <p>${product.description || ""}</p>
          <span class="product-price">${money(product.price)}</span>
          <button class="primary-button" data-add-product="${product.id}" type="button">
            Adicionar ao pedido
          </button>
        </article>
      `,
    )
    .join("");
}

function renderCart() {
  $("#cart-count").textContent = `${cartQuantity()} itens`;
  $("#cart-list").innerHTML = state.cart.length
    ? state.cart
        .map(
          (item) => `
            <article class="cart-item">
              <div class="cart-row">
                <strong>${item.name}</strong>
                <div class="quantity-actions">
                  <button class="small-button" data-decrease-product="${item.id}" type="button">-</button>
                  <span>${item.quantity}</span>
                  <button class="small-button" data-add-product="${item.id}" type="button">+</button>
                  <button class="small-button" data-remove-product="${item.id}" type="button">Remover</button>
                </div>
              </div>
              <div class="cart-row">
                <span>${item.quantity} x ${money(item.price)}</span>
                <strong>${money(item.quantity * item.price)}</strong>
              </div>
            </article>
          `,
        )
        .join("")
    : '<p class="muted">Seu pedido ainda esta vazio.</p>';

  $("#cart-subtotal").textContent = moneyCents(cartSubtotalCents());
  $("#cart-delivery").textContent = moneyCents(deliveryFeeCents());
  $("#cart-discount").textContent = moneyCents(promotionDiscountCents());
  $("#cart-total").textContent = moneyCents(orderTotalCents());

  const amountToFreeDelivery = state.quote?.amount_to_free_delivery_cents || 0;
  if (!state.cart.length) {
    $("#free-delivery-hint").textContent = "Monte seu pedido para calcular entrega.";
  } else if (deliveryFeeCents() === 0) {
    $("#free-delivery-hint").textContent = "Entrega gratis aplicada ao pedido.";
  } else {
    $("#free-delivery-hint").textContent = `Faltam ${moneyCents(amountToFreeDelivery)} para entrega gratis.`;
  }
}

function renderAddresses() {
  const selectedId = $("#address-select").value;
  $("#address-select").innerHTML = state.addresses.length
    ? state.addresses
        .map(
          (address) => `
            <option value="${address.id}">
              ${address.label} - ${address.street}, ${address.number}
            </option>
          `,
        )
        .join("")
    : '<option value="">Cadastre um endereço</option>';
  if (selectedId && state.addresses.some((address) => address.id === selectedId)) {
    $("#address-select").value = selectedId;
  }
  $("#address-summary").textContent = formatAddress(selectedAddress());
}

function renderCheckoutDetails() {
  $("#payment-summary").textContent = `Pagamento via ${selectedPaymentLabel()}.`;
  if (state.promotion?.valid) {
    const deliveryText = state.promotion.type === "free_delivery"
      ? "Entrega gratis"
      : `${moneyCents(state.promotion.discount)} de desconto`;
    $("#promotion-summary").textContent = `${state.promotion.description} (${deliveryText}).`;
  } else {
    $("#promotion-summary").textContent = "Nenhum cupom aplicado.";
  }
}

function renderLastOrder() {
  const panel = $("#last-order-panel");
  if (!state.lastOrder) {
    panel.classList.add("hidden");
    return;
  }

  const order = state.lastOrder;
  panel.classList.remove("hidden");
  $("#last-order-status").className = `status ${order.status}`;
  $("#last-order-status").textContent = orderStatusLabels[order.status] || order.status;
  $("#last-order-title").textContent = `Pedido #${shortId(order.id)}`;
  $("#last-order-summary").textContent = `${paymentStatusLabels[order.payment_status] || order.payment_status} - Total ${money(order.total)} - Entrega estimada 25-40 min.`;
  renderPaymentInstructions(order.payment_instructions);

  const steps = ["pending", "confirmed", "preparing", "out_for_delivery", "delivered"];
  const activeIndex = Math.max(0, steps.indexOf(order.status));
  $("#order-progress").innerHTML = steps
    .map(
      (status, index) => `
        <div class="progress-step ${index <= activeIndex ? "active" : ""}">
          <span></span>
          <strong>${orderStatusLabels[status]}</strong>
        </div>
      `,
    )
    .join("");
}

function renderPaymentInstructions(instructions) {
  const panel = $("#payment-instructions");
  const pixBox = $("#pix-copy-box");
  const pixCode = instructions?.pix_copy_paste || "";

  if (!instructions) {
    panel.classList.add("hidden");
    return;
  }

  panel.classList.remove("hidden");
  $("#payment-instructions-title").textContent = instructions.title || "Pagamento";
  $("#payment-instructions-description").textContent = instructions.description || "";
  pixBox.classList.toggle("hidden", !pixCode);
  $("#pix-copy-paste").value = pixCode;
}

async function copyPixCode() {
  const code = $("#pix-copy-paste").value;
  if (!code) return;
  try {
    await navigator.clipboard.writeText(code);
    showNotice("Codigo Pix copiado.", "success");
  } catch {
    $("#pix-copy-paste").select();
    showNotice("Selecione e copie o codigo Pix.", "error");
  }
}

function renderAll() {
  renderSession();
  renderCategoryFilter();
  renderProducts();
  renderCart();
  renderAddresses();
  renderCheckoutDetails();
  renderLastOrder();
}

async function loadProducts() {
  state.products = await api("/api/v1/catalog/products");
  renderAll();
}

async function loadCustomerData() {
  if (!state.session) return;
  const addresses = await api("/api/v1/me/addresses");
  state.addresses = addresses;
  renderAll();
}

async function refreshQuote() {
  if (!state.cart.length) {
    state.quote = {
      subtotal_cents: 0,
      delivery_fee_cents: 0,
      free_delivery_threshold_cents: 0,
      amount_to_free_delivery_cents: 0,
    };
    renderCart();
    return;
  }

  state.quote = await api("/api/v1/orders/quote", {
    method: "POST",
    body: JSON.stringify({
      subtotal_cents: cartSubtotalCents(),
      free_delivery: state.promotion?.type === "free_delivery",
    }),
  });
  renderCart();
}

function logout() {
  state.session = null;
  state.addresses = [];
  state.promotion = null;
  state.quote = null;
  state.lastOrder = null;
  saveState();
  renderAll();
}

function addToCart(productId) {
  const product = state.products.find((item) => item.id === productId);
  if (!product) return;
  const existing = state.cart.find((item) => item.id === productId);
  if (existing) {
    existing.quantity += 1;
  } else {
    state.cart.push({
      id: product.id,
      name: product.name,
      price: Number(product.price),
      quantity: 1,
    });
  }
  saveState();
  renderCart();
  refreshQuote().catch((error) => showNotice(error.message, "error"));
}

function decreaseCartItem(productId) {
  const existing = state.cart.find((item) => item.id === productId);
  if (!existing) return;
  existing.quantity -= 1;
  if (existing.quantity <= 0) {
    state.cart = state.cart.filter((item) => item.id !== productId);
  }
  saveState();
  renderCart();
  refreshQuote().catch((error) => showNotice(error.message, "error"));
}

function removeFromCart(productId) {
  state.cart = state.cart.filter((item) => item.id !== productId);
  if (!state.cart.length) state.promotion = null;
  saveState();
  renderCart();
  refreshQuote().catch((error) => showNotice(error.message, "error"));
}

async function saveAddress(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!state.session) {
    showNotice("Entre antes de salvar endereço.", "error");
    return;
  }
  try {
    await api("/api/v1/me/addresses", {
      method: "POST",
      body: JSON.stringify(formData(form)),
    });
    form.reset();
    await loadCustomerData();
    showNotice("Endereco salvo e selecionado para entrega.", "success");
  } catch (error) {
    showNotice(`Nao foi possivel salvar o endereco: ${error.message}`, "error");
  }
}

async function validatePromotion() {
  if (!state.session) {
    showNotice("Entre antes de aplicar cupom.", "error");
    return;
  }
  const code = $("#promotion-code").value.trim();
  if (!code) return;
  if (!state.cart.length) {
    showNotice("Adicione produtos antes de aplicar cupom.", "error");
    return;
  }
  try {
    const result = await api("/api/v1/promotions/validate", {
      method: "POST",
      body: JSON.stringify({
        code,
        order_subtotal: cartSubtotalCents(),
      }),
    });
    state.promotion = result.valid ? result : null;
    await refreshQuote();
    renderAll();
    showNotice(
      result.description || "Cupom validado.",
      result.valid ? "success" : "error",
    );
  } catch (error) {
    state.promotion = null;
    await refreshQuote();
    renderAll();
    showNotice(`Nao foi possivel aplicar o cupom: ${error.message}`, "error");
  }
}

async function clearPromotion() {
  state.promotion = null;
  $("#promotion-code").value = "";
  await refreshQuote();
  renderAll();
  showNotice("Cupom removido.");
}

async function checkout() {
  openOrderConfirmation();
}

function validateCheckout() {
  if (!state.session) {
    showNotice("Entre antes de finalizar.", "error");
    return false;
  }
  if (!state.cart.length) {
    showNotice("Adicione produtos ao pedido.", "error");
    return false;
  }
  const addressId = $("#address-select").value;
  if (!addressId) {
    showNotice("Cadastre um endereço.", "error");
    return false;
  }
  return true;
}

function openOrderConfirmation() {
  if (!validateCheckout()) return;

  $("#confirm-summary").innerHTML = `
    <div><span>Entrega</span><strong>${formatAddress(selectedAddress())}</strong></div>
    <div><span>Pagamento</span><strong>${selectedPaymentLabel()}</strong></div>
    <div><span>Itens</span><strong>${cartQuantity()} item(ns)</strong></div>
    <div><span>Subtotal</span><strong>${moneyCents(cartSubtotalCents())}</strong></div>
    <div><span>Entrega</span><strong>${moneyCents(deliveryFeeCents())}</strong></div>
    <div><span>Desconto</span><strong>${moneyCents(promotionDiscountCents())}</strong></div>
    <div class="grand-total"><span>Total</span><strong>${moneyCents(orderTotalCents())}</strong></div>
  `;
  $("#confirm-dialog").classList.remove("hidden");
}

function closeOrderConfirmation() {
  $("#confirm-dialog").classList.add("hidden");
}

async function submitOrder() {
  if (!validateCheckout() || state.isSubmitting) return;
  state.isSubmitting = true;
  $("#confirm-order").disabled = true;
  $("#checkout-button").disabled = true;

  try {
    const order = await api("/api/v1/orders/", {
      method: "POST",
      body: JSON.stringify({
        address_id: $("#address-select").value,
        payment_method: $("#payment-method").value,
        promotion_code: $("#promotion-code").value.trim() || null,
        notes: $("#order-notes").value || null,
        items: state.cart.map((item) => ({
          product_id: item.id,
          quantity: item.quantity,
        })),
      }),
    });

    state.lastOrder = order;
    state.cart = [];
    state.promotion = null;
    state.quote = null;
    $("#promotion-code").value = "";
    $("#order-notes").value = "";
    saveState();
    closeOrderConfirmation();
    await loadCustomerData();
    await refreshQuote();
    renderAll();
    showNotice("Pedido enviado com sucesso. Acompanhe o status abaixo e no painel do cliente.", "success");
  } catch (error) {
    showNotice(`Nao foi possivel enviar o pedido: ${error.message}`, "error");
  } finally {
    state.isSubmitting = false;
    $("#confirm-order").disabled = false;
    $("#checkout-button").disabled = false;
  }
}

function bindEvents() {
  $("#logout-button").addEventListener("click", logout);
  $("#refresh-products").addEventListener("click", loadProducts);
  $("#category-filter").addEventListener("change", renderProducts);
  $("#address-select").addEventListener("change", renderAddresses);
  $("#payment-method").addEventListener("change", renderCheckoutDetails);
  $("#address-form").addEventListener("submit", saveAddress);
  $("#validate-promotion").addEventListener("click", validatePromotion);
  $("#clear-promotion").addEventListener("click", clearPromotion);
  $("#checkout-button").addEventListener("click", checkout);
  $("#cancel-confirmation").addEventListener("click", closeOrderConfirmation);
  $("#confirm-order").addEventListener("click", submitOrder);
  $("#copy-pix").addEventListener("click", copyPixCode);

  document.addEventListener("click", (event) => {
    const addButton = event.target.closest("[data-add-product]");
    const decreaseButton = event.target.closest("[data-decrease-product]");
    const removeButton = event.target.closest("[data-remove-product]");
    if (addButton) addToCart(addButton.dataset.addProduct);
    if (decreaseButton) decreaseCartItem(decreaseButton.dataset.decreaseProduct);
    if (removeButton) removeFromCart(removeButton.dataset.removeProduct);
  });
}

bindEvents();
renderAll();
loadProducts().catch((error) => showNotice(error.message, "error"));
loadCustomerData().catch((error) => showNotice(error.message, "error"));
refreshQuote().catch((error) => showNotice(error.message, "error"));
