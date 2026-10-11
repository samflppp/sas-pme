// Onglets du rapport : marque la page en cours de lecture (aria-current). Sans ce script, les
// onglets restent de simples ancres : rien ne casse.
(function () {
  "use strict";
  var liens = Array.prototype.slice.call(document.querySelectorAll(".onglets a"));
  var pages = Array.prototype.slice.call(document.querySelectorAll("main .page"));
  if (!liens.length || !pages.length) return;
  var actif = null;

  function activer(id) {
    if (id === actif) return;
    actif = id;
    liens.forEach(function (a) {
      if (a.getAttribute("href") === "#" + id) {
        a.setAttribute("aria-current", "true");
        var boite = a.parentNode.parentNode;          // l'onglet actif reste visible sur mobile
        boite.scrollLeft = a.offsetLeft - boite.clientWidth / 2 + a.clientWidth / 2;
      } else {
        a.removeAttribute("aria-current");
      }
    });
  }

  var prevu = false;
  function suivre() {
    prevu = false;
    var repere = 140;                                   // sous la barre et les onglets
    var id = pages[0].id;
    pages.forEach(function (p) { if (p.getBoundingClientRect().top <= repere) id = p.id; });
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) {
      id = pages[pages.length - 1].id;                  // tout en bas : la dernière page
    }
    activer(id);
  }
  window.addEventListener("scroll", function () {
    if (!prevu) { prevu = true; window.requestAnimationFrame(suivre); }
  }, { passive: true });
  window.addEventListener("resize", suivre);
  suivre();
})();
