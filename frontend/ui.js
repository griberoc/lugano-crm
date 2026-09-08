/* Shared, framework-free UI primitives. No customer data leaves the browser. */
(() => {
  const read = (key, fallback = null) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
  const text = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  function track(name) {
    const event = { name, at: Date.now() };
    window.dispatchEvent(new CustomEvent("lugano:analytics", { detail: event }));
    // Local, bounded and deliberately free of IDs, addresses, payment data or form values.
    const saved = read("lugano.ux.events", []);
    const events = Array.isArray(saved) ? saved : [];
    try { localStorage.setItem("lugano.ux.events", JSON.stringify([...events, event].slice(-100))); } catch {}
  }
  function notice(node, message, type = "info") {
    if (!node) return;
    node.textContent = message;
    node.classList.remove("hidden", "error", "success");
    node.classList.add(type);
    node.setAttribute("role", type === "error" ? "alert" : "status");
    const dialog=document.querySelector("dialog[open]");
    if (dialog && !dialog.contains(node)) {
      let local=dialog.querySelector(".dialog-notice");
      if(!local) { local=document.createElement("p"); local.className="notice dialog-notice"; dialog.prepend(local); }
      local.className="notice dialog-notice "+type; local.textContent=message;
      local.setAttribute("role",type==="error" ? "alert" : "status");
    }
  }
  function toast(message, type = "info", action) {
    let node = document.querySelector("#ux-toast");
    if (!node) { node = document.createElement("div"); node.id = "ux-toast"; document.body.append(node); }
    notice(node, message, type);
    if (action) {
      const button = document.createElement("button"); button.textContent = action.label;
      button.onclick = () => { action.run(); node.classList.add("hidden"); };
      node.append(button);
    }
    clearTimeout(node.timer);
    node.timer = setTimeout(() => node.classList.add("hidden"), action ? 10000 : 6000);
  }
  async function busy(button, label, work) {
    if (button?.disabled) return;
    const original = button?.textContent;
    if (button) { button.disabled = true; button.textContent = label; button.setAttribute("aria-busy", "true"); }
    try { return await work(); }
    finally { if (button) { button.disabled = false; button.textContent = original; button.removeAttribute("aria-busy"); } }
  }
  async function request(url, options = {}) {
    const method=(options.method || "GET").toUpperCase();
    const path=new URL(url,location.href).pathname.replace(/\/$/,"");
    const readOnlyPost=["/api/v1/admin/login","/api/v1/orders/quote","/api/v1/promotions/validate","/auth/v1/token"];
    if(window.LUGANO_CONFIG?.previewReadOnly && !["GET","HEAD","OPTIONS"].includes(method) && !(method==="POST" && readOnlyPost.includes(path))) {
      throw Object.assign(new Error("Prévia visual: alterações reais estão desativadas. Seus dados foram mantidos para revisão."),{status:409});
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, { ...options, signal: options.signal || controller.signal });
      const body = response.status === 204 ? null : await response.json().catch(() => null);
      if (!response.ok) {
        const messages = {
          400: "Confira os dados e tente novamente.",
          401: "Sua sessão expirou. Entre novamente para continuar.",
          403: "Sua conta não tem permissão para esta ação.",
          404: "Este item não está mais disponível. Atualize a página.",
          409: "Os dados mudaram. Atualize e revise antes de continuar.",
          422: "Confira os campos e as condições do pedido.",
          429: "Muitas tentativas. Aguarde um momento e tente novamente.",
        };
        const error = new Error(messages[response.status] || "Não foi possível concluir agora. Tente novamente em instantes.");
        error.status = response.status;
        throw error;
      }
      return body;
    } catch (error) {
      if (error.status) throw error;
      const failure = new Error(!navigator.onLine ? "Você está sem conexão. Seus dados foram mantidos." : "A conexão demorou ou foi interrompida. Tente novamente.");
      failure.uncertain = true;
      throw failure;
    } finally { clearTimeout(timeout); }
  }
  function empty(title, description, retry = "") {
    return '<div class="ux-empty"><span class="empty-mark" aria-hidden="true">L</span><h3>' + text(title) + '</h3><p>' + text(description) + '</p>' + (retry ? '<button type="button" class="ghost-button" data-retry="' + text(retry) + '">Tentar novamente</button>' : "") + '</div>';
  }
  function skeleton(count = 3) {
    return '<div class="sr-only" role="status">Carregando…</div>' + Array.from({length:count}, () => '<div class="ux-skeleton" aria-hidden="true"><i></i><i></i><i></i></div>').join("");
  }
  function openDialog(dialog, trigger) {
    dialog.querySelector(".dialog-notice")?.remove();
    dialog._trigger = trigger || document.activeElement;
    dialog.showModal();
    dialog.querySelector("button, input, textarea")?.focus();
  }
  const mediaCache = {
  "https://static.ifood-static.com.br/image/upload/t_low/pratos/9800bb4a-696d-447e-be36-449be1c63138/202105061600_2IWQ_.jpeg": "../assets/catalog/e850c828ebf639b7",
  "https://static.ifood-static.com.br/image/upload/t_low/pratos/9800bb4a-696d-447e-be36-449be1c63138/202409151234_0G87_i.jpg": "../assets/catalog/a6a69a2f2d2f9a19",
  "https://static.ifood-static.com.br/image/upload/t_low/pratos/9800bb4a-696d-447e-be36-449be1c63138/202409181619_T2CE_i.jpg": "../assets/catalog/853320fe0db2653c",
  "https://static.ifood-static.com.br/image/upload/t_low/pratos/9800bb4a-696d-447e-be36-449be1c63138/202509021905_4J3X_i.jpg": "../assets/catalog/c046923e74fdda76"
};
  function setup() {
    const module = location.pathname.split("/").filter(Boolean)[0];
    document.body.classList.add("premium", "module-" + module);
    if(window.LUGANO_CONFIG?.previewReadOnly) {
      document.body.classList.add("local-preview");
      const banner=document.createElement("div");banner.className="preview-banner";
      banner.textContent="Prévia local · pedidos e alterações desativados";
      banner.title="Navegue, entre na conta e monte o carrinho. Esta prévia não envia pedidos, cria contas ou altera cadastros.";
      document.body.append(banner);
    }
    if (["orders", "customer", "auth"].includes(module) && !document.querySelector(".shop-header")) {
      const header = document.createElement("header");
      header.className = "shop-header";
      header.innerHTML = '<a class="shop-brand" href="../orders/"><img src="../assets/lugano-logo-mark.svg" width="40" height="40" alt=""><span>Lugano<small>CAFETERIA & CHOCOLATERIA</small></span></a><nav aria-label="Navegação principal"><a href="../orders/"' + (module === "orders" ? ' aria-current="page"' : '') + '>Cardápio</a><a href="../customer/"' + (module === "customer" ? ' aria-current="page"' : '') + '>Minha Lugano</a></nav><div class="shop-session"></div>';
      const session = document.querySelector(".nav-session, .session-actions");
      if (session) header.querySelector(".shop-session").append(session);
      document.body.prepend(header);
      const skip = document.createElement("a"); skip.href = "#main-content"; skip.className = "skip-link"; skip.textContent = "Pular para o conteúdo"; document.body.prepend(skip);
      const main = document.querySelector("main"); if (main) { main.id = "main-content"; main.tabIndex = -1; }
    }
    const applyMedia = image => {
      const src=image.getAttribute("src");
      const prefix=mediaCache[src] || Object.values(mediaCache).find(p => src===p+"-400.webp"); if(!prefix)return;
      if(image.getAttribute("src")!==prefix+"-400.webp") image.src=prefix+"-400.webp"; image.srcset=prefix+"-400.webp 400w, "+prefix+"-800.webp 800w";
      image.sizes="(max-width:700px) 104px, (max-width:1100px) 300px, 400px";
      image.decoding="async";
    };
    const observer=new MutationObserver(records=>records.forEach(record=>{
      if(record.type==="attributes")applyMedia(record.target);
      record.addedNodes.forEach(node=>{ if(node.nodeType!==1)return; if(node.tagName==="IMG")applyMedia(node); node.querySelectorAll?.("img").forEach(applyMedia); });
    }));
    observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:["src"]});
    document.querySelectorAll("img").forEach(applyMedia);
    document.querySelectorAll("[data-logout-session]").forEach(button => button.onclick=()=>document.querySelector("#logout-button")?.click());
    document.querySelectorAll(".notice").forEach(node => node.setAttribute("role", "status"));
    document.querySelectorAll("dialog").forEach(dialog => {
      dialog.addEventListener("close", () => dialog._trigger?.focus());
      dialog.addEventListener("click", event => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
    });
    document.querySelectorAll('input[name="zip_code"]').forEach(input => {
      input.inputMode = "numeric"; input.autocomplete = "postal-code"; input.maxLength = 9;
      input.pattern = "[0-9]{5}-?[0-9]{3}"; input.title = "Informe um CEP com 8 dígitos.";
      input.addEventListener("input", () => { input.value = input.value.replace(/\D/g, "").slice(0,8).replace(/^(\d{5})(\d)/,"$1-$2"); input.setCustomValidity(""); });
    });
    document.querySelectorAll('input[name="phone"]').forEach(input => { input.type = "tel"; input.autocomplete = "tel"; input.inputMode = "tel"; });
    document.addEventListener("invalid", event => {
      const field = event.target; if (!field.id) field.id = "field-" + Math.random().toString(36).slice(2);
      field.setAttribute("aria-invalid", "true");
      let message = document.getElementById(field.id + "-error");
      if (!message) { message = document.createElement("span"); message.id = field.id + "-error"; message.className = "field-error"; field.after(message); }
      message.textContent = field.validity.valueMissing ? "Preencha este campo." : "Confira o formato informado.";
      field.setAttribute("aria-describedby", message.id);
    }, true);
    document.addEventListener("input", event => { event.target.removeAttribute("aria-invalid"); document.getElementById(event.target.id + "-error")?.remove(); });
    document.addEventListener("error", event => {
      if (event.target.tagName === "IMG" && !event.target.dataset.fallback) {
        event.target.dataset.fallback = "true"; event.target.removeAttribute("srcset"); event.target.src = "../assets/lugano-logo-mark.svg"; event.target.classList.add("image-fallback");
      }
    }, true);
    window.addEventListener("offline", () => toast("Sem conexão. Seus dados continuam neste dispositivo.", "error"));
    window.addEventListener("online", () => toast("Conexão restabelecida. Você já pode tentar novamente.", "success"));
    window.__luganoVitals = { cls: 0, lcp: null };
    try {
      new PerformanceObserver(list => list.getEntries().forEach(e => { window.__luganoVitals.lcp = e.startTime; })).observe({type:"largest-contentful-paint", buffered:true});
      new PerformanceObserver(list => list.getEntries().forEach(e => { if (!e.hadRecentInput) window.__luganoVitals.cls += e.value; })).observe({type:"layout-shift", buffered:true});
    } catch {}
  }
  window.LuganoUI = { read, text, track, notice, toast, busy, request, empty, skeleton, openDialog, media: url => mediaCache[url] ? mediaCache[url] + "-400.webp" : url };
  setup();
})();
