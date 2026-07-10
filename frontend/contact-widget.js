(function () {
  const config = window.LUGANO_CONFIG || {};
  const rawPhone = String(config.whatsappPhone || "").replace(/\D/g, "");
  const message = config.whatsappMessage || "Ola, Lugano Sao Luis! Gostaria de atendimento.";
  const phone = rawPhone && rawPhone.startsWith("55") ? rawPhone : rawPhone ? `55${rawPhone}` : "";
  const url =
    config.whatsappUrl ||
    (phone ? `https://wa.me/${phone}?text=${encodeURIComponent(message)}` : "");

  if (!url) return;

  const link = document.createElement("a");
  link.className = "whatsapp-contact-button";
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.setAttribute("aria-label", "Fale conosco pelo WhatsApp");
  link.innerHTML = `
    <span class="whatsapp-contact-icon" aria-hidden="true">W</span>
    <span class="whatsapp-contact-copy">
      <small>Atendimento</small>
      <strong>Fale conosco</strong>
    </span>
  `;

  document.body.appendChild(link);
})();
