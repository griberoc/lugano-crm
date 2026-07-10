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
};

const $ = (selector) => document.querySelector(selector);

function showNotice(message, type = "info") {
  const notice = $("#notice");
  notice.textContent = message;
  notice.classList.remove("hidden", "error");
  if (type === "error") notice.classList.add("error");
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

function setAuthMode(mode) {
  const isSignup = mode === "signup";
  $("#login-form").classList.toggle("hidden", isSignup);
  $("#signup-form").classList.toggle("hidden", !isSignup);
  $("#show-login").classList.toggle("active", !isSignup);
  $("#show-signup").classList.toggle("active", isSignup);
}

function requireSupabaseConfig() {
  if (!state.supabaseUrl || !state.supabaseAnonKey) {
    showNotice("Nao foi possivel iniciar o acesso. Configuracao publica ausente.", "error");
    return false;
  }
  return true;
}

async function supabaseAuth(path, payload) {
  const response = await fetch(`${state.supabaseUrl}/auth/v1/${path}`, {
    method: "POST",
    headers: {
      apikey: state.supabaseAnonKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.msg || body.message || body.error_description || "Falha na autenticacao.");
  }
  return body;
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
    showNotice("As senhas nao conferem.", "error");
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
    showNotice(`Nao foi possivel criar a conta. ${error.message}`, "error");
  }
}

function logout() {
  state.session = null;
  saveSession();
  notifySessionChanged();
  renderSession();
  showNotice("Sessao encerrada.");
}

function bindEvents() {
  $("#login-form").addEventListener("submit", login);
  $("#signup-form").addEventListener("submit", signup);
  $("#show-login").addEventListener("click", () => setAuthMode("login"));
  $("#show-signup").addEventListener("click", () => setAuthMode("signup"));
  $("#logout-button").addEventListener("click", logout);
}

bindEvents();
renderSession();
