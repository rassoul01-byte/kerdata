# Insights de la compétence 2 → actions en compétence 3

1. **`transaction` manque à 100 % dans agence, historique et notaires (1 578 lignes) : mécanisme structurel.**
   Imputation par seuil de prix (3 M FCFA ; 0 erreur sur les 1 537 lignes à transaction connue), provenance tracée,
   **pas d'indicateur de manque** (il révélerait la source : fuite type 4, comp 8). Les ~111 loyers de l'agence
   sortent du modèle de prix de vente.

2. **Mojibake : 208 lignes, toutes dans `historique` (3 formes de région, 11 de ville).**
   Chaque forme se rattache à un seul nom du référentiel géographique : correction fiable à faire en priorité
   (avant jointure et avant re-mesure des doublons inter-sources, aujourd'hui à 0).

3. **Paradoxe de Simpson actif sur `prix` ~ `surface` (global ρ = 0,43 ; par catégorie |ρ| < 0,14, p > 0,09).**
   Ne pas créer `prix_m2` (dérivé de la cible, fuite type 1) ; ne pas utiliser `surface` seule ;
   tester l'interaction `categorie × surface` en comp 6. La catégorie explique 74 % de la variance de log(prix).

4. **Aucune tendance temporelle (p ≥ 0,17 à 4 échelles ; 96 mois sur 96 couverts).**
   Split aléatoire acceptable en comp 7, stratifié sur `categorie` (et `source`, l'historique ne couvrant que 2018-2020).

5. **Lignes à écarter ou à signaler : plateforme 15 doublons exacts (garder la 1re occurrence) et 5 dates futures ;
   prix/surface absents ou non interprétables (MCAR) → quarantaine ; 80 prix hors fourchette indicative (3,1 %) →
   avertissement seulement ; 4 paires région/ville incohérentes → signalées, non corrigées.**
