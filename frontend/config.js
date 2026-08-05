const isLocalFrontend = ["127.0.0.1", "localhost"].includes(window.location.hostname);
const apiBaseUrl = isLocalFrontend
  ? "http://127.0.0.1:8000"
  : "https://api.chocolateluganosaoluis.com.br";

window.LUGANO_CONFIG = {
  apiBaseUrl,
  adminApiBaseUrl: apiBaseUrl,
  supabaseUrl: "https://iintlyrukrbuvqmjdeqg.supabase.co",
  supabaseAnonKey: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlpbnRseXJ1a3JidXZxbWpkZXFnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE3MzQ0ODAsImV4cCI6MjA5NzMxMDQ4MH0.cjCa9BYRQycD-AUOiM0CiEIQT4KDkWWtWCtFm3biqU0",
  whatsappPhone: "",
  whatsappMessage: "Ola, Lugano Sao Luis! Gostaria de atendimento.",
};
