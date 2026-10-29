# Registre des décisions — ImmoAnalyse (Module 2)

Règle : chaque décision = une preuve chiffrée, notée au moment où elle est prise.

| # | Date | Compétence | Source | Question | Mesure / preuve | Décision | Règle métier |
|---|------|------------|--------|----------|-----------------|----------|--------------|
| 0.1 | 2026-10-29 | Étape 0 | plateforme | Où est l'en-tête dupliqué ? | 876 lignes brutes ; en-tête en ligne 575 uniquement (absent en ligne 1) ; 875 lignes de données = fiche | Lecture `header=None`, 15 noms imposés, ligne d'en-tête écartée | Critère 1 (lecture) |
| 0.2 | 2026-10-29 | Étape 0 | historique | L'encodage est-il récupérable ? | Fichier UTF-8 valide mais 272 caractères U+FFFD (ex. `Thi�s` ×45, `S�dhiou` ×56) : l'accent est perdu dans le fichier | Lecture telle quelle ; reconstruction des noms via `referentiel_geographique.csv` renvoyée à la compétence 3 (à prouver, sans correction aveugle) | Normalisable (région/ville) |
| 0.3 | 2026-10-29 | Étape 0 | particuliers | Tous les enregistrements ont-ils le même schéma ? | 731/731 avec enveloppe `annonce` et les 11 mêmes chemins | Aplatissement `localisation.*` et `details.*` ; valeurs `null` → chaîne vide | Critère 1 |
| 0.4 | 2026-10-29 | Étape 0 | agence | Volume conforme à la fiche ? | 640 lignes lues vs 680 annoncées (−40) ; 0 ligne vide ; feuille `Params` = 4 lignes de métadonnées | Écart documenté, non comblé ; seul écart du corpus (3184 vs 3224) | Critère 9 (limites reconnues) |
| 0.5 | 2026-10-29 | Étape 0 | plateforme | `pieces` = `chambres` ? | Définitions différentes (pièces ≠ chambres) | Colonne `pieces` conservée à part, non mappée sur `chambres` | Dictionnaire de données |
| 0.6 | 2026-10-29 | Étape 0 | toutes | Typage à la lecture ? | Prix/dates contiennent du texte (`147.52 millions`, `05/06/2018`) | Tout lu en texte, aucune inférence ; conversion en compétence 3 | Règles normalisables |
| 0.7 | 2026-10-29 | Étape 0 | corpus | Doublons d'identifiant ? | 15 couples `(source, id)` dupliqués sur 3184 lignes | Aucun traitement ici ; analyse en compétence 3 (exact vs probable) | Avertissements : doublons |
