# Pipeline final — `models/pipeline_preparation.joblib`

Généré par `run_pipeline.py` (module `src/kerdata/modele.py`). Les chiffres ci-dessous sont mesurés, pas déclarés.

## Rôle

Une annonce au schéma commun (`categorie`, `region`, `surface`) → prix de vente prédit en FCFA.
Les valeurs brutes des sources sont acceptées : la normalisation est **dans** le pipeline, donc rejouée à l'identique en production.

## Structure (ordre figé)

| # | Étape | Apprend des paramètres ? | Ce qu'elle fait |
|---|---|---|---|
| 1 | `normalisation` (`NormaliserAnnonce`) | non (règles des référentiels, embarquées dans l'objet) | synonymes de catégorie, casse/accents/mojibake des régions, surface → nombre ; surface absente, illisible ou ≤ 0 → refus explicite |
| 2 | `preparation` (`ColumnTransformer`) | oui, **sur le train seul** | one-hot `categorie` (7 colonnes) et `region` (14 colonnes) avec `handle_unknown="ignore"` ; `log1p` puis `RobustScaler` sur `surface` |
| 3 | `modele` (`Ridge`, α = 1) | oui, sur le train seul | régression linéaire régularisée sur 22 colonnes |
| — | `TransformedTargetRegressor` | non | cible `log(prix)` à l'entraînement, `exp` à la prédiction (prix en FCFA) |

**Pourquoi cet ordre.** On normalise avant d'encoder (sinon 15 modalités de catégorie au lieu de 7), on convertit la surface avant de la transformer (le texte avec virgule plante le scaler), on symétrise (log) avant de centrer-réduire.

## Ce qui est volontairement hors du pipeline

Le nettoyage de la comp 3 (quarantaine, doublons, dates), l'inférence de `transaction` et le split : ce sont des règles fixes ou des décisions sur le corpus, rejouées par `run_pipeline.py` (étape 0 incluse : concaténation des 5 sources par `kerdata.concat`). `statut`, `source`, `commune`, `quartier`, `description`, `date_expiration` et `annee/mois` n'entrent pas dans le pipeline (audits comp 5 et 8).

## Paramètres appris sur le train seul

| parametre | appris_par_le_pipeline | train_seul | train_plus_val | correspond_au_train |
|---|---|---|---|---|
| médiane de log1p(surface) (centre du RobustScaler) | 5.00193 | 5.00193 | 4.99451 | True |
| IQR de log1p(surface) (échelle du RobustScaler) | 1.2295 | 1.2295 | 1.23306 | True |
| modalités de catégorie apprises | 7 | 7 | 7 | True |
| modalités de région apprises | 14 | 14 | 14 | True |
| colonnes apprises par le Ridge (7 catégories + 14 régions + 1 surface) | 22 | 22 | 22 | True |

## Graine et reproductibilité

Graine **42** (split : `random_state`, vérification 3 : deux exécutions complètes donnent les mêmes coefficients et les mêmes prédictions, empreinte `1bc3b7192d92c61e`). Ridge est déterministe : aucune autre graine n'intervient.

Versions de l'entraînement : scikit-learn 1.9.1, Python 3.12.3.

## Procédure de rechargement

```python
import joblib, pandas as pd
modele = joblib.load("models/pipeline_preparation.joblib")      # nécessite `pip install pandas scikit-learn joblib` et PYTHONPATH=src
annonce = pd.DataFrame([{"categorie": "Villa", "region": "Dakar", "surface": "275,8"}])
print(modele.predict(annonce))                                    # prix en FCFA
```

Pour une annonce au schéma natif d'une source (Excel, CSV, JSON imbriqué), passer d'abord par `kerdata.modele.adapter_ligne(source, ligne)`.
Le rechargement a été testé dans un interpréteur neuf : prédictions identiques (écart maximal = 0).

## Limites

- Le pipeline ne prédit que des **ventes** (les locations suivent un autre régime de prix, comp 1).
- Les prédictions sont des **médianes conditionnelles** (`exp` de la moyenne du log) : elles sous-estiment la moyenne.
- Un rechargement exige la même version majeure de scikit-learn et le paquet `kerdata` importable (classe `NormaliserAnnonce`).
- La surface est refusée si absente : en production, l'annonce doit être complétée, comme à la quarantaine.

## Performance

**Validation (380 ventes)** : choix de l'hyperparamètre α = 1 (meilleur R² log sur la validation).

| modele | r2_log | rmse_log | mdape_pct | mae_fcfa |
|---|---|---|---|---|
| Ridge (pipeline final) | 0.738 | 0.474 | 34.1 | 38.4 M |
| baseline : médiane de la catégorie | 0.722 | 0.489 | 32.5 | 39.0 M |

Le pipeline gagne +0.016 de R² log sur la baseline, mais son erreur médiane relative (34.1 %) n'est pas meilleure que celle de la baseline (32.5 %) : la catégorie porte presque tout le signal (η² = 0,74), la région et la surface n'ajoutent presque rien (comp 2 et 6).

**Évaluation finale sur le test (381 ventes), réalisée une seule fois le 2026-11-17** (le test n'a servi à aucune décision) :

| modele | r2_log | rmse_log | mdape_pct | mae_fcfa |
|---|---|---|---|---|
| Ridge (pipeline final) | 0.731 | 0.484 | 35.9 | 38.5 M |
| baseline : médiane de la catégorie | 0.713 | 0.5 | 34.1 | 39.0 M |

Par source :

| source | n | r2_log | mdape_pct |
|---|---|---|---|
| agence | 79 | 0.685 | 33.5 |
| historique | 78 | 0.802 | 30.3 |
| notaires | 58 | 0.756 | 37.6 |
| particuliers | 65 | 0.663 | 40.0 |
| plateforme | 101 | 0.711 | 37.4 |

