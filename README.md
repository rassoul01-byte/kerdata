# KerData — préparation des données immobilières (Module 2)

Pipeline reproductible qui transforme **5 sources immobilières hétérogènes** du Sénégal (Excel, CSV `;` aux accents cassés, CSV `,`,
JSON imbriqué, CSV sans en-tête) en un jeu de données propre et documenté, puis en un **pipeline scikit-learn sérialisé** qui prédit
le prix de vente, sans fuite de données. Chaque décision est justifiée par un chiffre (`docs/justifications.md`).

## Démarrer

```bash
pip install -r requirements.txt
python run_pipeline.py          # lecture → nettoyage → figures → features → split → audit → pipeline final → rapports (~2 min)
pytest                          # 157 tests
```

`run_pipeline.py` est rejouable : sur un clone neuf, il ne modifie aucun fichier suivi par git.
Le notebook `notebooks/02_preparation_analyse.ipynb` rejoue le tout de bout en bout (sorties incluses).
Le jeu de test est **scellé** (`sortie/test_scelle.json`) et son évaluation est verrouillée : elle est relue, jamais recalculée.

## Résultat en trois chiffres

| | |
|---|---|
| Corpus | 3184 lignes lues → **2872 propres**, 111 avertissements, 201 en quarantaine |
| Cible | `log(prix)` des ventes : skew 1,86 → −0,22 ; la catégorie explique 74 % de la variance |
| Test (évalué une seule fois) | R² log **0,731** contre 0,713 pour la simple médiane de la catégorie : la catégorie porte presque tout le signal |

## Où trouver quoi

| Dossier / fichier | Contenu |
|---|---|
| `sources/`, `referentiels/` | données d'origine, **intouchées** (`docs/manifeste_sources_sha256.json`) |
| `sortie/` | `donnees_propres.csv`, `avertissements.csv`, `quarantine.csv`, `corpus_conserve.csv`, `journal_corrections.csv`, `split.csv`, `test_scelle.json`, **`rapport_qualite.md`** |
| `models/` | **`pipeline_preparation.joblib`** et `pipeline_meta.json` |
| `docs/` | **`justifications.md`** (registre des décisions), `rapport_final.md`, `pipeline.md`, `soutenance.md`, `auto_evaluation.md`, `insights_comp2.md`, `planning/` (fiches) |
| `reports/` | tableaux CSV de chaque compétence, `dictionnaire_features.csv`, `figures/` (V1 à V6 et diagnostics) |
| `notebooks/` | `02_preparation_analyse.ipynb` |
| `src/kerdata/` | le code : `readers`, `concat`, `typage`, `nettoyage`, `viz`, `features`, `split`, `modele`… |
| `tests/` | 157 tests (nettoyage, split, fuite, pipeline, notebook, documents générés) |

## Les 9 compétences dans le code

| # | Compétence | Module | Livrable principal |
|---|---|---|---|
| 0 | Lecture et concaténation des 5 sources | `readers.py`, `concat.py` | `reports/volumes_etape0.csv` |
| 1 | Types et statistiques | `typage.py`, `comp1.py` | `reports/comp1_*.csv` |
| 2 | Analyse exploratoire | `comp2.py` | `reports/comp2_*.csv`, `docs/insights_comp2.md` |
| 3 | Nettoyage | `nettoyage.py`, `qualite.py` | `sortie/*.csv`, `rapport_qualite.md` |
| 4 | Visualisations de restitution | `viz.py` | `reports/figures/v1…v6` |
| 5 | Encodage et normalisation | `comp5.py`, `preprocess.py` | `reports/comp5_tableau_variables.csv` |
| 6 | Feature engineering | `features.py`, `comp6.py` | `reports/dictionnaire_features.csv` |
| 7 | Split train / validation / test | `split.py`, `comp7.py` | `sortie/split.csv`, `test_scelle.json` |
| 8 | Anti-fuite | `comp8.py` | `reports/comp8_audit_features.csv` |
| 9 | Pipeline reproductible | `modele.py` | `models/pipeline_preparation.joblib` |

## Utiliser le pipeline sérialisé

```python
import joblib, pandas as pd        # PYTHONPATH=src nécessaire pour retrouver la classe NormaliserAnnonce
modele = joblib.load("models/pipeline_preparation.joblib")
print(modele.predict(pd.DataFrame([{"categorie": "Villa", "region": "Dakar", "surface": "275,8"}])))   # prix en FCFA
```

Pour une annonce au schéma natif d'une source : `kerdata.modele.adapter_ligne(source, ligne)`.

## Limites reconnues

40 lignes d'agence manquent par rapport à la fiche de conception (640 lues pour 680) ; l'historique ne couvre que 2018-2020 ; 4 ventes datées de 2028
restent en avertissement ; le seuil de 3 M FCFA ventes/locations a été observé avant le split ; les données sont synthétiques et la surface n'explique
rien à l'intérieur d'une catégorie. Détail : `docs/rapport_final.md`, section 7.
