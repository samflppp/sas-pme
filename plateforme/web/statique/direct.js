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

  var ecran = document.getElementById("ecran-serveur");

  function ligne(classe, morceaux) {
    var p = el("p", classe);
    morceaux.forEach(function (m) {
      if (typeof m === "string") p.appendChild(document.createTextNode(m));
      else p.appendChild(el("span", m[0], m[1]));
    });
    return p;
  }

  function terminal(s, nom) {
    var f = document.createDocumentFragment();
    if (!s || !s.configure) {
      f.appendChild(ligne("t-note", ["Passerelle non configurée : aucun serveur n'est relié à cette plateforme."]));
      return f;
    }
    var cmd = [["t-invite", "serveur:~$"], " " + s.commande];
    if (s.demandee_a) cmd.push(" ", ["t-heure", s.demandee_a]);
    f.appendChild(ligne("t-cmd", cmd));
    f.appendChild(ligne("t-note", ["# " + (s.manuel ? "registre" : "index") + " : " + s.index +
      " : seule source de paquets, pas de repli vers " + s.repli]));
    if (s.manuel) f.appendChild(ligne("t-note", ["# à taper sur le serveur : l'agent de la démo n'installe que les paquets pip"]));
    if (s.erreur) f.appendChild(ligne("t-erreur", ["✗ " + s.erreur]));
    s.lignes.forEach(function (x) {
      f.appendChild(ligne("t-ligne", [["t-heure", x.a], " ", ["t-ip", x.ip], " " + x.texte]));
    });
    if (s.installee) f.appendChild(ligne("t-ok", ["✓ " + nom + " " + s.installee + " installée : la dernière version vérifiée et signée"]));
    else if (s.reessaie) f.appendChild(ligne("t-attente", ["pas encore servie : le serveur réessaie dès que la version est publiée…"]));
    else if (s.aucune_servie) f.appendChild(ligne("t-erreur", ["✗ " + "aucune version de " + nom + " n'est servie par la passerelle : pip n'installe rien"]));
    else if (!s.erreur && !s.manuel) f.appendChild(ligne("t-attente", ["en attente des requêtes du serveur…"]));
    if (s.amont) {
      f.appendChild(ligne("t-amont", ["↳ " + s.amont.version + " sur PyPI : " + s.amont.libelle +
        (s.amont.detail ? ", " + s.amont.detail : "") + ". Pas servie aux serveurs."]));
    }
    return f;
  }

  function afficher(i) {
    if (ecran) ecran.replaceChildren(terminal(i.serveur, i.nom));
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
