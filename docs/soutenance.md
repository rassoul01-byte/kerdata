# Support de soutenance — KerData (Module 2)

*Généré par `run_pipeline.py` : chaque chiffre est relu dans `reports/` et `sortie/`. Règle d'or : répondre en 30 secondes, chiffrer, nommer la limite.*

## 0. Les 7 choses à savoir montrer en 30 secondes

| Demande du jury | Réponse chiffrée | Où l'ouvrir |
|---|---|---|
| Retrouver le chiffre d'une décision | 98 décisions numérotées (`0.1` à `9.8`), chacune avec sa preuve chiffrée | `docs/justifications.md` |
| Pipeline rechargé | `models/pipeline_preparation.joblib` rechargé dans un interpréteur neuf, prédictions identiques (écart 0) | `docs/pipeline.md`, notebook section 7 |
| Gain de `prix_m2` | seul : R² 0.881 (gain +0.135) ; avec `surface_log` : **R² = 0.99996** → fuite | `reports/comp6_candidates.csv` |
| Limite principale | le prix se prédit par la catégorie ; à l'intérieur d'une catégorie R² de -0.13 à +0.05 | décision 9.8 |
| Pourquoi `statut` est exclu | connu après la vente (fuite type 2) et proxy de la source (V = 0.58) | décisions 5.1, 8.3 |
| Pourquoi `source` est exclue | identifiant de flux (type 4) ; gain mesuré -0.0015 | décisions 5.2, 6.7, 8.4 |
| Une anomalie par source | voir section 1 | `sortie/quarantine.csv` |

## 1. Chiffres à connaître : lignes par source, avant et après nettoyage

| source | lues | propres | avertissements | quarantaine |
|---|---|---|---|---|
| agence | 640 | 614 | 17 | 9 |
| historique | 528 | 500 | 18 | 10 |
| notaires | 410 | 374 | 16 | 20 |
| particuliers | 731 | 575 | 20 | 136 |
| plateforme | 875 | 809 | 40 | 26 |

Total : **3184 lues → 2872 propres, 111 avertissements, 201 en quarantaine** (50.7 % conformes d'emblée, 90.2 % propres après traitement). Écart avec la fiche : 40 lignes d'agence manquent (640 lues pour 680).

**Une anomalie par source :**

| Source | Anomalie | Chiffre |
|---|---|---|
| `historique` | accents cassés (mojibake) | 211 lignes ; 14 formes distinctes, chacune rattachée à un seul nom du référentiel |
| `plateforme` | en-tête absent en ligne 1, répété en ligne 575 ; ID dupliqués | 1 ligne d'en-tête écartée ; 15 doublons exacts → quarantaine |
| `particuliers` | prix en texte (suffixe FCFA, `None FCFA`) et surfaces en mots | prix : 5 à convertir, 2 illisibles, 61 vides ; 136 lignes en quarantaine |
| `notaires` | statuts aux libellés variables, dates impossibles | statuts non harmonisés (`VENDU`, `Vente conclue`, `Acte signé`) : notaires 132 lignes ; 6 dates impossibles (`32/13/2024`) |
| `agence` | surfaces et prix négatifs ou nuls | 4 surfaces ≤ 0 et 5 prix ≤ 0 ; 9 lignes en quarantaine ; 40 lignes manquantes vs fiche |

## 2. Questions par compétence (réponses de 30 secondes)

### Compétence 1 — Types et statistiques
- **Skewness de `prix` avant/après log ?** Ventes : **1.86** → **-0.22**. Conséquence : on modélise `log(prix)`.
- **Pourquoi la médiane ?** La moyenne dépasse la médiane (ratio 1.40) à cause de la queue à droite ; la médiane résume le bien typique.
- **QQ-plot ?** Compare les quantiles à ceux d'une loi normale : `log(prix)` suit la diagonale par segment, le mélange ventes + locations montre une cassure (deux populations), d'où la segmentation.
- **Conséquence d'un mauvais typage ?** Un prix en texte (« 147.52 millions ») ferait planter ou fausser tout calcul ; ici 65 prix de `plateforme` sont à convertir et 6 illisibles (« à négocier »).
- **Prix en texte ?** `particuliers` : 5 convertibles + 2 illisibles ; `plateforme` : 65 convertibles + 6 illisibles.

### Compétence 2 — EDA
- **Insights ?** 5 (voir `docs/insights_comp2.md`) : `transaction` structurellement absente de 3 sources ; mojibake réparable ; Simpson actif ; pas de tendance ; lignes à écarter.
- **Simpson ?** Oui, sur `prix` ~ `surface` : corrélation globale 0.43, mais |r| ≤ 0.13 dans chaque catégorie. Conséquence : pas de `prix_m2`, pas de `surface` seule.
- **Mann-Kendall ?** p = 0.73 à 1.00 à 3 échelles : pas de tendance → split aléatoire.
- **Mécanisme des manquants ?** 100 % absent dans une source = structurel ; sinon khi2 contre catégorie/statut/transaction : p > 0,05 = aléatoire → quarantaine plutôt qu'imputation.
- **Source la plus anomalique ?** `particuliers` (136 des 201 lignes en quarantaine).

### Compétence 3 — Nettoyage
- **Quarantaine / avertissements par source ?** Tableau de la section 1 (201 / 111 au total).
- **Bloquante vs avertissement ?** Bloquante : la ligne n'est pas exploitable (prix, surface ou date absents/illisibles/≤ 0, doublon exact, date future + vendu). Avertissement : exploitable mais suspecte (hors fourchette, ville absente, doublon probable) : conservée et signalée.
- **Indicateur de manque ?** Non : `chambres_vide` + `sdb_vide` devinent la source (AUC 0.86) : fuite type 4.
- **Sort d'un outlier ?** Fourchette du référentiel de sa catégorie : hors fourchette mais plausible → avertissement (80 ventes), jamais supprimé ; l'IQR sert de confirmation seulement.
- **Doublon probable ?** Même bien vu par 2 sources (date, ville, catégorie, surface) : mesuré (0 trouvé) ; on signale, on ne fusionne jamais sans preuve.
- **Mojibake ?** Caractère de remplacement `�` ; on le remplace par le nom du référentiel **uniquement si le rattachement est unique** (14 formes sur 14) ; un motif ambigu n'est pas deviné.
- **Header dupliqué ?** Lecture sans en-tête, 15 noms imposés, ligne répétant l'en-tête écartée (ligne 575).
- **ID dupliqués dans `plateforme` ?** 15, tous identiques à la ligne d'origine : 1re occurrence conservée, copies en quarantaine (« doublon exact de plateforme:00xx »).
- **Surfaces négatives de `agence` ?** 4 lignes avec surface ≤ 0 : quarantaine, valeur brute conservée dans `quarantine.csv`.

> **Piège : pourquoi ne pas supprimer toutes les lignes avec des manquants ?** Les manquants structurels (`transaction`, `sdb`, `chambres`, `statut`) sont concentrés sur une source : supprimer ces lignes reviendrait à exclure la source entière (perte et biais). On distingue structurel, aléatoire et bloquant.
>
> **Piège : pourquoi ne pas garder la feuille `Params` d'Excel ?** C'est de la métadonnée (4 lignes), pas des annonces : elle corromprait le corpus ; seule la feuille `Annonces` est lue.

### Compétence 4 — Visualisations
- **Diagnostique vs restitution ?** La diagnostique cherche (exploration, comp 2) ; la restitution prouve une décision déjà prise, avec une conclusion chiffrée dans le titre.
- **Figure qui justifie `log(prix)` ?** V1 : skew 1.86 → -0.22.
- **Preuve du nettoyage ?** V5 : conformité 50.7 % → 90.2 %, mesurée sur les fichiers livrés (prix invalides 98 → 0, dates non ISO 965 → 0, accents cassés 211 → 0).
- **V6 : sources alignées ?** Oui après regroupement par catégorie (Kruskal prix p = 0.79, surface p = 0.54) ; en brut la surface de l'historique se détache par **effet de composition** (14.1 % de chambres). Conséquence : `source` n'entre pas dans le modèle et le split est stratifié.

### Compétence 5 — Encodage
- **One-hot et pas label encoding ?** `categorie` n'a pas d'ordre : un entier inventerait un ordre (Villa > Studio) que le modèle linéaire exploiterait.
- **`statut` ?** Exclu : `Vendu` est connu après la vente (type 2) ; V(source, statut) = 0.58 le rend proxy de la source ; aucun lien avec le prix (η² = 0.0011).
- **`source` ?** Exclue : identifiant de flux, η² sur le prix relatif = 0.0005 (aucun signal).
- **`commune` ?** Exclue du one-hot : 46 modalités, gain de variance expliquée de 0.56 point par rapport à la région ; frequency encoding testé en comp 6 : gain -0.0002.
- **Preuve d'absence de fuite ?** Fit sur le train : moyenne de `annee` = 0 sur le train, -0.0030 sur la validation ; fit sur la validation donnerait exactement 0.
- **`handle_unknown="ignore"` ?** Une modalité jamais vue en production (« Château ») donne une ligne de zéros au lieu d'une erreur.

> **Piège : pourquoi ne pas one-hot `commune` ? Elle contient peut-être de l'information.** 46 modalités, redondantes avec la région ; gain mesuré -0.0002 en CV : proche de 0.
>
> **Piège : pourquoi ne pas utiliser `source` en one-hot ?** Identifiant de flux, pas une caractéristique du bien. Gain mesuré -0.0015 : la fiche attendait un gain positif, il n'est pas observé ; on l'exclut quand même par principe (fuite type 4).

### Compétence 6 — Features
- **Créées ?** `distance_dakar_km`, `ville_frequence`, `surface_x_categorie`, `surface_par_chambre` (4) + 4 fuites volontaires + 2 audits.
- **Exclues ?** Toutes les créées (gain maximal en valeur absolue : 0.0027, bien sous le seuil de 0,01), plus `annee`, `mois`, `chambres_sdb`.
- **Meilleur gain ?** `region` : +0.0044 en R² CV, soit < 0,01 : neutre ; gardée par sens métier.
- **`prix_m2` ?** Seul : R² 0.881, gain +0.135 ; avec `surface_log` : **R² 0.99996**. Fuite type 1 : `prix_m2` contient la cible.
- **`source` en feature ?** Gain -0.0015 ; fuite type 4 ; exclue.
- **Mesure du gain ?** CV 5 plis sur le train seul, une candidate à la fois sur la baseline `categorie` (R² 0.74585), seuil ±0,01, confirmé par une forêt.

> **Piège : « votre modèle a un R² de 0,99, c'est excellent non ? »** Non : c'est un signal d'alarme. Une feature contient probablement `prix` (c'est ce que fait `prix_m2 + surface_log`, R² 0.99996) ou `source` a été gardée. Ici `garde_score` interrompt tout R² > 0,95, et notre modèle légitime plafonne à 0.73.
>
> **Piège : `est_hors_fourchette` a un gain de +0.022 > 0,01, on la garde ?** Non : elle est dérivée de `prix`. Un seuil seul aurait gardé une fuite : le rejet de principe passe avant la mesure.

### Compétence 7 — Split
- **Ratio ?** 70/15/15 : 1773 / 380 / 381 ventes ; ≥ 22 biens par catégorie dans chaque ensemble.
- **Aléatoire ou temporel ?** Aléatoire : Mann-Kendall p = 0.73 à 1.00 (annuel, mensuel, par vente).
- **Test scellé ?** Empreinte SHA-256 de ses 381 lignes (`sortie/test_scelle.json`, `416abcd763c5…`) ; modifier un prix ou déplacer une ligne change l'empreinte ; aucun module hors `split.py` et `comp7.py` ne lit le test (testé).
- **Stratifier par `categorie` ?** Elle explique 74 % de la variance : sans stratification, une petite catégorie pourrait manquer au test.
- **5 sources dans chaque ensemble ?** Oui : effectifs agence 367/79/79, historique 363/77/78, notaires 274/58/58, particuliers 295/63/65, plateforme 474/103/101 (train/val/test) ; écart maximal 0.60 point.
- **Relancer le split ?** Mêmes lignes : graine 42, testé (graine 43 donne un autre split).

> **Piège : les sources ne couvrent pas les mêmes périodes, un split aléatoire est-il correct ?** Oui si Mann-Kendall ne détecte pas de tendance (p > 0,05), mais il faut vérifier les effectifs par source. Ici, stratifié sur `categorie` seule, l'écart par source dépassait 2 points : on a ajouté `source` à la stratification (écart final 0.60 point).

### Compétence 8 — Anti-fuite
- **Les 4 types, un cas réel chacun :** 1 `prix_m2` (R² 0.99996) ; 2 `statut` = `Vendu` (connu après la vente) ; 3 un scaler fitté sur tout le jeu (contre-épreuve : fit sur la validation → moyenne exactement 0) ; 4 `source`, `annee+mois` (AUC 0.65), indicateurs de manque (AUC 0.86).
- **Fuite de type 2 ?** `statut` (`Vendu`, `Vente conclue`, `Acte signé`, `Loué`) et `date` pour notaires/historique (date d'acte ou de vente).
- **Vérifier qu'un scaler n'est pas fitté sur tout ?** Un espion en tête du pipeline enregistre les lignes vues au fit : 1773 vues, 0 de validation ou test.
- **Prévenir le type 4 ?** Tester si les features devinent la source : features finales AUC 0.543 (hasard = 0,5), précision 0.273 contre 0.267.
- **Détecter une fuite sans la voir ?** Un score suspect (R² > 0,95 pour un prix immobilier) déclenche l'audit.
- **Pourquoi retirer `date_expiration`, `quartier`, `description` ?** Colonnes renseignées dans une seule source : leur présence **est** la source (V de Cramér = 1,00). Elles sont absentes des 4 fichiers de sortie ; seule la trace brute les garde. *Écart assumé : la fiche demande de les retirer avant la concaténation.*

### Compétence 9 — Pipeline
- **Dans le pipeline ?** `normalisation` → `preparation` (one-hot 7 + 14, log1p/RobustScaler sur la surface) → `Ridge`, cible `log(prix)` : 22 colonnes.
- **Hors pipeline ?** Nettoyage de la comp 3, inférence de `transaction`, split : règles ou décisions sur le corpus, rejouées par `run_pipeline.py` (concaténation des 5 sources incluse).
- **Reproductible ?** Deux exécutions complètes : mêmes coefficients (`1bc3b7192d92c61e`), mêmes prédictions ; sur un clone neuf, `run_pipeline.py` ne modifie aucun fichier suivi.
- **Nouvelle modalité ?** Ignorée (ligne de zéros), sans erreur ; surface absente ou illisible : refus explicite.
- **Sérialisation ?** `joblib` ; rechargé dans un interpréteur neuf : écart 0 sur 60 lignes de validation et 60 de test.
- **`particuliers` (JSON imbriqué) vs `plateforme` (CSV) ?** `adapter_ligne(source, ligne)` aplatit `annonce.details.surface` ou renomme les colonnes natives, puis le même pipeline s'applique ; testé sur une ligne brute de chacune des 5 sources.

## 3. Questions transverses (honnêteté)

- **Décision la plus hésitée ?** Garder `surface_log` : gain neutre (-0.0011) mais la forêt perd 0.043 ; gardée par sens métier et parce que le modèle final est linéaire.
- **Ce que je changerais ?** Mettre en quarantaine les 4 ventes datées de 2028 (conservées en avertissement) ; je ne l'ai pas fait pour ne pas modifier le corpus après le scellé du test.
- **Limite principale ?** Le modèle fait à peine mieux que la médiane de la catégorie : R² log 0.731 contre 0.713 sur le test, erreur médiane 35.9 % contre 34.1 %. Les données sont synthétiques : la surface n'explique rien à l'intérieur d'une catégorie.
- **Avec deux fois plus de temps ?** Enrichir les features intra-catégorie (quartier, état, étage), modéliser les loyers séparément, valider dans le temps.
- **Hypothèse la plus fragile ?** Le seuil de 3 M FCFA entre ventes et locations : 0 erreur sur 1537 lignes connues et confirmé par le statut, mais choisi en regardant tout le corpus, test compris.
- **Gérer 5 sources sans perdre le fil ?** Un schéma commun, `source` conservée pour l'audit seulement, un registre de décisions numérotées et un script unique rejouable.

## 4. Trois slides

1. **Nettoyage** : tableau de la section 1, V5 (50.7 % → 90.2 %), une anomalie par source.
2. **Features** : tableau des 15 candidates (`reports/comp6_candidates.csv`), le mirage `prix_m2` (R² 0.99996), l'AUC de détection de la source.
3. **Pipeline** : schéma `normalisation → préparation → Ridge`, rechargement en direct, résultat du test (0.731, évalué une seule fois) et limites.

## 5. À ouvrir à la demande

```
head sortie/quarantine.csv sortie/avertissements.csv sortie/donnees_propres.csv
grep "^| 6.6" docs/justifications.md
PYTHONPATH=src python -c "import joblib; m = joblib.load('models/pipeline_preparation.joblib'); print(m)"
```

## 6. Réponses à ne jamais donner

« C'est la méthode » · « Je ne sais pas » (dire : *je n'ai pas mesuré, voici comment je le ferais*) · « Ça marche bien » sans chiffre · « C'est mieux » sans comparaison · inventer un chiffre · « j'ai suivi le tutoriel ».
