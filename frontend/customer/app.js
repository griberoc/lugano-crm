const runtimeConfig = window.LUGANO_CONFIG || {};
const DEFAULT_API_URL = runtimeConfig.apiBaseUrl || "http://127.0.0.1:8000";

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}
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
  session: LuganoUI.read("lugano.customer.session"),
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

function showNotice(message,type="info") { LuganoUI.notice($("#notice"),message,type); LuganoUI.toast(message,type); }

function authHeaders() {
  return state.session?.access_token
    ? { Authorization: `Bearer ${state.session.access_token}` }
    : {};
}

async function api(path, options = {}) { return LuganoUI.request(state.apiBaseUrl + path,{...options, headers:{"Content-Type":"application/json",...authHeaders(),...(options.headers || {})}}); }

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
    ? `Olá, ${firstName}.`
    : "Seu clube de benefícios.";
  $("#customer-summary").textContent = email
    ? "Acompanhe seus pontos, pedidos recentes e promoções."
    : "Entre para ver seus pontos, nível, pedidos e promoções.";
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
    list.innerHTML = '<p class="muted">Entre para ver seus endereços salvos.</p>';
    return;
  }

  list.innerHTML = state.addresses.length
    ? state.addresses
        .map(
          (address) => `
            <article class="address-card ${address.is_default ? "selected-address" : ""}">
              <div>
                <strong>${escapeHTML(address.label)}</strong>
                <span>${escapeHTML(addressLine(address))}</span>
                <span>CEP ${escapeHTML(address.zip_code)}</span>
              </div>
              <div class="address-actions">
                ${address.is_default ? '<span class="mini-badge">Principal</span>' : ""}
                <button class="ghost-button" data-edit-address="${escapeHTML(address.id)}" type="button">Editar</button>
                <button class="ghost-button" data-default-address="${escapeHTML(address.id)}" type="button">Padrão</button>
                <button class="ghost-button danger-button" data-delete-address="${escapeHTML(address.id)}" type="button">Remover</button>
              </div>
            </article>
          `,
        )
        .join("")
    : '<p class="muted">Nenhum endereço cadastrado ainda.</p>';
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
  $("#loyalty-available").textContent = loyalty?.available_points ?? "—";
  $("#loyalty-total").textContent = loyalty?.total_points ?? "—";
  $("#loyalty-tier").textContent = tier?.name || "--";
  $("#tier-badge").textContent = tier?.name || "Visitante";
  $("#loyalty-cashback").textContent = tier ? `${Number(tier.cashback_rate)}%` : "—";

  if (!loyalty || !tier) {
    $("#loyalty-headline").textContent = state.session ? "Consulte seus pontos e benefícios." : "Entre para ativar sua conta Lugano.";
    $("#loyalty-progress-bar").style.width = "0%";
    $("#loyalty-progress-label").textContent = state.session ? "Aguardando os dados de fidelidade." : "Entre para ver seu progresso.";
    $("#loyalty-benefits").innerHTML = '<p class="muted">Seus benefícios aparecerão após a consulta da conta.</p>';
    return;
  }

  $("#loyalty-headline").textContent =
    `${loyalty.available_points} pontos disponíveis no nível ${tier.name}.`;
  $("#loyalty-progress-bar").parentElement.hidden = true;
  $("#loyalty-progress-label").textContent =
    `${loyalty.total_points} pontos acumulados. Nível ${tier.name} conquistado a partir de ${tier.min_points} pontos.`;

  const benefits = tier.benefits || {};
  $("#loyalty-benefits").innerHTML = Object.keys(benefits).length
    ? Object.entries(benefits)
        .map(
          ([key, value]) => `
            <article>
              <strong>${escapeHTML(benefitLabel(key))}</strong>
              <span>${escapeHTML(value === true ? "Incluído no seu nível" : value === false ? "Não incluído" : typeof value === "object" ? "Consulte as condições com a loja" : value)}</span>
            </article>
          `,
        )
        .join("")
    : '<p class="muted">Nenhum benefício cadastrado para este nível.</p>';
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
 const orders=[...state.orders].sort((a,b)=>new Date(b.placed_at)-new Date(a.placed_at));
 $("#orders-list").innerHTML=orders.length ? orders.map(order=>'<article class="order-card"><div><strong>Pedido #'+escapeHTML(String(order.id).slice(0,8))+'</strong><span>'+dateLabel(order.placed_at)+' · '+money(order.total)+'</span></div><span class="status '+escapeHTML(order.status)+'">'+escapeHTML(statusLabel(order.status))+'</span><div class="order-actions"><button class="ghost-button" data-view-order="'+escapeHTML(order.id)+'">Ver pedido</button><button class="ghost-button" data-reorder="'+escapeHTML(order.id)+'">Pedir novamente</button></div></article>').join("") : LuganoUI.empty("Seu primeiro pedido está esperando","Escolha seus favoritos no cardápio para começar.");
 const guest=!state.session;
 document.querySelectorAll(".account-overview,.loyalty-panel,.priority-grid,.transactions-panel,.account-settings").forEach(node=>node.classList.toggle("hidden",guest));
 const active=orders.find(o=>!["delivered","cancelled"].includes(o.status));
 $("#active-order").innerHTML=active ? '<span class="section-kicker">Pedido em andamento</span><h2>'+escapeHTML(statusLabel(active.status))+'</h2><p>Pedido #'+escapeHTML(String(active.id).slice(0,8))+' · '+money(active.total)+'</p><button class="primary-button" data-view-order="'+escapeHTML(active.id)+'">Acompanhar pedido</button>' : '<span class="section-kicker">Sua próxima pausa</span><h2>Que tal algo especial?</h2><p>Seus favoritos estão no cardápio.</p><a class="primary-button" href="../orders/">Escolher meu pedido</a>';
 if(guest) $("#active-order").innerHTML='<span class="section-kicker">Bem-vindo à Minha Lugano</span><h2>Seus pedidos e benefícios, juntos.</h2><p>Entre para acompanhar pedidos, consultar pontos e salvar seus endereços.</p><a class="primary-button" href="../auth/">Entrar ou criar conta</a>';
 const uncertain=LuganoUI.read("lugano.order.uncertain");
 $("#uncertain-order").classList.toggle("hidden",!uncertain || uncertain.user!==state.session?.user?.id);
}

function promotionValue(promotion) {
  if (promotion.type === "percentage") return `${Number(promotion.value)}% off`;
  if (promotion.type === "fixed") return `${money(Number(promotion.value))} off`;
  if (promotion.type === "free_delivery") return "Frete grátis";
  return "Beneficio";
}

function renderPromotions() {
  $("#promotions-list").innerHTML = state.promotions.length
    ? state.promotions
        .map(
          (promotion) => `
            <article class="promotion-card">
              <div>
                <strong>${escapeHTML(promotion.code)}</strong>
                <span>${escapeHTML(promotion.description || promotion.audience)}</span>
              </div>
              <div class="promotion-meta">
                <span>${escapeHTML(promotionValue(promotion))}</span>
                <span>Pedido mínimo ${money((promotion.min_order_cents || 0) / 100)}</span>
                ${promotion.expires_at ? `<span>Válido até ${dateLabel(promotion.expires_at)}</span>` : ""}
              </div>
            </article>
          `,
        )
        .join("")
    : '<p class="muted">Nenhuma promoção disponível no momento.</p>';
}

function transactionLabel(type) {
  const labels = {
    earn: "Ganho",
    redeem: "Resgate",
    expire: "Expiração",
    bonus: "Bônus",
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
                <strong>${escapeHTML(transactionLabel(transaction.type))}</strong>
                <span>${escapeHTML(transaction.description)}</span>
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
 if(!state.session) { state.addresses=[];renderAll();return; }
 $("#orders-list").innerHTML=LuganoUI.skeleton(2);
 $("#active-order").innerHTML=LuganoUI.skeleton(1);
 const busyPanels=["#loyalty-benefits","#promotions-list","#transactions-list","#addresses-list"];
 busyPanels.forEach(s=>$(s).setAttribute("aria-busy","true"));
 try {
 const results=await Promise.allSettled([
 api("/api/v1/me/"),api("/api/v1/loyalty/"),api("/api/v1/orders/"),api("/api/v1/promotions/available"),api("/api/v1/loyalty/transactions"),api("/api/v1/me/addresses")]);
 const keys=["profile","loyalty","orders","promotions","transactions","addresses"];
 results.forEach((result,i)=> { if(result.status==="fulfilled")state[keys[i]]=result.value; });
 renderAll();
 busyPanels.forEach(s=>$(s).removeAttribute("aria-busy"));
 const panels=[null,"#loyalty-benefits","#orders-list","#promotions-list","#transactions-list","#addresses-list"];
 results.forEach((result,i)=>{
   if(result.status!=="rejected")return;
   const node=panels[i] && $(panels[i]);
   if(node) node.insertAdjacentHTML("afterbegin",'<div class="notice error" role="alert">Não foi possível atualizar esta seção. <button class="ghost-button" data-retry-dashboard>Tentar novamente</button></div>');
   if(i===2) $("#active-order").innerHTML=LuganoUI.empty("Pedidos temporariamente indisponíveis","Não repita um pedido por causa desta falha. Atualize o painel para conferir o status.");
 });
 if(results.some(r=>r.status==="rejected"))showNotice(results.some(r=>r.status==="rejected" && r.reason.status===401) ? "Sua sessão expirou. Entre novamente para consultar a conta." : "Parte da sua conta não carregou. Atualize para tentar novamente.","error");
 } catch(error) { showNotice(error.message,"error"); }
}

async function loadAddresses() {
  state.addresses = await api("/api/v1/me/addresses");
  renderAddresses();
}

function logout() {
  sessionStorage.removeItem("lugano.address.draft"); sessionStorage.removeItem("lugano.checkout.draft");
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
    showNotice("Entre antes de atualizar suas preferências.", "error");
    return;
  }

  state.profile = await api("/api/v1/me/", {
    method: "PATCH",
    body: JSON.stringify({
      preferences: preferencePayload(event.currentTarget),
    }),
  });
  renderPreferences();
  showNotice("Preferências salvas.", "success");
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
    showNotice("Entre antes de salvar endereços.", "error");
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
  showNotice(addressId ? "Endereço atualizado." : "Endereço salvo.", "success");
}

async function setDefaultAddress(addressId) {
  await api(`/api/v1/me/addresses/${addressId}`, {
    method: "PATCH",
    body: JSON.stringify({ is_default: true }),
  });
  await loadAddresses();
  showNotice("Endereço principal atualizado.", "success");
}

async function deleteAddress(addressId) {
  const address=state.addresses.find(item=>item.id===addressId);
  if (!confirm("Remover o endereço "+(address?.label || "")+" — "+(address?.street || "")+"? Ele deixará de aparecer nas opções de entrega.")) return;
  await api(`/api/v1/me/addresses/${addressId}`, { method: "DELETE" });
  clearAddressForm();
  await loadAddresses();
  showNotice("Endereço removido.", "success");
}

function bindEvents() {
  $("#profile-form").addEventListener("submit", event => { event.preventDefault(); LuganoUI.busy(event.currentTarget.querySelector('button[type="submit"]'),"Salvando…",() => saveProfile(event)).catch(error=>showNotice(error.message,"error")); });
  $("#preferences-form").addEventListener("submit", event => { event.preventDefault(); LuganoUI.busy(event.currentTarget.querySelector('button[type="submit"]'),"Salvando…",() => savePreferences(event)).catch(error=>showNotice(error.message,"error")); });
  $("#address-form").addEventListener("submit", event => { event.preventDefault(); LuganoUI.busy(event.currentTarget.querySelector('button[type="submit"]'),"Salvando…",() => saveAddress(event)).catch(error=>showNotice(error.message,"error")); });
  $("#cancel-address-edit").addEventListener("click", clearAddressForm);
  $("#logout-button").addEventListener("click", logout);
  $("#refresh-dashboard").addEventListener("click", () => {
    LuganoUI.busy($("#refresh-dashboard"),"Atualizando…",loadDashboard).catch((error) => showNotice(error.message, "error"));
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


function benefitLabel(key) {
 const names={boas_vindas:"Benefício de boas-vindas",birthday_discount:"Desconto de aniversário",free_delivery:"Entrega grátis",priority_support:"Atendimento prioritário",exclusive_promotions:"Promoções exclusivas"};
 return names[key] || key.replace(/_/g," ").replace(/^./,s=>s.toUpperCase());
}
async function viewOrder(id) {
 const order=state.orders.find(o=>o.id===id);if(!order)return;
 $("#customer-order-title").textContent="Pedido #"+String(id).slice(0,8);
 $("#customer-order-content").innerHTML='<p>'+escapeHTML(statusLabel(order.status))+' · '+money(order.total)+'</p><p>'+dateLabel(order.placed_at)+'</p><p>Pagamento: '+escapeHTML(({pending:"Aguardando pagamento",paid:"Confirmado",failed:"Não aprovado",refunded:"Reembolsado"})[order.payment_status] || "A consultar")+'</p><p>Itens: '+(order.items || []).map(i=>escapeHTML(i.quantity+" × "+(i.product?.name || "Produto "+String(i.product_id).slice(0,8)))).join("<br>")+'</p><button id="follow-order" class="primary-button">Acompanhar atualização</button>';
 LuganoUI.openDialog($("#customer-order-dialog"));
 $("#follow-order").onclick=()=>{localStorage.setItem("lugano.lastOrder",JSON.stringify({id,user:state.session.user?.id}));location.assign("../orders/?acompanhar=1");};
}
let pendingReorder=null;
async function prepareReorder(id,button) {
 await LuganoUI.busy(button,"Conferindo…",async()=>{
 try {
 const order=state.orders.find(o=>o.id===id); if(!order)return;
 let products=[],page=1,batch;
 do {batch=await api("/api/v1/catalog/products?page="+page+"&page_size=100");products.push(...batch);page++;}while(batch.length===100 && page<=20);
 const items=order.items || order.order_items || [], available=[], removed=[];
 for(const item of items) {const product=products.find(p=>p.id===item.product_id && p.available!==false); if(!product) {removed.push(item.product?.name || "Item indisponível");continue;}available.push({id:product.id,name:product.name,price:Number(product.price),quantity:item.quantity,customization:item.customization || ""});}
 pendingReorder=available;
 $("#customer-order-title").textContent="Revisar recompra";
 $("#customer-order-content").innerHTML='<p>Os itens abaixo substituirão seu carrinho. Confira os preços atuais.</p>'+available.map(i=>'<p>'+escapeHTML(i.quantity+" × "+i.name)+' <strong>'+money(i.price*i.quantity)+'</strong></p>').join("")+(removed.length?'<p>'+removed.length+' item(ns) indisponível(is) não serão incluídos.</p>':'')+'<button id="confirm-reorder" class="primary-button" '+(!available.length?'disabled':'')+'>Usar este carrinho</button>';
 LuganoUI.openDialog($("#customer-order-dialog"),button);
 $("#confirm-reorder").onclick=()=>{ localStorage.setItem("lugano.customer.cart",JSON.stringify(pendingReorder));sessionStorage.setItem("lugano.checkout.step","cart");LuganoUI.track("reorder_started");location.assign("../orders/"); };
 }catch(error){showNotice(error.message,"error");}
 });
}
document.addEventListener("click",event=>{
 const b=event.target.closest("button");if(!b)return;
 if(b.hasAttribute("data-retry-dashboard"))LuganoUI.busy(b,"Atualizando…",loadDashboard);
 if(b.dataset.viewOrder)viewOrder(b.dataset.viewOrder);
 if(b.dataset.reorder)prepareReorder(b.dataset.reorder,b);
});

bindEvents();
renderAll();
$("#close-customer-order").onclick=()=>$("#customer-order-dialog").close();
$("#clear-uncertain").onclick=()=>{if(confirm("Você confirmou com a loja que não há um pedido duplicado?")){localStorage.removeItem("lugano.order.uncertain");renderOrders();}};
loadDashboard().catch((error) => showNotice(error.message, "error"));
