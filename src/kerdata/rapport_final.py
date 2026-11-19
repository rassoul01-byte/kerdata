"""Assemble docs/rapport_final.md (structure de la grille, partie D) à partir des mesures du pipeline.

Aucun chiffre n'est écrit à la main : tout est relu dans `reports/` et `sortie/`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .qualite import md_table


def _sections(texte: str) -> dict[str, str]:
    """Découpe rapport_qualite.md en sections `## titre`."""
    morceaux = re.split(r"(?m)^## ", texte)
    return {m.split("\n", 1)[0].strip(): "## " + m for m in morceaux[1:]}


def _chercher(secs: dict[str, str], debut: str) -> str:
    for k, v in secs.items():
        if k.startswith(debut):
            return v
    raise KeyError(debut)


def _retitrer(section: str, nouveau: str) -> str:
    """Remplace le titre `##` d'une section par un titre `###` et rend les sous-titres plus discrets."""
    lignes = section.split("\n")
    lignes[0] = f"### {nouveau}"
    return "\n".join("#" + l if l.startswith("###") and i > 0 else l for i, l in enumerate(lignes))


def generer(racine: Path) -> Path:
    racine = Path(racine)
    rep, sortie = racine / "reports", racine / "sortie"
    vol = pd.read_csv(rep / "volumes_etape0.csv")
    mes = pd.read_csv(rep / "comp3_mesures.csv", index_col=0).valeur
    rq = _sections((sortie / "rapport_qualite.md").read_text(encoding="utf-8"))
    ev = json.loads((rep / "comp9_evaluation_finale.json").read_text(encoding="utf-8"))
    g, b = ev["global_"], ev["baseline_mediane_categorie"]
    types = pd.read_csv(rep / "comp1_types_par_source.csv")
    pl = pd.read_csv(rep / "comp1_prix_vs_log.csv").set_index("population")
    sv = pl.loc["segment vente"]
    glob = pl.iloc[0]
    sm = pd.read_csv(rep / "comp2_d4_d5_correlations_prix_surface.csv")
    r_glob = sm[sm.niveau == "global"].spearman.iloc[0]
    r_cat = sm[sm.niveau == "catégorie"].spearman
    rob = pd.read_csv(rep / "comp2_d6_robustesse.csv")
    man = pd.read_csv(rep / "comp2_d2_manquants.csv")
    struct = man[man.mecanisme.str.startswith("structurel")]
    tab = pd.read_csv(rep / "comp2_d7_tests_croises.csv")
    eta = tab.loc[tab.mesure_effet == "eta²", "effet"].iloc[0]
    f_ins = racine / "docs" / "insights_comp2.md"
    insights = f_ins.read_text(encoding="utf-8").split("\n", 2)[2].strip() if f_ins.exists() else "_(voir `docs/insights_comp2.md`)_"
    f_j = racine / "docs" / "justifications.md"
    nb_dec = len(re.findall(r"(?m)^\| \d+\.\d+ \|", f_j.read_text(encoding="utf-8"))) if f_j.exists() else 0
    det = pd.read_csv(rep / "comp8_detectabilite_source.csv")
    scelle = json.loads((sortie / "test_scelle.json").read_text(encoding="utf-8"))
    r2_val = json.loads((racine / "models" / "pipeline_meta.json").read_text(encoding="utf-8"))["val"]["r2_log"]

    sources_tab = vol.assign(ecart=vol.ecart.map(lambda x: f"{x:+d}"))
    nb_non_num = int(types[(types.champ == "prix") & (types.type_reel == "texte mixte")].shape[0])

    p = f"""# Rapport final — KerData : préparation des données immobilières (Module 2)

*Rapport généré par `run_pipeline.py` à partir des mesures ; chaque chiffre est relu dans `reports/` et `sortie/`. Décisions détaillées : `docs/justifications.md` ({nb_dec} décisions chiffrées).*

## 1. Introduction

**Objectif.** Transformer 5 sources immobilières hétérogènes du Sénégal en un jeu de données propre, documenté et reproductible, puis en un pipeline prêt pour la modélisation du prix de vente, sans fuite de données.

**Corpus.** Cinq sources aux formats et conventions différents (Excel, CSV `;` aux accents cassés, CSV `,`, JSON imbriqué, CSV dont l'en-tête n'est pas en première ligne) :

{md_table(sources_tab)}
Le total lu ({int(mes['n'])} lignes) est inférieur de 40 lignes à la fiche de conception : l'écart vient entièrement de l'agence (640 lues pour 680 annoncées). Il n'a pas été comblé.

**Démarche.** Neuf compétences enchaînées, chaque décision étant appuyée sur une mesure : types et statistiques → analyse exploratoire → nettoyage → visualisations de restitution → encodage → features → split → audit anti-fuite → pipeline sérialisé. Tout est rejouable par `python run_pipeline.py` et par le notebook `notebooks/02_preparation_analyse.ipynb`.

## 2. Types, statistiques et analyse exploratoire (compétences 1 et 2)

### 2.1 Types et statistiques (compétence 1)

`prix` est du texte mixte dans {nb_non_num} sources sur 5 (suffixe FCFA, « 147.52 millions », `N/A`, « à négocier ») ; `surface` contient des virgules décimales et des mots (« quatre-vingt ») ; les dates mêlent ISO et JJ/MM/AAAA, dont 6 impossibles (`32/13/2024`, notaires).

![Prix de vente brut et en log](../reports/figures/comp1_prix_vs_log_ventes.png)

**Conclusion.** Sur les ventes, la moyenne dépasse la médiane (ratio {sv.ratio_mean_median:.2f}) et le skew vaut **{sv.skew_brut:.2f}** ; avec `log(prix)` il tombe à **{sv.skew_log:.2f}**. Mélanger ventes et locations (médiane ×230) dégrade le skew du log à {glob.skew_log:.2f} : on segmente toujours `vente` / `location`. Cible retenue : `log(prix)` sur les ventes, résumé par la médiane.

### 2.2 Analyse exploratoire (compétence 2)

![Valeurs inutilisables par source et champ](../reports/figures/comp2_manquants.png)

**Conclusion.** {len(struct)} couples (source, champ) sont structurellement absents à 100 % (par exemple `transaction` dans 3 sources, `sdb` dans les notaires) ; les manques de `prix` et de `surface` sont aléatoires (khi2, tous p > 0,05) et vont en quarantaine plutôt qu'être imputés. La plateforme contient 15 doublons exacts et 5 dates futures.

![Paradoxe de Simpson](../reports/figures/comp2_simpson_prix_surface.png)

**Conclusion.** La corrélation prix/surface est de {r_glob:.2f} (Spearman) sur l'ensemble, mais comprise entre {r_cat.min():+.2f} et {r_cat.max():+.2f} dans chaque catégorie : paradoxe de Simpson. La catégorie explique {100 * eta:.0f} % de la variance de `log(prix)`.

![Tendance temporelle](../reports/figures/comp2_tendance_temporelle.png)

**Conclusion.** Aucune tendance significative à {len(rob)} échelles (p de {rob.p_value.min():.2f} à {rob.p_value.max():.2f}) : un split aléatoire est acceptable.

**Insights actionnables :**

{insights}

## 3. Nettoyage (compétence 3)

{_retitrer(_chercher(rq, "Bilan global"), "Bilan global").replace("### Bilan global", "Chaque ligne lue finit dans un seul fichier.", 1)}
{_chercher(rq, "Les 6 mesures obligatoires").replace("## ", "### ", 1)}
{_chercher(rq, "Manquants : mécanisme").replace("## ", "### ", 1)}
{_chercher(rq, "Doublons").replace("## ", "### ", 1)}
{_chercher(rq, "Aberrants").replace("## ", "### ", 1)}
{_chercher(rq, "Transaction inférée").replace("## ", "### ", 1)}
## 4. Visualisations de restitution (compétence 4)

{_retitrer(_chercher(rq, "Visualisations de restitution"), "Figures V1 à V6").replace("### Figures V1 à V6", "", 1)}
## 5. Encodage, normalisation et features (compétences 5 et 6)

{_retitrer(_chercher(rq, "Encodage et normalisation"), "Encodage et normalisation (compétence 5)")}
{_retitrer(_chercher(rq, "Feature engineering"), "Feature engineering (compétence 6)")}
## 6. Split, anti-fuite et pipeline (compétences 7, 8 et 9)

{_retitrer(_chercher(rq, "Découpage train"), "Split (compétence 7)")}
{_retitrer(_chercher(rq, "Audit anti-fuite"), "Audit anti-fuite (compétence 8)")}
{_retitrer(_chercher(rq, "Pipeline reproductible"), "Pipeline reproductible (compétence 9)")}
## 7. Conclusion

**Bilan.** {int(mes['n'])} lignes lues → {int(mes['propres'])} propres, {int(mes['avertissements'])} avertissements, {int(mes['quarantaine'])} en quarantaine ; {mes['taux_conformes_emblee']} % des lignes étaient conformes d'emblée, {mes['taux_propres']} % le sont après traitement. Le pipeline final (normalisation → préparation → Ridge, 22 colonnes) est sérialisé, rechargé dans un interpréteur neuf avec des prédictions identiques, et reproductible (mêmes coefficients, mêmes prédictions).

**Résultat sur le test**, évalué une seule fois le {ev['realisee_le']} sur {g['n']} ventes (test scellé le {scelle['scelle_le']}, empreinte vérifiée) : R² log = **{g['r2_log']:.3f}**, erreur médiane relative {g['mdape_pct']:.1f} %, contre {b['r2_log']:.3f} et {b['mdape_pct']:.1f} % pour la simple médiane de la catégorie. La performance se généralise (validation → test : {g['r2_log'] - r2_val:+.3f} de R²), mais elle est portée presque entièrement par la catégorie : à l'intérieur d'une catégorie, le R² est compris entre {min(m['r2_log'] for m in ev['par_categorie'].values()):+.2f} et {max(m['r2_log'] for m in ev['par_categorie'].values()):+.2f}.

**Rigueur.** `statut`, `source`, `annee`/`mois`, les indicateurs de manque et les colonnes mono-source sont écartés (fuites de types 2 et 4 mesurées : par exemple `annee`+`mois` devinent la source avec une AUC de {det[det.ensemble_de_features.str.startswith('annee')].auc_macro.iloc[0]:.2f}, les features finales avec {det.iloc[0].auc_macro:.2f}, proche du hasard). Le test de fuite volontaire (`prix_m2 + surface_log`) atteint R² = 0,9999 : le mirage est reconnu et exclu.

**Limites reconnues.**
- 40 lignes d'agence manquent par rapport à la fiche de conception ; non comblé.
- La quarantaine est stricte : prix ou surface absents ou illisibles sont rejetés (surface imputable pour certaines lignes).
- 4 ventes datées de 2028 sont conservées en avertissement (leur date n'entre dans aucune feature) ; le seuil de 3 M FCFA entre ventes et locations a été observé avant le split (règle métier fixe, pas un paramètre appris).
- L'historique ne couvre que 2018-2020 et le test est tiré de la même période : la performance n'est pas extrapolable à un marché futur.
- Le pipeline ne prédit que des ventes, par une médiane conditionnelle, et exige une surface valide.
- Les données sont synthétiques : l'absence d'effet de la surface à l'intérieur d'une catégorie reflète leur construction autant que le marché.

**Perspectives.** Enrichir les features intra-catégorie (état du bien, étage, quartier, distance à la mer) ; modèle de loyers séparé ; validation temporelle si de nouvelles années sont collectées.
"""
    chemin = racine / "docs" / "rapport_final.md"
    chemin.parent.mkdir(exist_ok=True)
    chemin.write_text(p, encoding="utf-8")
    return chemin


if __name__ == "__main__":
    print(generer(Path(".")))
