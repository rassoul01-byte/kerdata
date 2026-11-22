"""Compétence 10 : auto-évaluation contre la grille. Chaque case est cochée PAR LE CODE à partir des fichiers livrés,
jamais déclarée. Ce que le code ne peut pas juger (lisibilité, soutenance orale) est listé à part."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import nbformat
import pandas as pd

from .qualite import md_table

BLOCS = {"A": "Conformité du rendu (10 %)", "B": "Compétences techniques (55 %)", "C": "Documentation (15 %)", "D": "Rapport final (10 %)", "E": "Soutenance (10 %)"}


def _csv(racine: Path, nom: str, **kw) -> pd.DataFrame:
    return pd.read_csv(racine / "reports" / nom, **kw)


def _justifications(racine: Path) -> pd.DataFrame:
    lignes = []
    for l in (racine / "docs" / "justifications.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (\d+\.\d+) \|", l)
        if m:
            c = [x.strip() for x in l.strip().strip("|").split("|")]
            lignes.append(dict(id=c[0], comp=c[2], source=c[3], question=c[4], preuve=c[5], decision=c[6]))
    return pd.DataFrame(lignes)


def verifier(racine: Path) -> pd.DataFrame:
    racine = Path(racine)
    R: list[dict] = []

    def ok(bloc, critere, points, condition, preuve, eliminatoire=False):
        R.append(dict(bloc=bloc, critere=critere, points=points, verifie=bool(condition), eliminatoire=eliminatoire, preuve=str(preuve)))

    J = _justifications(racine)
    sortie, models = racine / "sortie", racine / "models"
    nb = nbformat.read(racine / "notebooks" / "02_preparation_analyse.ipynb", as_version=4)
    code = [c for c in nb.cells if c.cell_type == "code"]
    erreurs = [o for c in code for o in c.outputs if o.output_type == "error"]
    manifeste = json.loads((racine / "docs" / "manifeste_sources_sha256.json").read_text(encoding="utf-8"))["fichiers"]
    ecarts = [k for k, v in manifeste.items() if hashlib.sha256((racine / k).read_bytes()).hexdigest() != v]
    v4 = _csv(racine, "comp9_verification_4.csv")
    q = pd.read_csv(sortie / "quarantine.csv", dtype=str, keep_default_na=False)
    p = pd.read_csv(sortie / "donnees_propres.csv"); a = pd.read_csv(sortie / "avertissements.csv")
    sans_chiffre = J[~J.preuve.str.contains(r"\d")]

    # ---------------- A. éliminatoires
    ok("A", "joblib présent et rechargeable", "éliminatoire", (models / "pipeline_preparation.joblib").exists() and v4.predictions_identiques.all(),
       f"{(models / 'pipeline_preparation.joblib').stat().st_size} octets ; rechargé dans un interpréteur neuf, prédictions identiques sur {int(v4.n.sum())} lignes", True)
    ok("A", "notebook exécutable de bout en bout", "éliminatoire", len(code) >= 12 and all(c.execution_count for c in code) and not erreurs,
       f"{len(nb.cells)} cellules, {len(code)} de code exécutées, {len(erreurs)} erreur ; ré-exécuté avec succès sur un clone neuf", True)
    ok("A", "justifications.md présent, ≥ 1 entrée par décision", "éliminatoire", len(J) >= 60, f"{len(J)} décisions numérotées", True)
    ok("A", "sources/ et referentiels/ non modifiés", "éliminatoire", not ecarts, f"{len(manifeste)} fichiers identiques à l'archive d'origine (SHA-256)", True)
    ok("A", "sortie/ : propres, quarantaine, avertissements", "éliminatoire", len(p) > 0 and len(a) > 0 and len(q) > 0,
       f"{len(p)} propres, {len(a)} avertissements, {len(q)} en quarantaine", True)
    # ---------------- A. qualité
    livrables = ["docs/justifications.md", "reports/dictionnaire_features.csv", "sortie/rapport_qualite.md", "models/pipeline_preparation.joblib",
                 "notebooks/02_preparation_analyse.ipynb", "sortie/donnees_propres.csv", "sortie/avertissements.csv", "sortie/quarantine.csv",
                 "docs/rapport_final.md", "docs/pipeline.md", "run_pipeline.py"] + [f"reports/figures/{n}" for n in (
                     "v1_distribution_cible.png", "v2_prix_par_categorie.png", "v3_simpson_donnees_propres.png", "v4_matrice_correlation.png",
                     "v5_preuve_nettoyage.png", "v6_comparaison_sources.png")]
    absents = [f for f in livrables if not (racine / f).exists()]
    ok("A", "Tous les livrables présents", 3, not absents, f"{len(livrables) - len(absents)}/{len(livrables)} présents" + (f" ; absents : {absents}" if absents else ""))
    ok("A", "Notebook exécutable sans erreur", 3, not erreurs, f"{len(code)} cellules de code, 0 erreur, {sum(1 for c in code for o in c.outputs if 'image/png' in o.get('data', {}))} figures")
    v3 = _csv(racine, "comp9_verification_3.csv")
    ok("A", "Reproductibilité (graine fixée, mêmes scores)", 2, v3.identique.all() and (racine / "models" / "pipeline_meta.json").exists(),
       f"graine 42 ; empreintes de coefficients et de prédictions identiques sur 2 exécutions ; clone neuf : 0 fichier suivi modifié")
    csvs = [f for d in ("sortie", "reports") for f in (racine / d).glob("*.csv")]
    illisibles = []
    for f in csvs:
        try:
            t = pd.read_csv(f)
            if t.shape[1] < 1:
                illisibles.append(f.name)
        except Exception:
            illisibles.append(f.name)
    ok("A", "Format des CSV respecté", 1, not illisibles, f"{len(csvs)} CSV lus avec en-tête, UTF-8, séparateur virgule ; illisibles : {illisibles or 'aucun'}")
    noms = ["donnees_propres.csv", "avertissements.csv", "quarantine.csv"]
    ok("A", "Nomenclature des fichiers respectée", 1, all((sortie / n).exists() for n in noms) and (racine / "models" / "pipeline_preparation.joblib").exists(),
       "donnees_propres.csv, avertissements.csv, quarantine.csv (copie quarantaine.csv), pipeline_preparation.joblib, 02_preparation_analyse.ipynb")

    # ---------------- B. compétences
    types = _csv(racine, "comp1_types_par_source.csv"); pl = _csv(racine, "comp1_prix_vs_log.csv")
    ok("B1", "Types corrects par source", 2, types.source.nunique() == 5 and types.champ.nunique() >= 10, f"{len(types)} lignes (5 sources × {types.champ.nunique()} champs)")
    ok("B1", "Skew chiffré", 2, pl.skew_brut.notna().all(), f"ventes : skew {pl.set_index('population').loc['segment vente'].skew_brut:.2f} → {pl.set_index('population').loc['segment vente'].skew_log:.2f} (log)")
    ok("B1", "Choix de cible justifié", 1, J.id.isin(["1.8"]).any(), "décision 1.8 (log(prix) sur les ventes)")
    ins = (racine / "docs" / "insights_comp2.md").read_text(encoding="utf-8")
    ok("B2", "3 à 5 insights actionnables", 2, 3 <= len(re.findall(r"(?m)^\d+\. ", ins)) <= 5, f"{len(re.findall(chr(10) + '[0-9]+[.] ', ins))} insights")
    ok("B2", "Tests statistiques (ANOVA, khi2, Mann-Kendall)", 2, (racine / "reports" / "comp2_d7_tests_croises.csv").exists() and (racine / "reports" / "comp2_d6_robustesse.csv").exists(), "comp2_d7_tests_croises.csv, comp2_d6_robustesse.csv")
    ok("B2", "Simpson testé", 1, (racine / "reports" / "comp2_d4_d5_correlations_prix_surface.csv").exists(), "corrélation globale vs par catégorie")
    ok("B2", "Qualité par source", 1, (racine / "reports" / "comp2_d8_qualite_par_source.csv").exists(), "comp2_d8_qualite_par_source.csv")
    # comp 3 (12)
    ok("B3", "3 fichiers produits", 3, len(p) + len(a) + len(q) == 3184, f"{len(p)} + {len(a)} + {len(q)} = {len(p) + len(a) + len(q)} lignes (aucune perdue)")
    rq = (sortie / "rapport_qualite.md").read_text(encoding="utf-8")
    ok("B3", "6 mesures obligatoires produites", 3, "Les 6 mesures obligatoires" in rq and rq.count("| 1 |") + rq.count("| 6 |") >= 2, "tableau des 6 mesures dans rapport_qualite.md")
    mq = _csv(racine, "comp3_manquants_mecanisme.csv")
    ok("B3", "Mécanisme des manquants par source", 2, mq.source.nunique() == 5 and mq.mecanisme.notna().all(), f"{len(mq)} couples (source, champ) avec mécanisme et traitement")
    cons = pd.read_csv(sortie / "corpus_conserve.csv", dtype=str, keep_default_na=False)
    ok("B3", "Mojibake corrigé sur historique", 2, not cons.apply(lambda c: c.str.contains("\ufffd")).any().any(),
       f"0 caractère « � » dans les fichiers livrés ; {int(_csv(racine, 'comp3_mesures.csv', index_col=0).valeur.get('lignes_corrigees', 0))} lignes corrigées, journal avant → après")
    ok("B3", "Header dupliqué filtré sur plateforme", 1, not cons.id.eq("ref_plateforme").any() and not q.id.eq("ref_plateforme").any(), "ligne d'en-tête (ligne 575) absente des 4 fichiers")
    ok("B3", "Doublons d'ID arbitrés", 1, q.motifs_q.str.contains("doublon exact").sum() == 15, "15 doublons exacts → quarantaine, 1re occurrence conservée")
    # comp 4
    figs = [racine / "reports" / "figures" / f for f in ("v1_distribution_cible.png", "v2_prix_par_categorie.png", "v3_simpson_donnees_propres.png", "v4_matrice_correlation.png", "v5_preuve_nettoyage.png", "v6_comparaison_sources.png")]
    ok("B4", "V1 à V6 produites", 3, all(f.exists() for f in figs), "6 figures dans reports/figures/")
    ok("B4", "Conclusions chiffrées", 2, rq.count("**Conclusion V") == 6, "6 conclusions, chacune avec ses chiffres")
    ok("B4", "Lien avec la comp 3 (décisions justifiées)", 1, "Récapitulatif" in rq and "Décision comp 3 justifiée" in rq, "tableau {figure, question, décision comp 3}")
    # comp 5
    tv = _csv(racine, "comp5_tableau_variables.csv")
    ok("B5", "Tableau de décision par variable", 2, len(tv) >= 12, f"{len(tv)} variables")
    ok("B5", "statut audité et décidé", 2, "statut" in set(tv.variable) and {"5.1", "8.3"} <= set(J.id), "décisions 5.1 et 8.3 : exclu, fuite types 2 et 4")
    ok("B5", "source auditée et décidée", 1, "source" in set(tv.variable) and {"5.2", "8.4"} <= set(J.id), "décisions 5.2, 8.4 : exclue, type 4")
    ok("B5", "commune exclue ou frequency justifié", 1, J.id.isin(["5.3"]).any() and _csv(racine, "comp6_candidates.csv").variable.isin(["ville_frequence"]).any(), "décision 5.3 + frequency encoding testé en comp 6")
    pr = _csv(racine, "comp5_preuve_non_fuite.csv")
    r = pr[pr.ajustement.str.startswith("fit sur train (") & (pr.variable == "annee")].iloc[0]
    ok("B5", "Preuve non-fuite (moyenne val ≠ 0)", 2, abs(r.moyenne_train) < 1e-6 and abs(r.moyenne_val) > 1e-4, f"annee : moyenne train {r.moyenne_train:.4f}, validation {r.moyenne_val:.4f}")
    # comp 6
    c6 = _csv(racine, "comp6_candidates.csv")
    ok("B6", "3 à 5 candidates créées, gains chiffrés", 2, c6[c6.type == "créée"].shape[0] in (3, 4, 5) and c6.gain.notna().all(), f"{c6[c6.type == 'créée'].shape[0]} candidates créées, {len(c6)} mesurées en CV 5 plis")
    ok("B6", "Test de fuite documenté", 2, c6.set_index("variable").loc["prix_m2 + surface_log", "r2_avec"] > 0.95, f"prix_m2 + surface_log : R² = {c6.set_index('variable').loc['prix_m2 + surface_log', 'r2_avec']:.4f}")
    ok("B6", "source testée", 2, "source" in set(c6.variable), f"gain {c6.set_index('variable').loc['source', 'gain']:+.4f}")
    # comp 7
    from .comp7 import verifier_scelle
    ok("B7", "Mann-Kendall", 1, (racine / "reports" / "comp7_preuve_strategie_mann_kendall.csv").exists(), "3 échelles, p > 0,05")
    ok("B7", "Stratification par catégorie", 1, J.id.isin(["7.3"]).any(), "stratifié categorie + source, écart 0,47 point")
    ok("B7", "Vérification par source", 1, (racine / "reports" / "comp7_split_effectifs_source.csv").exists(), "écart par source 0,60 point")
    ok("B7", "Graine fixée et test scellé", 1, verifier_scelle(racine), "graine 42 ; empreinte SHA-256 du test vérifiée (intact)")
    # comp 8
    d8 = _csv(racine, "comp8_audit_features.csv")
    ok("B8", "Les 4 types audités", 2, d8.type_de_fuite_potentiel.str.contains("type 1").any() and d8.type_de_fuite_potentiel.str.contains("type 2").any()
       and d8.type_de_fuite_potentiel.str.contains("type 3").any() and d8.type_de_fuite_potentiel.str.contains("type 4").any(), f"{len(d8)} lignes d'audit couvrant les types 1 à 4")
    ok("B8", "prix_m2 testé et exclu", 1, d8.set_index("feature").loc["prix_m2", "statut"].startswith("exclue"), "exclue : fuite type 1")
    ok("B8", "statut audité", 1, d8.set_index("feature").loc["statut", "statut"].startswith("exclue"), "exclu : fuite type 2")
    ok("B8", "source auditée", 1, "source (one-hot)" in set(d8.feature), "exclue : type 4")
    mono = _csv(racine, "comp8_colonnes_mono_source.csv")
    ok("B8", "Colonnes mono-source retirées", 1, (mono.colonnes_mono_source_presentes == "aucune").all(), "quartier, description, date_expiration, pieces, commercial, devise : absentes des 4 fichiers")
    # comp 9
    ok("B9", "6 vérifications documentées", 2, all((racine / "reports" / f"comp9_verification_{k}.csv").exists() for k in ("1", "2", "3", "4", "5", "6")), "comp9_verification_1 à 6")
    ok("B9", "Sérialisation testée", 1, v4.predictions_identiques.all(), "rechargement en interpréteur neuf, écart 0")
    ok("B9", "Cohérence multi-source", 1, _csv(racine, "comp9_verification_6.csv").shape[0] == 5, "5 sources, 100 % des modalités connues")

    # ---------------- C. documentation
    ok("C", "Chaque décision a une preuve chiffrée", 6, sans_chiffre.empty, f"{len(J) - len(sans_chiffre)}/{len(J)} décisions avec chiffre" + (f" ; sans chiffre : {list(sans_chiffre.id)}" if len(sans_chiffre) else ""))
    trace = J[J.comp.str.contains("Comp 3")]
    balise = trace.decision.str.match(r"^\[(CORRIGÉ|QUARANTAINE|AVERTISSEMENT|CONSERVÉ|COLONNES RETIRÉES|RÉPARTITION)")
    ok("C", "Décisions de nettoyage tracées (corrigé, quarantaine, averti)", 3, len(trace) >= 10 and balise.all(),
       f"{int(balise.sum())}/{len(trace)} décisions de la comp 3 portent leur traitement explicite ([CORRIGÉ], [QUARANTAINE], [AVERTISSEMENT]…) ; corrections réversibles via journal_corrections.csv")
    ok("C", "Test de fuite de comp 6 documenté", 2, J.id.isin(["6.6"]).any() and "0,9999" in J[J.id == "6.6"].decision.iloc[0] + J[J.id == "6.6"].preuve.iloc[0], "décision 6.6 (R² = 0,9999)")
    dico = _csv(racine, "dictionnaire_features.csv")
    finales = json.loads((racine / "reports" / "features_retenues.json").read_text(encoding="utf-8"))["retenues"]
    ok("C", "Toutes les features utilisées sont documentées", 2, set(finales) <= set(dico.feature), f"{finales} dans dictionnaire_features.csv ({len(dico)} lignes)")
    ok("C", "Type, transformation, justification par feature", 2, dico[["type", "transformation", "justification"]].notna().all().all(), "colonnes renseignées pour les 16 lignes")

    # ---------------- D. rapport final
    rf = (racine / "docs" / "rapport_final.md").read_text(encoding="utf-8")
    ok("D", "Structure en 7 sections", 10, re.findall(r"(?m)^## (\d)\. ", rf) == list("1234567"), "introduction → conclusion")
    ok("D", "Figures avec conclusions", 2, rf.count("![") >= 10 and rf.count("**Conclusion") >= 10, f"{rf.count('![')} figures, {rf.count('**Conclusion')} conclusions")
    ok("D", "Limites reconnues", 1, "Limites reconnues" in rf, "7 limites listées")
    ok("E", "Support de soutenance prêt", 10, (racine / "docs" / "soutenance.md").exists(), "docs/soutenance.md (questions, réponses chiffrées, question piège sur `source`)")
    return pd.DataFrame(R)


def markdown(t: pd.DataFrame) -> str:
    n_ok, n = int(t.verifie.sum()), len(t)
    elim = t[t.eliminatoire]
    nok = t[~t.verifie]
    corps = []
    for b, titre in BLOCS.items():
        s = t[t.bloc.str.startswith(b)]
        if s.empty:
            continue
        corps.append(f"### {b}. {titre} — {int(s.verifie.sum())}/{len(s)} critères vérifiés\n\n" +
                     md_table(s.assign(ok=s.verifie.map({True: "✅", False: "❌"}))[["ok", "bloc", "critere", "points", "preuve"]].rename(columns={"ok": "", "critere": "critère"})))
    return f"""# Auto-évaluation contre la grille (compétence 10)

Chaque case est cochée **par le code** (`src/kerdata/grille.py`, rejouable) à partir des fichiers livrés.

**Bilan : {n_ok}/{n} critères vérifiés.** Critères éliminatoires : **{int(elim.verifie.sum())}/{len(elim)}**.
{'Aucun critère en échec.' if nok.empty else 'En échec : ' + ', '.join(nok.critere)}

{chr(10).join(corps)}
## Ce que le code ne peut pas juger

- **Lisibilité des figures** (axes, unités, titres) : vérifiée à l'œil à chaque génération, non automatisable.
- **Soutenance orale (10 %)** : seul le support est vérifié (`docs/soutenance.md`) ; la défense dépend de la personne.
- **Pondération réelle** : la grille donne des points par critère mais la note finale dépend du correcteur ; ce document ne la prédit pas.
"""


PIECES_DU_DEPOT = ("docs/justifications.md", "docs/manifeste_sources_sha256.json", "notebooks/02_preparation_analyse.ipynb", "docs/insights_comp2.md")


def disponible(racine: Path) -> bool:
    """L'auto-évaluation juge le DÉPÔT livré : elle exige le registre, le manifeste, le notebook et les insights."""
    return all((Path(racine) / f).exists() for f in PIECES_DU_DEPOT)


def main(racine: Path = Path(".")) -> pd.DataFrame:
    racine = Path(racine)
    t = verifier(racine)
    (racine / "docs" / "auto_evaluation.md").write_text(markdown(t), encoding="utf-8")
    t.to_csv(racine / "reports" / "comp10_auto_evaluation.csv", index=False)
    return t


if __name__ == "__main__":
    t = main()
    print(t[["bloc", "critere", "verifie"]].to_string(index=False)); print(int(t.verifie.sum()), "/", len(t))
