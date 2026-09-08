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
  session: LuganoUI.read("lugano.customer.session"),
};

const $ = (selector) => document.querySelector(selector);

function showNotice(message,type="info") { LuganoUI.notice($("#notice"),message,type); LuganoUI.toast(message,type); }

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
 if(!state.session)return;
 const route=localStorage.getItem("lugano.customer.returnAfterLogin");
 localStorage.removeItem("lugano.customer.returnAfterLogin");
 location.assign(route === "delivery" ? "../orders/" : "../customer/");
}

function authHeaders() {
  return state.session?.access_token
    ? { Authorization: `Bearer ${state.session.access_token}` }
    : {};
}

async function api(path, options = {}) { return LuganoUI.request(state.apiBaseUrl + path,{...options, headers:{"Content-Type":"application/json",...authHeaders(),...(options.headers || {})}}); }

function setAuthMode(mode) {
  const isSignup = mode === "signup";
  $("#login-form").classList.toggle("hidden", isSignup);
  $("#signup-form").classList.toggle("hidden", !isSignup);
  $("#show-login").classList.toggle("active", !isSignup);
  $("#show-signup").classList.toggle("active", isSignup);
  $("#show-login").setAttribute("aria-selected",String(!isSignup));
  $("#show-login").tabIndex=isSignup ? -1 : 0;
  $("#show-signup").tabIndex=isSignup ? 0 : -1;
  $("#show-signup").setAttribute("aria-selected",String(isSignup));
}

function requireSupabaseConfig() {
  if (!state.supabaseUrl || !state.supabaseAnonKey) {
    showNotice("O acesso está temporariamente indisponível. Tente novamente em instantes.", "error");
    return false;
  }
  return true;
}

async function supabaseAuth(path,payload) {
 try { return await LuganoUI.request(state.supabaseUrl + "/auth/v1/" + path,{method:"POST",headers:{apikey:state.supabaseAnonKey,"Content-Type":"application/json"},body:JSON.stringify(payload)}); }
 catch(error) { if(error.status===400 || error.status===401)throw new Error(path.startsWith("token") ? "Email ou senha incorretos. Confira e tente novamente." : "Não foi possível cadastrar estes dados. Confira o email e os requisitos da senha."); throw error; }
}

function sessionFromAuthResponse(body) {
  if (body.access_token) return body;
  if (body.session?.access_token) {
    return {
      ...body.session,
      user: body.user || body.session.user,
    };
  }
  return null;
}

function renderSession() {
  const email = state.session?.user?.email;
  $("#session-label").textContent = email || "Visitante";
  $("#session-summary").textContent = email
    ? `Conta conectada: ${email}`
    : "Nenhuma conta conectada.";
  $("#logout-button").classList.toggle("hidden", !state.session);
  $("#session-panel").classList.toggle("hidden", !state.session);
}

async function login(event) {
  event.preventDefault();
  const form = event.currentTarget;

  if (!requireSupabaseConfig()) return;

  try {
    state.session = await supabaseAuth("token?grant_type=password", formData(form));
    saveSession();
    notifySessionChanged();
    form.reset();
    renderSession();
    showNotice("Login realizado.");
  } catch (error) {
    showNotice(`Login falhou. ${error.message}`, "error");
  }
}

async function signup(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);

  if (!requireSupabaseConfig()) return;

  if (data.password !== data.password_confirm) {
    form.elements.password_confirm.setCustomValidity("As senhas não conferem.");
    form.elements.password_confirm.reportValidity();
    showNotice("As senhas não conferem.", "error");
    return;
  }

  try {
    const response = await supabaseAuth("signup", {
      email: data.email,
      password: data.password,
      data: {
        full_name: data.full_name,
        phone: data.phone,
      },
    });
    const session = sessionFromAuthResponse(response);
    form.reset();

    if (!session) {
      setAuthMode("login");
      showNotice("Conta criada. Confirme seu email e depois entre.");
      return;
    }

    state.session = session;
    saveSession();
    notifySessionChanged();
    renderSession();
    setAuthMode("login");

    try {
      await api("/api/v1/me/", {
        method: "PATCH",
        body: JSON.stringify({
          full_name: data.full_name,
          phone: data.phone,
        }),
      });
    } catch {
      // O perfil pode ser criado pelo gatilho do Supabase alguns instantes depois.
    }

    showNotice("Conta criada e conectada.");
  } catch (error) {
    showNotice(`Não foi possível criar a conta. ${error.message}`, "error");
  }
}

function logout() {
  sessionStorage.removeItem("lugano.address.draft"); sessionStorage.removeItem("lugano.checkout.draft");
  state.session = null;
  saveSession();
  notifySessionChanged();
  renderSession();
  showNotice("Sessão encerrada.");
}

function bindEvents() {
  $("#login-form").addEventListener("submit", event => { event.preventDefault(); LuganoUI.busy(event.currentTarget.querySelector("button"),"Entrando…",() => login(event)); });
  $("#signup-form").addEventListener("submit", event => { event.preventDefault(); LuganoUI.busy(event.currentTarget.querySelector("button"),"Criando conta…",() => signup(event)); });
  $(".auth-tabs").addEventListener("keydown",event=>{
    if(!["ArrowLeft","ArrowRight","Home","End"].includes(event.key))return;
    event.preventDefault(); const signup=event.key==="End" || (event.key!=="Home" && $("#show-login").getAttribute("aria-selected")==="true");
    setAuthMode(signup?"signup":"login");$(signup?"#show-signup":"#show-login").focus();
  });
  $("#signup-form").elements.password_confirm.addEventListener("input",event=>event.target.setCustomValidity(""));
  $("#show-login").addEventListener("click", () => setAuthMode("login"));
  $("#show-signup").addEventListener("click", () => setAuthMode("signup"));
  $("#logout-button").addEventListener("click", logout);
}

bindEvents();
renderSession();
