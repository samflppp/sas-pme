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

// Textures en boucle : elles ne jouent que visibles à l'écran, et jamais si le système demande moins
// d'animation. Sans ce script, l'image fixe (poster) reste affichée.
(function () {
  "use strict";
  var videos = Array.prototype.slice.call(document.querySelectorAll("video.texture"));
  if (!videos.length || !("IntersectionObserver" in window)) return;
  var calme = window.matchMedia("(prefers-reduced-motion: reduce)");

  function jouer(v) {
    if (calme.matches) return;
    if (v.preload === "none") v.preload = "auto";
    var essai = v.play();
    if (essai && essai.catch) essai.catch(function () {});   // lecture refusée : le poster reste
  }

  var visibles = new Set();
  var guet = new IntersectionObserver(function (entrees) {
    entrees.forEach(function (e) {
      if (e.isIntersecting) { visibles.add(e.target); jouer(e.target); }
      else { visibles.delete(e.target); e.target.pause(); }
    });
  }, { rootMargin: "120px 0px" });
  videos.forEach(function (v) { guet.observe(v); });

  calme.addEventListener("change", function () {
    videos.forEach(function (v) { if (calme.matches) v.pause(); else if (visibles.has(v)) jouer(v); });
  });
})();
