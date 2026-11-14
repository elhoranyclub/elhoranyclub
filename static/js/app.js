/* مركز شباب الحوراني — progressive enhancement only.
   Alpine.js handles sheets/menus; this file adds tiny global helpers. */
(function () {
  "use strict";

  // Footer year
  document.querySelectorAll("[data-year]").forEach(function (el) {
    el.textContent = new Date().getFullYear();
  });

  // Global Escape closes any open sheet (Alpine listens for its own state,
  // this is a belt-and-braces for keyboard users)
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      document.dispatchEvent(new CustomEvent("app:close-sheet"));
    }
  });

  // Offline indicator
  const bar = document.getElementById("offline-bar");
  const toggleBar = () => { if (bar) bar.hidden = navigator.onLine; };
  window.addEventListener("online", toggleBar);
  window.addEventListener("offline", toggleBar);
  toggleBar();

  // Auto-dismiss Django message toasts after 5s (Alpine also handles click)
  window.setTimeout(function () {
    document.querySelectorAll("[data-toast]").forEach(function (t) {
      t.style.opacity = "0";
      t.style.transform = "translateY(8px)";
      window.setTimeout(function () { t.remove(); }, 350);
    });
  }, 5000);
})();
