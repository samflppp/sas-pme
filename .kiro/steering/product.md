# Produit

## Phrase-problème

Les PME et startups qui développent installent chaque jour des paquets PyPI qu'aucune personne ne
relit, alors que la chaîne d'approvisionnement logicielle est devenue un vecteur d'attaque majeur
(ultralytics en décembre 2024, typosquats, mainteneurs compromis) ; elles n'ont ni RSSI ni SOC.

## Défenseur aidé

Le responsable technique d'une PME ou d'une startup qui développe en Python (5 à 100 personnes),
sans équipe sécurité. Canal de vente visé : l'infogérant.

## Proposition

Un sas local, posé entre le réseau de la PME et Internet :

1. il sert de miroir PyPI et cache toute version nouvelle pendant une quarantaine active ;
2. pendant la quarantaine, il analyse le paquet (code déterministe puis LLM local) et surveille ce
   que le monde en dit (bases de vulnérabilités, statut PyPI, blogs de chercheurs) ;
3. il observe les connexions sortantes des postes, sans les déchiffrer, et relie un domaine suspect
   au paquet installé juste avant.

## Principes non négociables

- **Le code décide, l'IA alerte et explique.** Un LLM peut monter un risque, jamais l'abaisser ni
  approuver une version.
- **Un texte lu n'est jamais une instruction.** Code de paquet, changelog, article : ce sont des
  données à juger.
- **On lit Internet, on ne lui parle pas de vous.** Ne sortent que des requêtes « nom de paquet +
  version » et des requêtes RDAP sur des domaines. Jamais le code, les données ni l'identité de la PME.
- **Tout est local.** Le LLM tourne sur le boîtier (Ollama). Aucun service cloud managé.
- **Transparent pour le développeur.** Une ligne de configuration ; `pip` ne voit jamais d'erreur à
  cause d'une quarantaine.

## Contexte

Hackathon, Track 3 « Open Track » (IA × cybersécurité, défensif), 34 h, porteur seul. Grille du jury :
importance et originalité du problème 25 %, efficacité défensive démontrée 25 %, impact 20 %, viabilité
20 %, pitch 10 %. Livrables : dépôt, vidéo de démo, deck, fiche de défense.
