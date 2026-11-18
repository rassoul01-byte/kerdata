"""Génère et exécute notebooks/02_preparation_analyse.ipynb (bout en bout, sorties incluses)."""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

M = nbf.v4.new_markdown_cell
C = nbf.v4.new_code_cell


def construire() -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    nb.cells = [
        M("""# KerData — Préparation et analyse des données immobilières (Module 2)

Ce notebook rejoue **tout le pipeline de bout en bout** : lecture des 5 sources, types et statistiques, EDA, nettoyage, visualisations,
encodage, features, split, audit anti-fuite, pipeline final et évaluation. Chaque décision est justifiée dans `docs/justifications.md`.

**Exécution :** `jupyter nbconvert --to notebook --execute notebooks/02_preparation_analyse.ipynb` (ou « Run All »).
La première cellule lance `run_pipeline` ; l'évaluation sur le test est verrouillée : elle est lue, jamais recalculée."""),
        C("""import sys, json
from pathlib import Path
import pandas as pd
from IPython.display import Image, Markdown, display

RACINE = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(RACINE / "src"))
pd.set_option("display.width", 200, "display.max_columns", 30, "display.max_colwidth", 90)

from kerdata.pipeline import executer
res = executer(RACINE)           # étape 0 à compétence 9 ; l'évaluation du test est relue si déjà faite
m = res["tabs"]["mesures"]
print(f"{m['n']} lignes lues -> {m['propres']} propres | {m['avertissements']} avertissements | {m['quarantaine']} en quarantaine")
def csv(nom, **kw): return pd.read_csv(RACINE / "reports" / nom, **kw)
def fig(nom): display(Image(filename=str(RACINE / "reports" / "figures" / nom), width=900))"""),
        M("## 0. Lecture et concaténation des 5 sources\n\nChaque source a son propre format (Excel, CSV `;` avec accents cassés, CSV `,`, JSON imbriqué, CSV sans en-tête). Les volumes lus sont comparés à la fiche de conception."),
        C("""display(csv("volumes_etape0.csv"))"""),
        M("## 1. Types et statistiques descriptives (compétence 1)\n\nLe prix des ventes est asymétrique (skew > 1) : on modélise `log(prix)`. Ventes et locations ne se mélangent pas (médianes ×230)."""),
        C("""display(csv("comp1_types_par_source.csv").query("champ in ['prix','surface','date']")[["source","champ","type_reel","ecart","action"]])
display(csv("comp1_prix_vs_log.csv")[["population","n","median","skew_brut","skew_log"]])"""),
        C("""fig("comp1_prix_vs_log_ventes.png")"""),
        M("## 2. Analyse exploratoire (compétence 2)\n\nManquants et leur mécanisme, doublons, paradoxe de Simpson, tendance temporelle."),
        C("""fig("comp2_manquants.png"); fig("comp2_simpson_prix_surface.png")
display(csv("comp2_d6_robustesse.csv"))"""),
        M("## 3. Nettoyage (compétence 3) — les 6 mesures obligatoires\n\nChaque ligne finit dans un seul fichier : propres, avertissements ou quarantaine."),
        C("""display(Markdown((RACINE / "sortie" / "rapport_qualite.md").read_text(encoding="utf-8").split("## Manquants")[0]))"""),
        C("""display(csv("comp3_manquants_mecanisme.csv")); display(csv("comp3_doublons.csv"))"""),
        M("## 4. Visualisations de restitution (compétence 4)"),
        C("""for f in ["v1_distribution_cible.png", "v2_prix_par_categorie.png", "v3_simpson_donnees_propres.png"]: fig(f)"""),
        C("""for f in ["v4_matrice_correlation.png", "v5_preuve_nettoyage.png", "v6_comparaison_sources.png"]: fig(f)"""),
        M("## 5. Encodage, features, split (compétences 5 à 7)\n\n`statut`, `source` et `commune` sont exclues ; le split est aléatoire stratifié (Mann-Kendall p > 0,05) ; le test est scellé."),
        C("""display(csv("comp5_tableau_variables.csv")[["variable","encodage_ou_scaler","justification"]])
display(csv("comp6_candidates.csv")[["variable","type","r2_seul","gain","gain_foret","decision"]].round(4))"""),
        C("""display(csv("comp7_split_ensembles.csv")); display(csv("comp7_preuve_strategie_mann_kendall.csv"))
print(json.dumps(json.loads((RACINE / "sortie" / "test_scelle.json").read_text(encoding="utf-8")), ensure_ascii=False, indent=1)[:600])"""),
        M("## 6. Audit anti-fuite (compétence 8)\n\nLes features finales ne permettent pas de deviner la source ; `annee+mois` et les indicateurs de manque la révèlent."),
        C("""display(csv("comp8_detectabilite_source.csv")); display(csv("comp8_plausibilite_score.csv"))"""),
        M("## 7. Pipeline final et évaluation (compétence 9)\n\nLe pipeline sérialisé est rechargé depuis le disque et appliqué à une ligne brute de chaque source."),
        C("""import joblib
from kerdata.modele import adapter_ligne, lignes_natives
modele = joblib.load(RACINE / "models" / "pipeline_preparation.joblib")
print(type(modele).__name__, "->", [n for n, _ in modele.regressor_.steps])
for source, ligne in lignes_natives(RACINE).items():
    X = adapter_ligne(source, ligne)
    print(f"{source:13} {X.iloc[0].to_dict()} -> {modele.predict(X)[0] / 1e6:8.1f} M FCFA")"""),
        C("""for k in ["v3", "v4"]: display(res["comp9"]["verifs"][k])
t = json.loads((RACINE / "reports" / "comp9_evaluation_finale.json").read_text(encoding="utf-8"))
print("Évaluation finale (réalisée une seule fois le", t["realisee_le"], ") :")
display(pd.DataFrame({"Ridge": t["global_"], "baseline médiane catégorie": t["baseline_mediane_categorie"]}).T.round(4))
display(pd.DataFrame(t["par_categorie"]).T.round(3)[["n", "r2_log", "mdape_pct"]])"""),
        M("""## 8. Conclusion et limites

- **Données :** 3184 lignes lues, 2872 propres, 111 avertissements, 201 en quarantaine ; 40 lignes d'agence manquent par rapport à la fiche (non comblées).
- **Résultat :** le prix se prédit surtout par la **catégorie** (η² = 0,74). À l'intérieur d'une catégorie, ni la surface ni la région n'expliquent le prix (paradoxe de Simpson) : le pipeline fait à peine mieux que la médiane de la catégorie (R² log 0,731 contre 0,713 sur le test).
- **Rigueur :** aucune fuite détectée (`statut`, `source`, `annee`, indicateurs de manque écartés), fit sur le train seul, test scellé et évalué une seule fois.
- **Limites :** l'historique ne couvre que 2018-2020 ; 4 ventes datées de 2028 restent en avertissement ; le seuil de 3 M FCFA ventes/locations a été observé avant le split ; la performance n'est pas extrapolable à un marché futur."""),
    ]
    return nb


def generer(racine: Path, executer: bool = True) -> Path:
    racine = Path(racine)
    nb = construire()
    chemin = racine / "notebooks" / "02_preparation_analyse.ipynb"
    chemin.parent.mkdir(exist_ok=True)
    if executer:
        NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(chemin.parent)}}).execute()
    nbf.write(nb, chemin)
    return chemin


if __name__ == "__main__":
    print(generer(Path(".")))
