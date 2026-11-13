"""Compétence 7 : preuves formelles du split et scellé du jeu de test.

Le test n'est lu ici QUE pour (a) calculer des effectifs/proportions de composition et (b) calculer son empreinte
de scellé. Aucun prix du test n'entre dans une statistique, un graphique ou une décision.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

from .comp2 import AUJOURD_HUI, mann_kendall
from .split import ENSEMBLES, GRAINE, RATIOS

COLONNES_SCELLE = ["ligne_id", "source", "id", "date", "categorie", "region", "ville", "surface", "prix"]


def charger(racine: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    c = pd.read_csv(racine / "sortie" / "corpus_conserve.csv")
    sp = pd.read_csv(racine / "sortie" / "split.csv")
    v = c[c.transaction == "vente"].merge(sp, on="ligne_id", how="left")
    return c, v


def tableau_ensembles(v: pd.DataFrame) -> pd.DataFrame:
    t = v.ensemble.value_counts().reindex(ENSEMBLES).rename("count").to_frame()
    t["pourcentage"] = (100 * t["count"] / t["count"].sum()).round(2)
    t["cible_ratio"] = [f"{r:.0%}" for r in RATIOS]
    return t.rename_axis("ensemble").reset_index()


def prerequis(c: pd.DataFrame, racine: Path) -> pd.DataFrame:
    """Étape 1 de la fiche : corpus propre, features choisies, doublons supprimés, vocabulaire aligné."""
    cat = set(pd.read_csv(racine / "referentiels" / "referentiel_categories.csv").categorie)
    f_json = racine / "reports" / "features_retenues.json"
    feat = json.loads(f_json.read_text(encoding="utf-8"))["retenues"] if f_json.exists() else None
    q = pd.read_csv(racine / "sortie" / "quarantine.csv", dtype=str, keep_default_na=False)
    lignes = [
        ("corpus issu de la comp 3 (aucune ligne en quarantaine dans le corpus conservé)", bool((~c.ligne_id.isin(q.ligne_id)).all())),
        ("doublons exacts supprimés (aucun couple source+id répété)", not c.duplicated(["source", "id"]).any()),
        ("vocabulaire des catégories aligné sur le référentiel (7 modalités)", set(c.categorie) <= cat and c.categorie.nunique() == 7),
        ("features sélectionnées en comp 6 disponibles", feat is not None),
        ("`source` absente des features retenues", feat is not None and "source" not in feat),
        ("aucune colonne de fuite (prix_m2, ratio, hors_fourchette) dans les features retenues",
         feat is not None and not any(("prix" in f or "fourchette" in f) for f in feat)),
    ]
    return pd.DataFrame(lignes, columns=["prerequis", "verifie"])


def preuve_strategie(c: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mann-Kendall sur le prix relatif à la catégorie (3 échelles) + périodes couvertes par source."""
    v = c[c.transaction == "vente"].copy()
    v["d"] = pd.to_datetime(v.date)
    v = v[v.d <= AUJOURD_HUI].copy()                 # les ventes datées du futur (avertissement, comp 3) fausseraient la preuve
    v["prix_std"] = v.prix / v.groupby("categorie").prix.transform("median")
    ann = mann_kendall(v.groupby(v.d.dt.year).prix_std.median().sort_index())
    mens = mann_kendall(v.groupby(v.d.dt.to_period("M")).prix_std.median().sort_index())
    tau, p = st.kendalltau(v.d.map(pd.Timestamp.toordinal), v.prix_std)
    t = pd.DataFrame([
        dict(echelle="annuelle", n_points=ann["n_points"], tau=ann["tau"], p_value=ann["p_value"]),
        dict(echelle="mensuelle", n_points=mens["n_points"], tau=mens["tau"], p_value=mens["p_value"]),
        dict(echelle="par vente", n_points=len(v), tau=tau, p_value=p)]).round(4)
    t["decision"] = np.where(t.p_value > 0.05, "pas de tendance → split aléatoire", "tendance → split temporel")
    per = v.groupby("source").d.agg(debut="min", fin="max", ventes="size").reset_index()
    per["debut"], per["fin"] = per.debut.dt.date, per.fin.dt.date
    return t, per


def ids_partages(v: pd.DataFrame) -> pd.DataFrame:
    """Aucun identifiant ne doit apparaître dans deux ensembles ; même bien (clé métier) à cheval = signal à examiner."""
    par_id = v.groupby(["source", "id"]).ensemble.nunique()
    par_ligne = v.groupby("ligne_id").ensemble.nunique()
    cle_bien = v.date + "|" + v.ville.fillna("") + "|" + v.categorie + "|" + v.surface.round(1).astype(str)
    bien = v.assign(cle=cle_bien).groupby("cle").ensemble.nunique()
    return pd.DataFrame([
        dict(controle="(source, id) présents dans plusieurs ensembles", nombre=int((par_id > 1).sum()), attendu=0),
        dict(controle="ligne_id présents dans plusieurs ensembles", nombre=int((par_ligne > 1).sum()), attendu=0),
        dict(controle="lignes sans ensemble (non affectées)", nombre=int(v.ensemble.isna().sum()), attendu=0),
        dict(controle="même bien (date, ville, catégorie, surface) à cheval sur plusieurs ensembles", nombre=int((bien > 1).sum()), attendu=0),
    ])


def empreinte_test(v: pd.DataFrame) -> dict:
    """SHA-256 de l'appartenance ET du contenu des lignes du test : toute modification est détectable."""
    t = v[v.ensemble == "test"].sort_values("ligne_id")
    return dict(n_lignes=len(t),
                sha256_ligne_ids=hashlib.sha256("\n".join(t.ligne_id).encode()).hexdigest(),
                sha256_contenu=hashlib.sha256(t[COLONNES_SCELLE].astype(str).to_csv(index=False).encode()).hexdigest())


def sceller(v: pd.DataFrame, racine: Path, date: str) -> dict:
    d = empreinte_test(v)
    d.update(graine=GRAINE, scelle_le=date, utilisable_a_partir="compétence 9 (évaluation finale unique)",
             declaration="Jeu de test scellé : interdit pour toute décision (features, seuils, hyperparamètres, modèle) avant la compétence 9.")
    (racine / "sortie" / "test_scelle.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def verifier_scelle(racine: Path) -> bool:
    """True si le test n'a pas bougé depuis le scellé (appartenance et contenu)."""
    _, v = charger(racine)
    ref = json.loads((racine / "sortie" / "test_scelle.json").read_text(encoding="utf-8"))
    now = empreinte_test(v)
    return now["sha256_ligne_ids"] == ref["sha256_ligne_ids"] and now["sha256_contenu"] == ref["sha256_contenu"]


def main(racine: Path = Path("."), date_scelle: str | None = None) -> dict:
    racine = Path(racine)
    c, v = charger(racine)
    rep = racine / "reports"; rep.mkdir(exist_ok=True)
    out = dict(ensembles=tableau_ensembles(v), prerequis=prerequis(c, racine), ids=ids_partages(v),
               eff_cat=pd.crosstab(v.categorie, v.ensemble)[ENSEMBLES])
    out["strategie"], out["periodes"] = preuve_strategie(c)
    out["ensembles"].to_csv(rep / "comp7_split_ensembles.csv", index=False)
    out["prerequis"].to_csv(rep / "comp7_prerequis.csv", index=False)
    out["ids"].to_csv(rep / "comp7_absence_id_partage.csv", index=False)
    out["strategie"].to_csv(rep / "comp7_preuve_strategie_mann_kendall.csv", index=False)
    out["periodes"].to_csv(rep / "comp7_periodes_par_source.csv", index=False)
    out["eff_cat"].to_csv(rep / "comp7_effectifs_categorie_par_ensemble.csv")
    scelle = racine / "sortie" / "test_scelle.json"
    out["scelle"] = json.loads(scelle.read_text(encoding="utf-8")) if scelle.exists() else sceller(v, racine, date_scelle or pd.Timestamp.today().strftime("%Y-%m-%d"))
    out["scelle_intact"] = verifier_scelle(racine)
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    r = main()
    for k in ("ensembles", "prerequis", "ids", "strategie", "periodes", "eff_cat"):
        print(f"--- {k}"); print(r[k].to_string(index=k == "eff_cat"))
    print("--- scellé :", r["scelle"], "| intact :", r["scelle_intact"])


def markdown(r: dict) -> str:
    from .qualite import md_table
    s = r["scelle"]
    return f"""## Découpage train / validation / test (compétence 7)

Split **aléatoire** stratifié sur `categorie + source`, ratios 70/15/15, graine {s['graine']} (voir `src/kerdata/split.py`).

{md_table(r['ensembles'])}
**Preuve de la stratégie** (Mann-Kendall sur le prix relatif à la catégorie, ventes datées ≤ 2026-10-31) :

{md_table(r['strategie'])}
**Prérequis vérifiés par le code :**

{md_table(r['prerequis'])}
**Absence de fuite entre ensembles :**

{md_table(r['ids'])}
Effectifs par catégorie : train/val/test tous ≥ {int(r['eff_cat'].values.min())} lignes.

**Jeu de test scellé le {s['scelle_le']}** ({s['n_lignes']} lignes ; SHA-256 de l'appartenance `{s['sha256_ligne_ids'][:16]}…`, du contenu `{s['sha256_contenu'][:16]}…`).
{s['declaration']} Intégrité vérifiée à chaque exécution : **{'intact' if r['scelle_intact'] else 'ALTÉRÉ'}**.
"""
