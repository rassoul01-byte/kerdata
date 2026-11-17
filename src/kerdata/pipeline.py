"""Pipeline de bout en bout : sources brutes -> nettoyage -> exports + rapport de qualité."""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from .concat import concatener, controle_volumes
from .nettoyage import COLONNES_FINALES, nettoyer
from .qualite import (md_table, mesures, rapport_md, table_doublons, table_manquants,
                      table_outliers, validation_transaction)


def _sortie(d: pd.DataFrame, colonnes: list[str]) -> pd.DataFrame:
    x = d[colonnes].copy()
    for c in ("chambres", "sdb"):
        x[c] = pd.to_numeric(x[c], errors="coerce").astype("Int64")
    if "prix" in x:
        x["prix"] = x["prix"].round(0).astype("Int64")
    return x


def _motifs(serie: pd.Series) -> pd.DataFrame:
    from collections import Counter
    c = Counter()
    for t in serie[serie != ""]:
        for m in t.split("; "):
            m = m.split(" de ")[0] if m.startswith("doublon exact") else (m.split(" (")[0] if "inter-sources" in m else m)
            c[m] += 1
    return pd.DataFrame(sorted(c.items(), key=lambda kv: -kv[1]), columns=["motif", "lignes"])


def executer(racine: Path = Path("."), etapes_longues: bool = True) -> dict:
    racine = Path(racine)
    sortie, rep = racine / "sortie", racine / "reports"
    sortie.mkdir(exist_ok=True); rep.mkdir(exist_ok=True)

    brut = concatener(racine / "sources")
    controle_volumes(brut).to_csv(rep / "volumes_etape0.csv", index=False)
    brut.to_csv(sortie / "corpus_brut_concatene.csv", index=False, encoding="utf-8")

    res = nettoyer(brut, racine / "referentiels")
    d = res["d"].copy()
    d["prix"], d["surface"] = d["prix_num"], d["surface_num"]
    d["date"] = d["date_ts"].dt.strftime("%Y-%m-%d")

    propres = d[d.classe == "propre"]
    avert = d[d.classe == "avertissement"]
    quar = d[d.classe == "quarantaine"]
    _sortie(propres, COLONNES_FINALES).to_csv(sortie / "donnees_propres.csv", index=False, encoding="utf-8")
    _sortie(avert, COLONNES_FINALES + ["corrections", "motifs_a"]).to_csv(sortie / "avertissements.csv", index=False, encoding="utf-8")
    cols_q = COLONNES_FINALES + ["prix_brut", "surface_brut", "date_brut", "statut_brut", "motifs_q", "motifs_a"]
    q = quar.copy(); q["date"] = q["date_brut"]
    _sortie(q, cols_q).to_csv(sortie / "quarantine.csv", index=False, encoding="utf-8")
    shutil.copyfile(sortie / "quarantine.csv", sortie / "quarantaine.csv")
    conserve = d[d.classe != "quarantaine"].rename(columns={"classe": "classe_qualite"})
    _sortie(conserve, COLONNES_FINALES + ["classe_qualite"]).to_csv(sortie / "corpus_conserve.csv", index=False, encoding="utf-8")
    res["journal"].to_csv(sortie / "journal_corrections.csv", index=False, encoding="utf-8")
    res["paires"].to_csv(rep / "comp3_doublons_probables_detail.csv", index=False)

    tabs = dict(
        manquants=table_manquants(brut), doublons=table_doublons(res), outliers=table_outliers(res),
        motifs_q=_motifs(d.motifs_q), motifs_a=_motifs(d.motifs_a), validation_transaction=validation_transaction(d),
    )
    tabs["outliers_resume"] = (tabs["outliers"].groupby(["champ", "methode", "decision"], sort=False).nombre.sum().reset_index())
    tabs["mesures"] = mesures(brut, res)
    tabs["manquants"].to_csv(rep / "comp3_manquants_mecanisme.csv", index=False)
    tabs["doublons"].to_csv(rep / "comp3_doublons.csv", index=False)
    tabs["outliers"].to_csv(rep / "comp3_outliers.csv", index=False)
    pd.Series(tabs["mesures"]).to_csv(rep / "comp3_mesures.csv", header=["valeur"])
    (sortie / "rapport_qualite.md").write_text(rapport_md(brut, res, tabs), encoding="utf-8")
    res.update(tabs=tabs, d_final=d)

    from .viz import restitution  # restitution : relit les fichiers livrés, aucun retraitement
    c = restitution(res, racine)
    with open(sortie / "rapport_qualite.md", "a", encoding="utf-8") as fh:
        fh.write("\n" + c["markdown"])
    res["restitution"] = c

    # Compétence 5 : split (prérequis du fit), audits des variables, preuve de non-fuite
    from . import comp5
    from .split import produire_split
    cons = pd.read_csv(sortie / "corpus_conserve.csv")
    res["split"] = produire_split(cons, racine)
    res["comp5"] = comp5.main(racine)
    res["preuve"] = comp5.main_preuve(racine)
    with open(sortie / "rapport_qualite.md", "a", encoding="utf-8") as fh:
        fh.write("\n" + comp5.markdown(res["comp5"], res["preuve"], res["split"]))

    if etapes_longues:                       # compétence 6 : CV sur le train (quelques dizaines de secondes)
        from . import comp6
        res["comp6"] = comp6.main(racine)
        with open(sortie / "rapport_qualite.md", "a", encoding="utf-8") as fh:
            fh.write("\n" + comp6.markdown(res["comp6"]["tab"], res["comp6"]["retenues"], res["comp6"]["n_train"]))
        from . import comp7                  # compétence 7 : preuves du split et scellé du test (après les features de comp 6)
        res["comp7"] = comp7.main(racine)
        with open(sortie / "rapport_qualite.md", "a", encoding="utf-8") as fh:
            fh.write("\n" + comp7.markdown(res["comp7"]))
        from . import comp8                  # compétence 8 : audit anti-fuite (après le split et les features)
        res["comp8"] = comp8.main(racine)
        with open(sortie / "rapport_qualite.md", "a", encoding="utf-8") as fh:
            fh.write("\n" + comp8.markdown(res["comp8"], racine))
        from . import modele                 # compétence 9 : pipeline final, 6 vérifications, évaluation unique sur le test
        res["comp9"] = modele.main(racine, evaluer_test=True)
        with open(sortie / "rapport_qualite.md", "a", encoding="utf-8") as fh:
            fh.write("\n" + modele.markdown(res["comp9"]))
    return res
