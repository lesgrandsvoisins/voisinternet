/* Voisinternet — petits comportements ; le site fonctionne sans JavaScript. */
(function () {
  "use strict";

  function armToasts() {
    document.querySelectorAll(".toast").forEach(function (toast) {
      if (toast.dataset.armed) return;
      toast.dataset.armed = "1";
      var close = document.createElement("button");
      close.type = "button";
      close.className = "toast-close";
      close.setAttribute("aria-label", "Fermer le message");
      close.textContent = "×";
      close.addEventListener("click", function () { toast.remove(); });
      toast.appendChild(close);
      // Le numéro de compte reste affiché jusqu'à ce qu'on le ferme : il ne sera plus jamais montré.
      if (!toast.classList.contains("toast-number")) {
        setTimeout(function () { toast.remove(); }, 6000);
      }
    });
  }

  function closeMenu(focus) {
    var menu = document.querySelector("details.menu[open]");
    if (!menu) return;
    menu.removeAttribute("open");
    if (focus) menu.querySelector("summary").focus();
  }

  function closeAccountPanel() {
    var panel = document.querySelector("details.account-panel[open]");
    if (!panel) return;
    panel.removeAttribute("open");
  }

  function closeQuicknavGroups(except) {
    document.querySelectorAll("details.quicknav-group[open]").forEach(function (d) {
      if (d !== except) d.removeAttribute("open");
    });
  }

  document.addEventListener("DOMContentLoaded", armToasts);
  document.addEventListener("htmx:afterSettle", armToasts);
  // Un seul menu déroulant (mes/nous/…) ouvert à la fois dans la barre du haut.
  document.addEventListener("toggle", function (e) {
    if (e.target.matches && e.target.matches("details.quicknav-group") && e.target.open) {
      closeQuicknavGroups(e.target);
    }
  }, true);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { closeMenu(true); closeAccountPanel(); closeQuicknavGroups(); }
  });
  document.addEventListener("click", function (e) {
    var menu = document.querySelector("details.menu[open]");
    if (menu && !menu.contains(e.target)) closeMenu(false);

    var accountPanel = document.querySelector("details.account-panel[open]");
    if (accountPanel && !accountPanel.contains(e.target)) closeAccountPanel();

    document.querySelectorAll("details.quicknav-group[open]").forEach(function (d) {
      if (!d.contains(e.target)) d.removeAttribute("open");
    });
  });
})();
