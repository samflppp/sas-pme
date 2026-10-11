// Page « Direct » : l'avancement de chaque version d'une demande, reçu en Server-Sent Events.
// Tout est construit avec textContent : rien de ce que dit la pipeline n'est lu comme du HTML.
(function () {
  "use strict";
  var racine = document.querySelector(".direct[data-demande]");
  if (!racine) return;
  var demande = racine.getAttribute("data-demande");
  var conteneur = document.getElementById("versions-suivies");
  var voyant = document.getElementById("voyant");

  function el(balise, classe, texte) {
    var n = document.createElement(balise);
    if (classe) n.className = classe;
    if (texte) n.textContent = texte;
    return n;
  }

  function version(v) {
    var s = el("section", "version-suivie");
    s.setAttribute("data-sujet", v.sujet);
    var tete = el("header");
    var lien = el("a");
    lien.href = v.lien;
    lien.appendChild(el("strong", "", v.nom));
    lien.appendChild(document.createTextNode(" "));
    lien.appendChild(el("code", "", v.version));
    tete.appendChild(lien);
    tete.appendChild(document.createTextNode(" "));
    tete.appendChild(el("span", "etat etat-" + v.etat, v.libelle));
    s.appendChild(tete);
    var liste = el("ol", "etapes");
    v.etapes.forEach(function (e) {
      var li = el("li", "etape " + e.etat);
      li.setAttribute("data-cle", e.cle);
      var puce = el("span", "puce");
      puce.setAttribute("aria-hidden", "true");
      li.appendChild(puce);
      var corps = el("div");
      corps.appendChild(el("strong", "", e.titre));
      if (e.duree) { corps.appendChild(document.createTextNode(" ")); corps.appendChild(el("span", "duree", e.duree)); }
      if (e.detail) corps.appendChild(el("p", "detail", e.detail));
      if (e.texte) corps.appendChild(el("p", "pensee" + (e.etat === "en_cours" ? " ecrit" : ""), e.texte));
      li.appendChild(corps);
      liste.appendChild(li);
    });
    s.appendChild(liste);
    return s;
  }

  function afficher(i) {
    var neuf = document.createDocumentFragment();
    i.versions.forEach(function (v) { neuf.appendChild(version(v)); });
    if (!i.versions.length) neuf.appendChild(el("p", "vide", "Aucune nouvelle version : tout était déjà connu."));
    conteneur.replaceChildren(neuf);
  }

  function etat(texte, enDirect) {
    voyant.textContent = texte;
    voyant.classList.toggle("en-direct", enDirect);
  }

  if (!("EventSource" in window)) {          // repli : on relit l'instantané toutes les 2 s
    etat("Mise à jour toutes les 2 s", false);
    setInterval(function () {
      fetch("/direct/instantane?demande=" + demande, { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (i) { if (i) afficher(i); });
    }, 2000);
    return;
  }
  var flux = new EventSource("/direct/flux?demande=" + encodeURIComponent(demande));
  flux.onopen = function () { etat("En direct", true); };
  flux.onmessage = function (m) {
    try { afficher(JSON.parse(m.data)); } catch (e) { /* message illisible : on garde l'affichage */ }
  };
  flux.onerror = function () { etat("Reconnexion…", false); };
})();
