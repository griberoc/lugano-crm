const runtimeConfig = window.LUGANO_CONFIG || {};
const DEFAULT_API_URL = runtimeConfig.apiBaseUrl || "http://127.0.0.1:8000";

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
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
const DEFAULT_SUPABASE_URL = runtimeConfig.supabaseUrl || "";
const DEFAULT_SUPABASE_ANON_KEY = runtimeConfig.supabaseAnonKey || "";
const RETURN_AFTER_LOGIN_KEY = "lugano.customer.returnAfterLogin";

function clearLegacyTechnicalConfig() {
  localStorage.removeItem("lugano.customer.apiBaseUrl");
  localStorage.removeItem("lugano.customer.supabaseUrl");
  localStorage.removeItem("lugano.customer.supabaseAnonKey");
}

clearLegacyTechnicalConfig();

const storedCart = LuganoUI.read("lugano.customer.cart", []);
const state = {
  apiBaseUrl: DEFAULT_API_URL,
  supabaseUrl: DEFAULT_SUPABASE_URL,
  supabaseAnonKey: DEFAULT_SUPABASE_ANON_KEY,
  session: LuganoUI.read("lugano.customer.session"),
  products: [],
  productsLoaded: false,
  quoteSequence: 0,
  quoteLoading: false,
  activeStep: sessionStorage.getItem("lugano.checkout.step") || "cart",
  detailProduct: null,
  undoCart: null,
  cart: Array.isArray(storedCart) ? storedCart.filter(i => i && typeof i.id === "string" && Number.isInteger(i.quantity) && i.quantity > 0 && i.quantity <= 99 && Number.isFinite(i.price) && i.price >= 0) : [],
  addresses: [],
  promotion: null,
  quote: null,
  lastOrder: null,
  restoreError: null,
  isSubmitting: false,
  paymentPollId: null,
  paymentPollAttempts: 0,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const paymentLabels = {
  pix: "Pix",
  credit_card: "Cartão de crédito",
  debit_card: "Cartão de débito",
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

function showNotice(message, type = "info") { LuganoUI.notice($("#notice"), message, type); LuganoUI.toast(message, type); if(type === "error") LuganoUI.track("checkout_error"); }

function authHeaders() {
  return state.session?.access_token
    ? { Authorization: `Bearer ${state.session.access_token}` }
    : {};
}

async function api(path, options = {}) {
 try { return await LuganoUI.request(state.apiBaseUrl + path, { ...options, headers: { "Content-Type": "application/json", ...authHeaders(), ...(options.headers || {}) } }); }
 catch(error) { if(error.status===401 && state.session) {
   state.session=null;state.addresses=[];localStorage.removeItem("lugano.customer.session");
   rememberDeliveryReturn();renderSession();renderAddresses();goToStep("step-account");
 } throw error; }
}

function formData(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  Object.keys(data).forEach((key) => {
    if (data[key] === "") data[key] = null;
  });
  return data;
}

function saveState() { localStorage.setItem("lugano.customer.cart", JSON.stringify(state.cart)); }

function rememberDeliveryReturn() {
  localStorage.setItem(RETURN_AFTER_LOGIN_KEY, "delivery");
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
  if (!address) return "Selecione ou cadastre um endereço para entrega.";
  return `${address.label}: ${address.street}, ${address.number} - ${address.neighborhood}, ${address.city} (${address.zip_code})`;
}

function selectedPaymentLabel() {
  return paymentLabels[$("#payment-method")?.value] || "Pix";
}

function checkoutStepStatus() {
  const hasCart = cartQuantity() > 0;
  const hasAccount = Boolean(state.session);
  const hasDelivery = Boolean(selectedAddress());
  let active = "cart";

  if (hasCart && !hasAccount) active = "account";
  if (hasCart && hasAccount && !hasDelivery) active = "delivery";
  if (hasCart && hasAccount && hasDelivery) active = "payment";

  return {
    active,
    complete: {
      cart: hasCart,
      account: hasAccount,
      delivery: hasDelivery,
      payment: false,
    },
  };
}

function setStepClasses(baseId, step, status) {
  const element = $(`#${baseId}-${step}`);
  if (!element) return;
  element.classList.toggle("active", status.active === step);
  element.classList.toggle("complete", Boolean(status.complete[step]));
  element.classList.toggle("locked", !status.complete[step] && status.active !== step);
}

function renderCheckoutProgress() {
  if (state.activeStep === "account" && state.session) state.activeStep = "delivery";
  if (!state.cart.length) state.activeStep = "cart";
  if (!state.session && ["delivery", "payment"].includes(state.activeStep)) state.activeStep = "account";
  ["cart","account","delivery","payment"].forEach(step => {
    $("#step-"+step)?.classList.toggle("is-current", state.activeStep === step);
    $("#flow-"+step)?.classList.toggle("active", state.activeStep === step);
    $("#flow-"+step)?.setAttribute("aria-current", state.activeStep === step ? "step" : "false");
  });
  sessionStorage.setItem("lugano.checkout.step", state.activeStep);
  $("#mobile-cart").classList.toggle("hidden", !state.cart.length);
  $("#mobile-cart-total").textContent = cartQuantity() + (cartQuantity() === 1 ? " item · " : " itens · ") + money(cartSubtotal());
}

function updateFloatingAccessButton() { /* Cart is the single mobile floating action. */ }

function goToStep(stepId) {
  let step = stepId.replace("step-","");
  if (step !== "cart" && !state.cart.length) return showNotice("Adicione um produto para continuar.", "error");
  if (step === "account" && state.session) step = "delivery";
  if (["delivery","payment"].includes(step) && !state.session) step = "account";
  if (step === "payment" && !selectedAddress()) return showNotice("Selecione ou cadastre um endereço.", "error");
  state.activeStep = step; document.body.classList.add("checkout-open"); renderCheckoutProgress();
  LuganoUI.track("checkout_step_viewed");
  const panel = $("#step-"+step); panel.scrollIntoView({block:"start",behavior:"smooth"});
  panel.querySelector("h2")?.setAttribute("tabindex","-1"); panel.querySelector("h2")?.focus({preventScroll:true});
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
  $("#category-filter").innerHTML = '<option value="">Todas as categorias</option>' + categories().map(c => '<option value="'+escapeHTML(c)+'">'+escapeHTML(c)+'</option>').join("");
  $("#category-filter").value = current;
  $("#category-tabs").innerHTML = ["",...categories()].map(c => '<button type="button" data-category="'+escapeHTML(c)+'" aria-pressed="'+(c === current)+'">'+escapeHTML(c || "Todos")+'</button>').join("");
}

function renderProducts() {
  if (!state.productsLoaded) { $("#product-grid").innerHTML = LuganoUI.skeleton(4); return; }
  const normalize = text => String(text || "").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
  const query = normalize($("#product-search").value);
  const products = state.products.filter(p => (!$("#category-filter").value || p.category === $("#category-filter").value) && normalize(p.name+" "+p.description).includes(query));
  $("#product-grid").innerHTML = products.length ? products.map(product => {
    const imageUrl = LuganoUI.media(safeHttpUrl(product.image_url));
    const media = imageUrl ? '<figure class="product-media"><img src="'+escapeHTML(imageUrl)+'" width="400" height="300" alt="'+escapeHTML(product.name)+'" loading="lazy" decoding="async"></figure>' : '<figure class="product-media product-media-fallback"><img src="../assets/lugano-logo-mark.svg" width="64" height="64" alt=""></figure>';
    return '<article class="product-card has-image"><button class="product-detail-trigger" data-product-detail="'+escapeHTML(product.id)+'" aria-label="Ver detalhes de '+escapeHTML(product.name)+'">'+media+'</button><div class="product-body"><small>'+escapeHTML(product.category)+'</small><button class="product-name" data-product-detail="'+escapeHTML(product.id)+'">'+escapeHTML(product.name)+'</button><p>'+escapeHTML(product.description || "Um sabor especial para a sua pausa.")+'</p><div class="product-buy"><span class="product-price">'+money(product.price)+'</span><button class="primary-button" data-add-product="'+escapeHTML(product.id)+'" type="button" '+(product.available === false ? "disabled":"")+'>'+(product.available === false ? "Indisponível" : "Adicionar")+'</button></div></div></article>';
  }).join("") : LuganoUI.empty("Nenhum produto encontrado", query ? "Tente outro nome ou escolha uma categoria diferente." : "O cardápio está sendo preparado. Volte em breve.");
}

function renderCart() {
  $("#cart-count").textContent = cartQuantity() + (cartQuantity() === 1 ? " item" : " itens");
  $("#cart-list").innerHTML = state.cart.length ? state.cart.map((item,index) => '<article class="cart-item"><div class="cart-row"><strong>'+escapeHTML(item.name)+'</strong><strong>'+money(item.quantity*item.price)+'</strong></div>'+(item.customization ? '<p>'+escapeHTML(item.customization)+'</p>':'')+'<div class="quantity-actions"><button class="small-button" data-cart-change="'+index+'" data-delta="-1" aria-label="Diminuir '+escapeHTML(item.name)+'">−</button><span aria-live="polite">'+item.quantity+'</span><button class="small-button" data-cart-change="'+index+'" data-delta="1" aria-label="Aumentar '+escapeHTML(item.name)+'">+</button><button class="small-button" data-cart-remove="'+index+'">Remover</button></div></article>').join("") : LuganoUI.empty("Sua pausa começa aqui", "Escolha algo do cardápio para montar seu pedido.");
  $("#cart-subtotal").textContent = moneyCents(cartSubtotalCents());
  $("#cart-delivery").textContent = state.quoteLoading ? "Calculando…" : state.quote ? moneyCents(deliveryFeeCents()) : "A calcular";
  $("#cart-discount").textContent = moneyCents(promotionDiscountCents());
  $("#cart-total").textContent = state.quote ? moneyCents(orderTotalCents()) : money(cartSubtotal());
  $("#free-delivery-hint").textContent = !state.cart.length ? "O frete aparece quando você adicionar um produto." : !state.quote ? "Recalcule o frete antes de finalizar." : deliveryFeeCents() === 0 ? "Entrega grátis aplicada." : state.quote.amount_to_free_delivery_cents > 0 ? "Faltam "+moneyCents(state.quote.amount_to_free_delivery_cents)+" para entrega grátis." : "Frete estimado. Confira o total na revisão.";
  $("#retry-quote").classList.toggle("hidden", !state.cart.length || Boolean(state.quote) || state.quoteLoading);
  renderCheckoutProgress();
}

function renderAddresses() {
  const selectedId = $("#address-select").value;
  $("#address-select").innerHTML = state.addresses.length
    ? state.addresses
        .map(
          (address) => `
            <option value="${escapeHTML(address.id)}">
              ${escapeHTML(address.label)} - ${escapeHTML(address.street)}, ${escapeHTML(address.number)}
            </option>
          `,
        )
        .join("")
    : '<option value="">Cadastre um endereço</option>';
  if (selectedId && state.addresses.some((address) => address.id === selectedId)) {
    $("#address-select").value = selectedId;
  }
  $("#address-summary").textContent = formatAddress(selectedAddress());
  renderCheckoutProgress();
}

function renderCheckoutDetails() {
  $("#payment-summary").textContent = `Pagamento via ${selectedPaymentLabel()}.`;
  if (state.promotion?.valid) {
    const deliveryText = state.promotion.type === "free_delivery"
      ? "Entrega grátis"
      : `${moneyCents(state.promotion.discount)} de desconto`;
    $("#promotion-summary").textContent = `${state.promotion.description} (${deliveryText}).`;
  } else {
    $("#promotion-summary").textContent = "Nenhum cupom aplicado.";
  }
}

function renderLastOrder() {
  const panel = $("#last-order-panel");
  if(state.restoreError) {
    panel.classList.remove("hidden");
    $("#last-order-title").textContent="Pedido #"+shortId(state.restoreError);
    $("#last-order-status").textContent="Consulta indisponível";
    $("#last-order-summary").textContent="Seu pedido já foi registrado. Não envie novamente. Atualize para consultar o status.";
    $("#payment-instructions").classList.add("hidden"); $("#order-progress").textContent="";return;
  }
  if (!state.lastOrder) {
    panel.classList.add("hidden");
    return;
  }

  const order = state.lastOrder;
  panel.classList.remove("hidden");
  $("#last-order-status").className = `status ${order.status}`;
  $("#last-order-status").textContent = orderStatusLabels[order.status] || order.status;
  $("#last-order-title").textContent = `Pedido #${shortId(order.id)}`;
  $("#last-order-summary").textContent = `${paymentStatusLabels[order.payment_status] || order.payment_status} - Total ${money(order.total)}.`;
  renderPaymentInstructions(order.payment_instructions ? {...order.payment_instructions,status:order.payment_status} : null, order.status);
  updatePaymentPolling(order);

  const steps = ["pending", "confirmed", "preparing", "out_for_delivery", "delivered"];
  const activeIndex = steps.indexOf(order.status);
  if(order.status === "cancelled") { $("#order-progress").textContent = "Este pedido foi cancelado."; return; }
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

function renderPaymentInstructions(instructions, orderStatus) {
  const panel = $("#payment-instructions");
  const pixBox = $("#pix-copy-box");
  const mercadoPagoBox = $("#mp-payment-box");
  const paymentUrl = $("#payment-url");
  const qrImage = $("#pix-qr-code");
  const pixCode = instructions?.pix_copy_paste || "";
  const qrBase64 = instructions?.pix_qr_code_base64 || "";
  const ticketUrl = safeHttpUrl(instructions?.payment_url || "");
  const liveStatus = $("#payment-live-status");

  if (!instructions) {
    panel.classList.add("hidden");
    return;
  }

  const expired=instructions.expires_at && new Date(instructions.expires_at).getTime()<=Date.now();
  const payable=instructions.status==="pending" && orderStatus!=="cancelled" && !expired;
  panel.classList.remove("hidden");
  $("#payment-instructions-title").textContent = instructions.title || "Pagamento";
  $("#payment-instructions-description").textContent = instructions.description || "";
  liveStatus.textContent = instructions.status === "pending"
    ? "Aguardando a confirmação segura do pagamento..."
    : paymentStatusLabels[instructions.status] || "Status atualizado";
  if(expired && instructions.status==="pending") liveStatus.textContent="Este código expirou. Não faça o pagamento. Fale com a loja para conferir o pedido e solicitar orientação.";
  if(orderStatus==="cancelled") liveStatus.textContent="Pedido cancelado. Não realize o pagamento.";
  pixBox.classList.toggle("hidden", !pixCode || !payable);
  $("#pix-copy-paste").value = pixCode;

  mercadoPagoBox.classList.toggle("hidden", (!qrBase64 && !ticketUrl) || !payable);
  qrImage.classList.toggle("hidden", !qrBase64);
  if (qrBase64) {
    qrImage.src = qrBase64.startsWith("data:image/png;base64,")
      ? qrBase64
      : `data:image/png;base64,${qrBase64}`;
  } else {
    qrImage.removeAttribute("src");
  }

  paymentUrl.classList.toggle("hidden", !ticketUrl || !payable);
  if (ticketUrl) {
    paymentUrl.href = ticketUrl;
  } else {
    paymentUrl.removeAttribute("href");
  }
}

function stopPaymentPolling() {
  if (state.paymentPollId) window.clearTimeout(state.paymentPollId);
  state.paymentPollId = null;
  state.paymentPollAttempts = 0;
}

function updatePaymentPolling(order) {
  if (!order || ["delivered", "cancelled"].includes(order.status)) {
    stopPaymentPolling();
    return;
  }
  if (state.paymentPollId || state.paymentPollAttempts >= 60) return;
  state.paymentPollId = window.setTimeout(refreshPendingPayment, 5000);
}

async function refreshPendingPayment() {
  state.paymentPollId = null;
  if (!state.session) return;
  if(!state.lastOrder) { await restoreOrder(); return; }
  state.paymentPollAttempts += 1;
  try {
    const order = await api(`/api/v1/orders/${encodeURIComponent(state.lastOrder.id)}`);
    if(order.payment_status === "paid" && state.lastOrder?.payment_status !== "paid") LuganoUI.track("payment_confirmed");
    state.lastOrder = order;
    $("#order-refresh-message").textContent = "Status atualizado agora.";
    saveState();
    renderLastOrder();
    if (order.payment_status === "paid") {
      showNotice("Pagamento confirmado. Seu pedido já está com a equipe Lugano.", "success");
    } else if (order.payment_status === "failed") {
      showNotice("O pagamento não foi aprovado. Confira os dados ou fale com a equipe Lugano.", "error");
    }
  } catch {
    $("#order-refresh-message").textContent = "Não conseguimos atualizar agora. O pedido continua registrado; tente novamente.";
    updatePaymentPolling(state.lastOrder);
  }
}

async function copyPixCode() {
  const code = $("#pix-copy-paste").value;
  if (!code) return;
  try {
    await navigator.clipboard.writeText(code);
    showNotice("Código Pix copiado.", "success");
  } catch {
    $("#pix-copy-paste").select();
    showNotice("Selecione e copie o código Pix.", "error");
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
  renderCheckoutProgress();
  updateFloatingAccessButton();
}

async function loadProducts() {
  $("#product-grid").innerHTML = LuganoUI.skeleton(4);
  try {
    let products = [], page = 1, batch;
    do { batch = await api("/api/v1/catalog/products?page=" + page + "&page_size=100"); products.push(...batch); page++; } while(batch.length === 100 && page <= 20);
    state.products = products; state.productsLoaded = true;
    let changed = false;
    state.cart = state.cart.filter(item => {
      const product = products.find(p => p.id === item.id && p.available !== false);
      if (!product) { changed = true; return false; }
      if (Number(product.price) !== item.price) changed = true;
      item.price = Number(product.price); item.name = product.name;
      return Number.isInteger(item.quantity) && item.quantity > 0;
    });
    if(changed) { state.promotion = null; saveState(); showNotice("Atualizamos o carrinho conforme os preços e a disponibilidade atuais. Revise antes de continuar."); }
    renderAll(); await refreshQuote(); LuganoUI.track("menu_viewed");
  } catch(error) { state.productsLoaded = false; $("#product-grid").innerHTML = LuganoUI.empty("Não conseguimos abrir o cardápio", error.message, "products"); }
}

async function loadCustomerData() {
  if (!state.session) return;
  const addresses = await api("/api/v1/me/addresses");
  state.addresses = addresses;
  renderAll();
}

async function refreshQuote() {
  const sequence = ++state.quoteSequence;
  if(!state.cart.length) { state.quote = null; state.quoteLoading = false; renderCart(); return; }
  state.quoteLoading = true; state.quote = null; renderCart();
  try {
    const quote = await api("/api/v1/orders/quote", {method:"POST", body:JSON.stringify({subtotal_cents:cartSubtotalCents(),free_delivery:state.promotion?.type === "free_delivery"})});
    if(sequence === state.quoteSequence) state.quote = quote;
  } catch(error) { if(sequence === state.quoteSequence) showNotice(error.message, "error"); }
  finally { if(sequence === state.quoteSequence) { state.quoteLoading = false; renderCart(); } }
}

function logout() {
  state.session = null;
  state.addresses = [];
  state.promotion = null;
  state.quote = null;
  state.lastOrder = null;
  stopPaymentPolling();
  sessionStorage.removeItem("lugano.address.draft"); sessionStorage.removeItem("lugano.checkout.draft");
  $("#address-form").reset(); $("#order-notes").value = "";
  saveState();
  renderAll();
}

function addToCart(productId, quantity = 1, customization = "") {
  const product = state.products.find(p => p.id === productId && p.available !== false);
  if(!product || !state.productsLoaded) return;
  const existing = state.cart.find(i => i.id === productId && (i.customization || "") === customization);
  if(existing) existing.quantity = Math.min(99, existing.quantity + quantity);
  else state.cart.push({id:product.id,name:product.name,price:Number(product.price),quantity,customization});
  state.promotion = null; saveState(); renderCart(); renderCheckoutDetails(); refreshQuote();
  LuganoUI.track("product_added"); LuganoUI.toast(product.name + " adicionado ao carrinho.", "success");
}

async function saveAddress(event) {
  event.preventDefault(); const form = event.currentTarget;
  if(!state.session) return showNotice("Entre para salvar seu endereço.", "error");
  await LuganoUI.busy(form.querySelector("button"), "Salvando…", async () => {
    try { const address = await api("/api/v1/me/addresses",{method:"POST",body:JSON.stringify(formData(form))});
      state.addresses = [...state.addresses.filter(a => a.id !== address.id),address];
      renderAddresses(); $("#address-select").value = address.id; $("#address-summary").textContent = formatAddress(address);
      form.reset(); sessionStorage.removeItem("lugano.address.draft"); form.closest("details").open = false;
      showNotice("Endereço salvo e selecionado para entrega.", "success");
    } catch(error) { showNotice(error.message,"error"); }
  });
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
  const cartVersion=JSON.stringify(state.cart);
  try {
    const result = await api("/api/v1/promotions/validate", {
      method: "POST",
      body: JSON.stringify({
        code,
        order_subtotal: cartSubtotalCents(),
      }),
    });
    if(cartVersion!==JSON.stringify(state.cart) || code!==$("#promotion-code").value.trim()) { state.promotion=null; $("#promotion-summary").textContent="O carrinho ou o código mudou. Aplique o cupom novamente."; return; }
    state.promotion = result.valid ? {...result,code} : null;
    await refreshQuote();
    renderAll();
    $("#promotion-summary").textContent = result.description || (result.valid ? "Cupom aplicado." : "Cupom inválido.");
    showNotice(
      result.description || "Cupom validado.",
      result.valid ? "success" : "error",
    );
  } catch (error) {
    state.promotion = null;
    await refreshQuote();
    renderAll();
    $("#promotion-summary").textContent=error.status===422 ? "Cupom indisponível para este pedido. Confira a validade e as condições." : "Não conseguimos consultar o cupom. Tente novamente.";
    showNotice($("#promotion-summary").textContent, "error");
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
  if(!state.session) { rememberDeliveryReturn(); goToStep("step-account"); return false; }
  if(!state.cart.length) { goToStep("step-cart"); return false; }
  if(!selectedAddress()) { goToStep("step-delivery"); return false; }
  if(!state.productsLoaded || !state.quote || state.quoteLoading) { showNotice("Atualize o cardápio e calcule o frete antes de finalizar.","error"); return false; }
  if(LuganoUI.read("lugano.order.uncertain")?.user === state.session.user?.id) { showNotice("O envio anterior ainda precisa ser conferido. Consulte Meus pedidos antes de enviar novamente.","error"); return false; }
  return true;
}

function openOrderConfirmation() {
  if (!validateCheckout()) return;

  $("#confirm-summary").innerHTML = `
    <div><span>Entrega</span><strong>${escapeHTML(formatAddress(selectedAddress()))}</strong></div>
    <div><span>Pagamento</span><strong>${selectedPaymentLabel()}</strong></div>
    <div><span>Itens</span><strong>${state.cart.map(item => escapeHTML(item.quantity + " × " + item.name)).join("<br>")}</strong></div>
    <div><span>Subtotal</span><strong>${moneyCents(cartSubtotalCents())}</strong></div>
    <div><span>Entrega</span><strong>${moneyCents(deliveryFeeCents())}</strong></div>
    <div><span>Desconto</span><strong>${moneyCents(promotionDiscountCents())}</strong></div>
    <div class="grand-total"><span>Total</span><strong>${moneyCents(orderTotalCents())}</strong></div>
  `;
  LuganoUI.openDialog($("#confirm-dialog"));
  LuganoUI.track("payment_started");
}

function closeOrderConfirmation() {
  $("#confirm-dialog").close();
}

async function submitOrder() {
  if(!validateCheckout() || state.isSubmitting) return;
  state.isSubmitting = true;
  localStorage.setItem("lugano.order.uncertain",JSON.stringify({user:state.session.user?.id,at:Date.now()}));
  await LuganoUI.busy($("#confirm-order"), "Enviando pedido…", async () => {
    try {
      const order = await api("/api/v1/orders/",{method:"POST",body:JSON.stringify({
        address_id:$("#address-select").value,payment_method:$("#payment-method").value,
        promotion_code:state.promotion?.valid ? state.promotion.code || $("#promotion-code").value.trim() : null,
        notes:$("#order-notes").value || null,
        items:state.cart.map(i => ({product_id:i.id,quantity:i.quantity,customization:i.customization || null}))
      })});
      if (!order?.id) throw Object.assign(new Error("Resposta incompleta do envio."), {uncertain:true});
      localStorage.removeItem("lugano.order.uncertain");
      state.lastOrder = order; localStorage.setItem("lugano.lastOrder", JSON.stringify({id:order.id,user:state.session.user?.id}));
      state.cart = []; state.promotion = null; state.quote = null;
      $("#promotion-code").value = ""; $("#order-notes").value = ""; sessionStorage.removeItem("lugano.checkout.draft");
      saveState(); closeOrderConfirmation(); renderAll();
      document.body.classList.add("checkout-open");
      $("#last-order-panel").scrollIntoView({block:"start"});
      LuganoUI.track("order_submitted"); showNotice("Pedido enviado com sucesso. Acompanhe a confirmação abaixo.", "success");
    } catch(error) {
      if(error.uncertain || error.status >= 500) {
        localStorage.setItem("lugano.order.uncertain",JSON.stringify({user:state.session.user?.id,at:Date.now()}));
        closeOrderConfirmation();
        showNotice("Não recebemos a confirmação do envio. Confira Meus pedidos antes de tentar novamente.","error");
      } else { localStorage.removeItem("lugano.order.uncertain"); showNotice(error.message, "error"); }
    }
  });
  state.isSubmitting = false;
}

function bindEvents() {
  $("#logout-button").addEventListener("click", () => { localStorage.removeItem("lugano.customer.session"); logout(); });
  $("#refresh-products").addEventListener("click", () => LuganoUI.busy($("#refresh-products"),"Atualizando…",loadProducts));
  $("#product-search").addEventListener("input",renderProducts);
  $("#category-filter").addEventListener("change",renderProducts);
  $("#address-select").addEventListener("change",() => { renderAddresses(); saveDraft(); });
  $("#payment-method").addEventListener("change",() => { renderCheckoutDetails(); saveDraft(); });
  $("#order-notes").addEventListener("input", saveDraft);
  $("#address-form").addEventListener("submit",saveAddress);
  $("#address-form").addEventListener("input",event => sessionStorage.setItem("lugano.address.draft",JSON.stringify(formData(event.currentTarget))));
  $("#validate-promotion").addEventListener("click",() => LuganoUI.busy($("#validate-promotion"),"Validando…",async () => { await validatePromotion(); if(state.promotion?.valid) LuganoUI.track("coupon_applied"); }));
  $("#clear-promotion").addEventListener("click",clearPromotion);
  $("#checkout-button").addEventListener("click",checkout);
  $("#cancel-confirmation").addEventListener("click",closeOrderConfirmation);
  $("#confirm-order").addEventListener("click",submitOrder);
  $("#copy-pix").addEventListener("click",copyPixCode);
  $("#retry-quote").addEventListener("click",() => LuganoUI.busy($("#retry-quote"),"Calculando…",refreshQuote));
  $("#refresh-order").addEventListener("click",() => LuganoUI.busy($("#refresh-order"),"Atualizando…",() => { stopPaymentPolling(); return refreshPendingPayment(); }));
  $("#mobile-cart").addEventListener("click",() => { LuganoUI.track("cart_opened"); goToStep("step-cart"); });
  $("#back-to-menu").addEventListener("click",() => { document.body.classList.remove("checkout-open"); $("#product-search").focus(); });
  $("#close-product").addEventListener("click",() => $("#product-dialog").close());
  $("#add-product-detail").addEventListener("click",() => {
    const input = $("#product-quantity"); if(!input.reportValidity()) return;
    addToCart(state.detailProduct,Number(input.value),$("#product-note").value.trim()); $("#product-dialog").close();
  });
  document.addEventListener("click",event => {
    const b = event.target.closest("button,a"); if(!b)return;
    if(b.dataset.goStep)goToStep(b.dataset.goStep);
    if(b.dataset.addProduct)addToCart(b.dataset.addProduct);
    if(b.hasAttribute("data-category")) { $("#category-filter").value=b.dataset.category;renderCategoryFilter();renderProducts(); }
    if(b.dataset.retry === "products")loadProducts();
    if(b.dataset.returnAfterLogin)rememberDeliveryReturn();
    if(b.dataset.productDetail) {
      const p = state.products.find(p => p.id===b.dataset.productDetail); if(!p)return;
      state.detailProduct=p.id; $("#product-dialog-title").textContent=p.name;
      const image=LuganoUI.media(safeHttpUrl(p.image_url));
      $("#product-dialog-content").innerHTML=(image?'<figure class="product-media"><img width="400" height="300" alt="'+escapeHTML(p.name)+'" src="'+escapeHTML(image)+'"></figure>':'')+'<p>'+escapeHTML(p.description)+'</p><p class="product-price">'+money(p.price)+'</p>';
      $("#product-quantity").value=1; $("#product-note").value=""; LuganoUI.openDialog($("#product-dialog"),b);
    }
    if(b.hasAttribute("data-cart-change") || b.hasAttribute("data-cart-remove")) {
      state.undoCart=structuredClone(state.cart);
      const index=Number(b.dataset.cartChange ?? b.dataset.cartRemove), item=state.cart[index];
      if(!item)return;
      if(b.hasAttribute("data-cart-remove"))state.cart.splice(index,1);else { item.quantity=Math.min(99,item.quantity+Number(b.dataset.delta)); if(item.quantity<=0)state.cart.splice(index,1); }
      state.promotion=null; saveState();renderCart();renderCheckoutDetails();refreshQuote();
      LuganoUI.toast("Carrinho atualizado.","info",{label:"Desfazer",run:()=>{state.cart=state.undoCart;saveState();renderCart();refreshQuote();}});
    }
  });
}
function saveDraft() { sessionStorage.setItem("lugano.checkout.draft",JSON.stringify({address:$("#address-select").value,payment:$("#payment-method").value,notes:$("#order-notes").value})); }
async function restoreOrder() {
  const saved=LuganoUI.read("lugano.lastOrder");
  if(!state.session || !saved || saved.user!==state.session.user?.id)return;
  try { state.lastOrder=await api("/api/v1/orders/"+encodeURIComponent(saved.id));state.restoreError=null;renderLastOrder(); if(new URLSearchParams(location.search).has("acompanhar")) { document.body.classList.add("checkout-open"); $("#last-order-panel").scrollIntoView({block:"start"}); } } catch(error) { state.restoreError=saved.id; renderLastOrder();document.body.classList.add("checkout-open");showNotice("Não conseguimos consultar seu pedido. Ele já foi registrado; não envie novamente.","error"); }
}

bindEvents();
renderAll();
loadProducts().catch((error) => showNotice(error.message, "error"));
loadCustomerData().then(() => {
  try { const draft=JSON.parse(sessionStorage.getItem("lugano.checkout.draft") || "{}");
    if(draft.address && state.addresses.some(a=>a.id===draft.address)) $("#address-select").value=draft.address;
    $("#payment-method").value=draft.payment || "pix"; $("#order-notes").value=draft.notes || "";
    const address=JSON.parse(sessionStorage.getItem("lugano.address.draft") || "{}");
    for(const [key,value] of Object.entries(address)) if($("#address-form").elements[key]) $("#address-form").elements[key].value=value || "";
    renderAddresses();renderCheckoutDetails();
    if(state.session && state.cart.length && state.activeStep !== "cart") document.body.classList.add("checkout-open");
  } catch {}
}).catch((error) => showNotice(error.message, "error"));
restoreOrder();
refreshQuote().catch((error) => showNotice(error.message, "error"));
