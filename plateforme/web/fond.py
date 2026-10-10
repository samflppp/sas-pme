"""Tâche de fond du web (A) : appelle une fonction en boucle, sur un fil à elle.

Un seul fil, donc jamais deux appels en même temps : l'appel suivant part `intervalle` secondes
après la fin du précédent, même si celui-ci a dépassé l'intervalle (téléchargement + sandbox).
Une erreur est écrite sur stderr et la boucle continue.
"""
import sys
import threading
from collections.abc import Callable


class TacheDeFond:
    def __init__(self, fonction: Callable[[], object], intervalle: float, nom: str = "traitement"):
        self._fonction = fonction
        self._intervalle = intervalle
        self._nom = nom
        self._arret = threading.Event()
        self._fil: threading.Thread | None = None

    def demarrer(self) -> None:
        self._arret.clear()
        self._fil = threading.Thread(target=self._boucle, name=f"sas-{self._nom}", daemon=True)
        self._fil.start()

    def arreter(self, delai: float = 5.0) -> None:
        """Demande l'arrêt et attend au plus `delai` s la fin de l'appel en cours."""
        self._arret.set()
        if self._fil is not None:
            self._fil.join(delai)

    def vivante(self) -> bool:
        return self._fil is not None and self._fil.is_alive()

    def _boucle(self) -> None:
        while not self._arret.is_set():
            try:
                self._fonction()
            except Exception as e:  # noqa: BLE001 — une erreur ne doit pas tuer la boucle
                print(f"[sas-pme] {self._nom} : {e!r}", file=sys.stderr)
            self._arret.wait(self._intervalle)
