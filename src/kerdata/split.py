"""Découpage train / validation / test (règles de la comp 7, appliquées dès la comp 5 car le fit des
transformateurs en dépend).

- 70 / 15 / 15, aléatoire (aucune tendance temporelle : Mann-Kendall p > 0,05, comp 2),
- stratifié sur `categorie` ; si une proportion par `source` s'écarte de plus de 2 points, `source` est ajoutée,
- graine fixée : relancer le split redonne exactement les mêmes lignes,
- le test n'est JAMAIS utilisé pour décider : ici on ne calcule que des proportions de composition.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

GRAINE = 42
RATIOS = (0.70, 0.15, 0.15)
ENSEMBLES = ["train", "val", "test"]
TOLERANCE_POINTS = 2.0          # écart maximal toléré par source avant d'ajouter `source` à la stratification
TOLERANCE_CATEGORIE = 0.5       # proportions de catégorie identiques à 0,5 point près


def _decouper(df: pd.DataFrame, cle: pd.Series, graine: int) -> pd.Series:
    idx = df.index
    reste, test = train_test_split(idx, test_size=RATIOS[2], stratify=cle.loc[idx], random_state=graine)
    train, val = train_test_split(reste, test_size=RATIOS[1] / (RATIOS[0] + RATIOS[1]), stratify=cle.loc[reste], random_state=graine)
    out = pd.Series("", index=idx)
    out.loc[train], out.loc[val], out.loc[test] = "train", "val", "test"
    return out


def proportions(df: pd.DataFrame, ens: pd.Series, col: str) -> pd.DataFrame:
    """Pourcentage de chaque modalité de `col` dans train / val / test."""
    t = pd.crosstab(df[col], ens.rename("ensemble"), normalize="columns").mul(100).round(2)
    return t[ENSEMBLES]


def ecart_max(df: pd.DataFrame, ens: pd.Series, col: str) -> float:
    p = proportions(df, ens, col)
    return float((p.max(axis=1) - p.min(axis=1)).max())


def decouper(df: pd.DataFrame, graine: int = GRAINE) -> tuple[pd.Series, dict]:
    """-> (série 'train'/'val'/'test' indexée comme df, diagnostic de la stratégie retenue)."""
    cle_cat = df["categorie"].astype(str)
    ens = _decouper(df, cle_cat, graine)
    ecart_src = ecart_max(df, ens, "source")
    strategie = "categorie"
    if ecart_src > TOLERANCE_POINTS:
        ens = _decouper(df, cle_cat + "|" + df["source"].astype(str), graine)
        strategie = "categorie + source"
    diag = dict(strategie=strategie, graine=graine, ecart_source_premiere_passe=ecart_src,
                ecart_source_final=ecart_max(df, ens, "source"), ecart_categorie_final=ecart_max(df, ens, "categorie"),
                effectifs=ens.value_counts().reindex(ENSEMBLES).to_dict())
    return ens, diag


def produire_split(conserve: pd.DataFrame, racine: Path) -> dict:
    """Split du segment vente ; écrit sortie/split.csv et les 2 tableaux de preuve."""
    v = conserve[conserve.transaction == "vente"].reset_index(drop=True)
    ens, diag = decouper(v)
    rep = Path(racine) / "reports"; rep.mkdir(exist_ok=True)
    pd.DataFrame({"ligne_id": v.ligne_id, "ensemble": ens}).to_csv(Path(racine) / "sortie" / "split.csv", index=False)
    pc = proportions(v, ens, "categorie"); pc.to_csv(rep / "comp7_split_proportions_categorie.csv")
    eff = pd.crosstab(v.source, ens.rename("ensemble"))[ENSEMBLES]; eff["total"] = eff.sum(axis=1)
    for e in ENSEMBLES:
        eff[f"{e}_pct"] = (100 * eff[e] / eff[e].sum()).round(2)
    eff.to_csv(rep / "comp7_split_effectifs_source.csv")
    diag.update(prop_categorie=pc, effectifs_source=eff, v=v, ensemble=ens)
    return diag
