# Rapport de qualité — KerData (corpus de 5 sources)

Généré automatiquement par `run_pipeline.py`. Chaque ligne des 3184 lignes lues finit dans **un seul** fichier.

## Bilan global

| Fichier | Lignes | Part |
|---|---|---|
| `donnees_propres.csv` | 2872 | 90.2 % |
| `avertissements.csv` (conservées, signalées) | 111 | 3.5 % |
| `quarantine.csv` (rejetées, avec raison) | 201 | 6.3 % |
| **Total** | **3184** | 100 % |

Corpus conservé (propres + avertissements) : **2983 lignes** (93.7 %), fichier `corpus_conserve.csv`.

## Les 6 mesures obligatoires

| # | Mesure | Valeur |
|---|---|---|
| 1 | Taux de manquants par colonne (état initial, toutes sources) | voir tableau « Manquants » ; colonnes les plus vides : transaction 49.6 %, chambres 27.5 %, statut 16.6 %, sdb 12.9 %, surface 2.5 %, prix 2.4 % |
| 2 | Doublons exacts | **15** (tous dans `plateforme`, identifiants dupliqués) |
| 3 | Doublons probables / conflits entre sources | **0** probables, **0** conflits (clé : date + ville + catégorie + surface, après correction du mojibake) |
| 4 | Erreurs de conversion par champ | prix **18**, surface **4**, date **6** (valeurs non vides non convertibles) |
| 5 | Corrigés / quarantaine / avertissements | **1407** lignes corrigées (1740 corrections tracées dans `journal_corrections.csv`) / **201** / **111** |
| 6 | Taux d'enregistrements entièrement conformes | **50.7 %** conformes d'emblée (sans correction ni alerte), **90.2 %** propres après corrections |

## Manquants : mécanisme et traitement

| source | champ | vides | non_convertibles | pct_manquants_ou_illisibles | mecanisme | traitement |
|---|---|---|---|---|---|---|
| agence | transaction | 640 | 0 | 100.0 | structurel (100 % absent dans la source) | imputée par seuil de prix (3 M FCFA), provenance tracée, SANS indicateur de manque (fuite type 4) |
| historique | transaction | 528 | 0 | 100.0 | structurel (100 % absent dans la source) | imputée par seuil de prix (3 M FCFA), provenance tracée, SANS indicateur de manque (fuite type 4) |
| historique | ville | 8 | 0 | 1.5 | aléatoire (MCAR plausible) | conservée avec avertissement (région présente) |
| historique | prix | 0 | 10 | 1.9 | aléatoire (MCAR plausible) | quarantaine (règle bloquante) : jamais imputé, c'est la cible |
| historique | statut | 528 | 0 | 100.0 | structurel (100 % absent dans la source) | conservé vide : source qui ne le fournit pas ; pas d'indicateur de manque |
| notaires | date | 0 | 6 | 1.5 | aléatoire (MCAR plausible) | quarantaine (règle bloquante) |
| notaires | transaction | 410 | 0 | 100.0 | structurel (100 % absent dans la source) | imputée par seuil de prix (3 M FCFA), provenance tracée, SANS indicateur de manque (fuite type 4) |
| notaires | prix | 14 | 0 | 3.4 | aléatoire (MCAR plausible) | quarantaine (règle bloquante) : jamais imputé, c'est la cible |
| notaires | sdb | 410 | 0 | 100.0 | structurel (100 % absent dans la source) | conservé vide ; imputation par groupe dans le pipeline (fit sur train, comp 5/7), sans indicateur de manque |
| particuliers | prix | 61 | 2 | 8.6 | aléatoire (MCAR plausible) | quarantaine (règle bloquante) : jamais imputé, c'est la cible |
| particuliers | surface | 75 | 4 | 10.8 | aléatoire (MCAR plausible) | quarantaine (règle bloquante) |
| plateforme | prix | 0 | 6 | 0.7 | aléatoire (MCAR plausible) | quarantaine (règle bloquante) : jamais imputé, c'est la cible |
| plateforme | surface | 5 | 0 | 0.6 | aléatoire (MCAR plausible) | quarantaine (règle bloquante) |
| plateforme | chambres | 875 | 0 | 100.0 | structurel (100 % absent dans la source) | conservé vide ; imputation par groupe dans le pipeline (fit sur train, comp 5/7), sans indicateur de manque |

## Doublons

| type | nombre | decision |
|---|---|---|
| exact (intra-source) | 15 | supprimé du corpus (mis en quarantaine, 1re occurrence conservée) |
| ID dupliqué, contenu différent | 0 | conservé avec avertissement (arbitrage manuel) |
| probable inter-sources (même date, ville, catégorie, surface) | 0 | signalé, jamais fusionné sans preuve |
| conflit (même bien, prix à plus de 20 %) | 0 | signalé seulement |

## Aberrants

| champ | methode | decision | nombre |
|---|---|---|---|
| prix | fourchette du référentiel catégoriel | avertissement (plausible) | 80 |
| surface | fourchette typique du référentiel | avertissement | 3 |
| prix | seuils atypiques (<100 k ou >2 Md, ventes) | avertissement | 0 |
| surface | seuils atypiques (<5 ou >2000 m²) | avertissement | 0 |
| prix | prix <= 0 | quarantaine | 5 |
| surface | surface <= 0 | quarantaine | 4 |
| prix | IQR par catégorie sur log(prix) (confirmation) | confirmation seulement, aucune action | 9 |
| prix | … dont hors fourchette du référentiel | recoupement des 2 méthodes | 1 |

Détail par source : `reports/comp3_outliers.csv`.

## Motifs de quarantaine

| motif | lignes |
|---|---|
| surface absente | 80 |
| prix absent | 75 |
| prix non numérique | 18 |
| doublon exact | 15 |
| date non interprétable ou absente | 6 |
| prix <= 0 | 5 |
| surface <= 0 | 4 |
| surface non numérique | 4 |
| date future pour une vente conclue | 1 |

## Motifs d'avertissement

| motif | lignes |
|---|---|
| prix hors fourchette du référentiel (plausible) | 80 |
| statut incohérent avec la transaction | 14 |
| ville absente | 8 |
| région et ville incompatibles (non corrigé) | 4 |
| date future (non vendue) | 4 |
| surface hors fourchette typique de la catégorie | 3 |

## Transaction inférée : validation par le statut

La colonne `transaction` est absente de 3 sources ; elle est inférée par seuil de prix (3 M FCFA, 0 erreur sur les lignes à transaction connue).
Contrôle indépendant : dans les sources étiquetées, `Loué` (168 lignes) et `Disponible` (214 lignes) n'apparaissent qu'avec des locations (0 avec une vente). Pour `notaires`, seul `Vendu` existe : le contrôle ne vaut que pour l'agence (106 loyers confirmés par leur statut) ; `historique` n'a pas de statut et n'est donc pas contrôlable.

| source | transaction_inferee | lignes_inferees | confirmees_par_statut | pct_confirme |
|---|---|---|---|---|
| agence | location | 106 | 106 | 100.0 |
| agence | vente | 529 | 529 | 100.0 |
| notaires | vente | 396 | 396 | 100.0 |

## Limites reconnues

- **Volume agence :** 640 lignes lues pour 680 annoncées dans la fiche de conception (−40) ; non comblé.
- **Quarantaine volontairement stricte :** 98 lignes sans prix exploitable et 88 sans surface exploitable (absentes ou illisibles) sont rejetées par la règle bloquante, même si certaines surfaces seraient imputables ; 67.7 % de la quarantaine vient de `particuliers`.
- **Transaction inférée** pour 1549 lignes : fondée sur un seuil validé, mais reste une inférence (colonne `transaction_origine`).
- **Doublons probables inter-sources : 0** sur la clé stricte ; des doublons dont la date, la ville ou la surface diffèrent légèrement ne seraient pas vus.
- **Fourchettes du référentiel indicatives :** les prix hors fourchette sont conservés en avertissement, jamais supprimés.
- **Colonnes écartées du corpus final :** `quartier`, `pieces`, `description`, `date_expiration`, `commercial`, `devise` (propres à une source ou redondantes avec `transaction`).
- **Aucune imputation ici :** `chambres` et `sdb` restent vides là où la source ne les fournit pas ; l'imputation par groupe se fera dans le pipeline, ajustée sur le train uniquement.

## Visualisations de restitution (compétence 4)

Données : **corpus conservé** (`corpus_conserve.csv` = propres + avertissements), segment `vente` : 2534 ventes.
Écart assumé avec la fiche, qui cite `donnees_propres.csv` : les 80 prix hors fourchette plausibles sont gardés en avertissement (décision 3.9) ;
les retirer tronquerait la queue de prix (skew 1.86 avec eux, 1.77 sans) et rendrait V1/V2 circulaires.

![v1_distribution_cible](../reports/figures/v1_distribution_cible.png)

**Conclusion V1.** Le skew de `prix` est de **1.86** (moyenne 104.6 M contre médiane 74.7 M) ; il tombe à **-0.22** avec `log(prix)`. Décision confirmée : la cible est `log(prix)` sur le segment vente. *Justifie les décisions 1.8 et 3.9.*

![v2_prix_par_categorie](../reports/figures/v2_prix_par_categorie.png)

**Conclusion V2.** La médiane passe de 11.7 M (Chambre) à 266.0 M (Villa), soit **×22.7** ; la catégorie explique **74 %** de la variance de log(prix). `categorie` est la variable prioritaire (one-hot en comp 5/6). *Justifie 3.3 et 3.9.*

![v3_simpson_donnees_propres](../reports/figures/v3_simpson_donnees_propres.png)

**Conclusion V3.** `r` global = **0.43** ; `r` moyen par catégorie = **-0.02** (|r| max = 0.12, p minimum = 0.14) : le paradoxe de Simpson reste actif sur les données conservées. Implications : **pas de `prix_m2`** (dérivé de la cible, fuite type 1) et **pas de `surface` seule** ; tester l'interaction `categorie × surface` en comp 6. *Justifie 3.4, 3.5 et 2.7.*

![v4_matrice_correlation](../reports/figures/v4_matrice_correlation.png)

**Conclusion V4.** **Aucune paire** au-dessus de |r| = 0,8 (plus forte corrélation : log(prix) / log(surface), |r| = 0.43, calculée sur 1466 lignes complètes). Les corrélations de `sdb` et de `chambres` avec le prix sont des effets de composition (voir V3) : vérifier le VIF en comp 5/6. *Justifie 3.13.*

![v5_preuve_nettoyage](../reports/figures/v5_preuve_nettoyage.png)

**Conclusion V5.** Conformité globale de **50.7 %** avant (lignes sans aucune correction ni alerte) à **90.2 %** après (lignes propres, corrections tracées) ; les 9.8 % restants sont 201 lignes en quarantaine et 111 avertissements. Mesures « après » relues depuis `corpus_conserve.csv`, pas depuis les objets internes.

| Indicateur | Avant | Après |
|---|---|---|
| Prix absents, illisibles ou <= 0 | 98 | 0 |
| Surfaces absentes, illisibles ou <= 0 | 88 | 0 |
| Dates non ISO ou impossibles | 965 | 0 |
| Lignes avec accents cassés (�) | 211 | 0 |
| Catégories hors vocabulaire | 157 | 0 |
| Statuts non harmonisés | 132 | 0 |
| Doublons exacts (même id, même source) | 15 | 0 |
| Prix hors fourchette référentiel (ventes) | 80 | 0 (80 signalés) |
| Lignes en quarantaine (motif écrit) | 0 | 201 |
| chambres vides (%) | 27.5 | 28.5 |
| sdb vides (%) | 12.9 | 13.1 |
| Lignes | 3184 | 2983 conservées |

*Justifie 3.1 à 3.6.*

![v6_comparaison_sources](../reports/figures/v6_comparaison_sources.png)

**Conclusion V6.** Après alignement par catégorie, les 5 sources sont **comparables** : Kruskal sur le prix p = 0.79, sur la surface p = 0.54. En brut, la surface de l'`historique` (KS p < 0,0001) et de l'`agence` (KS p = 0.0037) se détache, mais c'est un **effet de composition** (khi2 catégorie × source p = 3e-46) : l'historique contient 14.1 % de chambres contre 2.1–5.9 % dans les autres sources. Source atypique : **`historique`** (mélange de catégories uniforme, période 2018-2020 seulement, ni `statut` ni `transaction`) ; elle ne l'est ni par le niveau de prix ni, une fois alignée par catégorie, par la surface. **Décision pour comp 5 et 7 :** ne pas utiliser `source` comme variable explicative (fuite type 4) et stratifier le split sur `categorie` ; `source` ne sert qu'à l'audit. *Justifie 3.2, 3.3 et 3.12.*

### Cohérence avec les diagnostics de la comp 2

| Indicateur | Comp 2 (données brutes) | Comp 4 (données conservées) |
|---|---|---|
| skew de prix (ventes) | 1.86 | 1.86 |
| skew de log(prix) | -0.22 | -0.22 |
| ratio médiane villa / chambre | ×22.5 | ×22.7 |
| corrélation prix ~ surface (global) | ρ = 0.43 | r = 0.43 |

Les valeurs sont quasi identiques : le nettoyage n'a pas déformé les distributions. Les {x['n_ventes_retirees']} ventes retirées (quarantaine) ont toutes un prix valide : elles sont rejetées pour surface ou date inexploitable, ou comme doublons, pas pour des valeurs extrêmes.

### Récapitulatif {figure, question, décision comp 3 justifiée}

| Figure | Question | Décision comp 3 justifiée |
|---|---|---|
| V1 | La cible est-elle modélisable telle quelle ? | 1.8 + 3.9 : modéliser log(prix) ; outliers plausibles conservés en avertissement |
| V2 | La catégorie structure-t-elle le prix ? | 3.3 : synonymes et casse harmonisés (7 catégories) ; 3.9 : fourchettes par catégorie |
| V3 | La relation prix ~ surface tient-elle par catégorie ? | 3.4 + 3.5 : surfaces normalisées, surfaces <= 0 rejetées ; 2.7 : Simpson actif |
| V4 | Quelles numériques sont redondantes ? | 3.13 : chambres/sdb non imputées (vides structurels) ; VIF à vérifier en comp 5/6 |
| V5 | Le nettoyage a-t-il supprimé les anomalies ? | 3.1 à 3.6 : quarantaine, normalisation, mojibake, doublons exacts |
| V6 | Les 5 sources sont-elles comparables ? | 3.2 + 3.3 + 3.12 : mojibake, catégories et transaction alignés sur les 5 sources |

## Encodage et normalisation (compétence 5)

Segment `vente` (2534 lignes). Tout transformateur est ajusté sur le **train** seulement (split 70/15/15, graine 42, stratifié sur categorie + source).

### Tableau des variables

| variable | type | cardinalite | ordre | dispo_en_prod | encodage_ou_scaler | justification |
|---|---|---|---|---|---|---|
| prix (cible) | numérique | — | — | non | log(prix) ; pas de scaler (c'est la cible) | skew 1.86 → -0.22 ; prix minimum = 5156000 > 0, le log est défini |
| transaction | catégorielle binaire | 1 | non | oui | EXCLUE (constante sur le segment vente) | le modèle porte sur les ventes (comp 1, décision 1.6) : une seule valeur, variance nulle ; binaire 0/1 si un modèle commun était fait |
| categorie | catégorielle | 7 | non | oui | one-hot (7 colonnes), handle_unknown=ignore | pas d'ordre ; porte l'essentiel du signal (η² = 0,74, comp 2) ; label encoding interdit (faux ordre) |
| region | catégorielle | 14 | non | oui | one-hot (14 colonnes), handle_unknown=ignore | effectif minimum 161 ; explique ω² = 2.5 % du prix relatif (p = 5.7e-11) |
| ville (commune) | catégorielle | 46 | non | oui | EXCLUE du one-hot (frequency à tester en comp 6) | emboîtée dans région (exception : 1 ville à 2 régions, les lignes Dakar/Ziguinchor signalées en comp 3) ; gain ω² ville vs région = 0.6 point pour 46 colonnes |
| statut | catégorielle | 6 | non | NON (Vendu = information postérieure à la mise en vente) | EXCLUE (fuite type 2) | V(source, statut) = 0.58 : proxy de la source (fuite type 4) ; aucun lien avec le prix relatif (η² = 0.0011, p = 0.70) |
| source | catégorielle | 5 | non | NON (identifiant de flux) | EXCLUE (audit seulement) | η² sur le prix relatif = 0.0005 (aucun signal) ; V(source, catégorie) = 0.17 : proxy de composition |
| transaction_origine | catégorielle | 2 | non | NON (métadonnée de nettoyage) | EXCLUE (fuite type 4) | V(source, transaction_origine) = 1.00 : reconstitue la source |
| surface | numérique | — | — | oui | log1p puis RobustScaler | skew 2.49 → 0.04 ; outliers conservés (comp 3) → échelle robuste ; seule, non prédictive (Simpson, comp 2/4) |
| chambres | numérique entière | — | — | oui | imputation par catégorie (fit train) puis RobustScaler | 26.8 % vides, structurels (plateforme 100 %) ; aucun indicateur de manque (révélerait la source) |
| sdb | numérique entière | — | — | oui | imputation par catégorie (fit train) puis RobustScaler | 15.4 % vides, structurels (notaires 100 %) ; aucun indicateur de manque |
| date → annee, mois | temporelle | — | cyclique (mois) | oui | annee (StandardScaler) + mois en sin/cos ; candidats, élagage en comp 6 | aucun signal : η² annee = 0.0056, mois = 0.0045 ; cohérent avec l'absence de tendance (comp 2) |
| id, ligne_id | identifiant | — | — | non | EXCLUES | identifiants : aucune information sur le bien |

### Décisions sur les trois variables à risque

- **`statut` : exclu (fuite types 2 et 4).** `Vendu` (1249 lignes) n'est connu qu'après la mise en vente ; V(source, statut) = 0.58 fait de `statut` un proxy de la source ; aucun lien avec le prix relatif (η² = 0.0011, p = 0.70).
- **`source` : exclue.** η² sur le prix relatif = 0.0005 (aucun signal) ; V(source, catégorie) = 0.17. Utilisée pour l'audit et la stratification du split seulement.
- **`commune` : exclue du one-hot.** 46 modalités, aucune sous 10 occurrences (la fiche annonçait l'inverse) ; gain de variance expliquée par rapport à la région = 0.56 point ; frequency encoding à tester en comp 6.

### Preuve de non-fuite (fit sur train uniquement)

| ajustement | variable | moyenne_train | moyenne_val | mediane_train | mediane_val |
|---|---|---|---|---|---|
| fit sur train (correct) | annee | -0.0 | -0.00304 | 0.03638 | -0.37978 |
| fit sur train (correct) | surface_log | -0.03632 | -0.05478 | 0.0 | -0.06133 |
| fit sur validation (fuite simulée) | annee | 0.00309 | -0.0 | 0.03999 | -0.38213 |
| fit sur validation (fuite simulée) | surface_log | 0.02319 | 0.00607 | 0.05687 | 0.0 |
| fit sur train+val (fit global) | annee | 0.00054 | -0.00251 | 0.03701 | -0.38018 |
| fit sur train+val (fit global) | surface_log | -0.03019 | -0.0486 | 0.00602 | -0.05513 |

Ajusté sur le train : moyenne de `annee` = 0 sur le train et -0.0030 sur la validation (≠ 0 : pas de fuite). Ajusté sur la validation, sa moyenne tomberait à 0 exactement : c'est la signature d'une fuite. `chambres` et `sdb` (entiers discrets) ne sont pas probants : leur médiane vaut 0 partout par construction.

## Feature engineering (compétence 6)

CV à 5 plis sur le **train seul** (1773 lignes), baseline `categorie` : R² = 0.7458. Une candidate à la fois, seuil ±0.01, graine 42.
Les fuites sont créées volontairement pour constater le mirage : `prix_m2 + surface_log` atteint R² = 1.0000.

| variable | type | base | r2_seul | r2_avec | gain | gain_foret | decision |
|---|---|---|---|---|---|---|---|
| region | existante | categorie | -0.0008 | 0.7502 | +0.0044 | -0.0020 | GARDER (neutre, sens métier fort) |
| surface_log | existante | categorie | 0.1800 | 0.7448 | -0.0011 | -0.0428 | GARDER (neutre, sens métier fort) |
| annee | existante | categorie | -0.0021 | 0.7454 | -0.0004 | -0.0064 | EXCLURE (neutre, sens métier faible) |
| mois | existante | categorie | -0.0026 | 0.7450 | -0.0008 | -0.0144 | EXCLURE (neutre, sens métier faible) |
| chambres_sdb | existante | categorie | 0.1186 | 0.7455 | -0.0003 | -0.0156 | EXCLURE (neutre, sens métier faible) |
| distance_dakar_km | créée | categorie+region | -0.0040 | 0.7502 | -0.0000 | -0.0012 | EXCLUE (redondante) |
| ville_frequence | créée | categorie+region | -0.0029 | 0.7501 | -0.0002 | -0.0081 | EXCLURE (neutre, sens métier faible) |
| surface_x_categorie | créée | categorie | 0.6479 | 0.7431 | -0.0027 | -0.0432 | EXCLURE (neutre, sens métier faible) |
| surface_par_chambre | créée | categorie | 0.0579 | 0.7451 | -0.0007 | -0.0497 | EXCLURE (neutre, sens métier faible) |
| prix_m2 | fuite (test) | categorie | 0.2109 | 0.8810 | +0.1352 | +0.1275 | REJETÉE (fuite) |
| prix_m2 + surface_log | fuite (test) | categorie | 0.9999 | 1.0000 | +0.2541 | +0.2448 | REJETÉE (fuite) |
| ratio_prix_fourchette | fuite (test) | categorie | 0.2124 | 0.9750 | +0.2292 | +0.2532 | REJETÉE (fuite) |
| est_hors_fourchette | fuite (test) | categorie | 0.0274 | 0.7675 | +0.0217 | +0.0207 | REJETÉE (fuite) |
| source | audit | categorie | 0.0109 | 0.7444 | -0.0015 | -0.0024 | EXCLUE (principe) |
| statut | audit | categorie | 0.0080 | 0.7441 | -0.0018 | -0.0049 | EXCLUE (principe) |

**Features retenues : categorie, region, surface_log.** Dictionnaire complet : `reports/dictionnaire_features.csv`.

## Découpage train / validation / test (compétence 7)

Split **aléatoire** stratifié sur `categorie + source`, ratios 70/15/15, graine 42 (voir `src/kerdata/split.py`).

| ensemble | count | pourcentage | cible_ratio |
|---|---|---|---|
| train | 1773 | 69.97 | 70% |
| val | 380 | 15.0 | 15% |
| test | 381 | 15.04 | 15% |

**Preuve de la stratégie** (Mann-Kendall sur le prix relatif à la catégorie, ventes datées ≤ 2026-10-31) :

| echelle | n_points | tau | p_value | decision |
|---|---|---|---|---|
| annuelle | 8 | 0.0 | 1.0 | pas de tendance → split aléatoire |
| mensuelle | 96 | -0.0241 | 0.7277 | pas de tendance → split aléatoire |
| par vente | 2530 | -0.0034 | 0.8006 | pas de tendance → split aléatoire |

**Prérequis vérifiés par le code :**

| prerequis | verifie |
|---|---|
| corpus issu de la comp 3 (aucune ligne en quarantaine dans le corpus conservé) | True |
| doublons exacts supprimés (aucun couple source+id répété) | True |
| vocabulaire des catégories aligné sur le référentiel (7 modalités) | True |
| features sélectionnées en comp 6 disponibles | True |
| `source` absente des features retenues | True |
| aucune colonne de fuite (prix_m2, ratio, hors_fourchette) dans les features retenues | True |

**Absence de fuite entre ensembles :**

| controle | nombre | attendu |
|---|---|---|
| (source, id) présents dans plusieurs ensembles | 0 | 0 |
| ligne_id présents dans plusieurs ensembles | 0 | 0 |
| lignes sans ensemble (non affectées) | 0 | 0 |
| même bien (date, ville, catégorie, surface) à cheval sur plusieurs ensembles | 0 | 0 |

Effectifs par catégorie : train/val/test tous ≥ 22 lignes.

**Jeu de test scellé le 2026-11-13** (381 lignes ; SHA-256 de l'appartenance `92a1f45006f51316…`, du contenu `416abcd763c5978e…`).
Jeu de test scellé : interdit pour toute décision (features, seuils, hyperparamètres, modèle) avant la compétence 9. Intégrité vérifiée à chaque exécution : **intact**.
