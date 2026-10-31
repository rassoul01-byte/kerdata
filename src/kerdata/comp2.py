"""Compétence 2 : EDA diagnostique par source (D1 effectifs/doublons, D2 manquants, D8 qualité)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

from .comp1 import ajouter_numeriques, charger_corpus
from .readers import COLONNES_COMMUNES, COLONNES_EXTRA
from .typage import parse_date

AUJOURD_HUI = pd.Timestamp("2026-10-31")
CHAMPS = [c for c in COLONNES_COMMUNES + COLONNES_EXTRA if c != "source"]
CHAMPS_UTILES = ["id", "date", "transaction", "categorie", "region", "ville", "prix",
                 "surface", "chambres", "sdb", "statut"]


def preparer(df: pd.DataFrame) -> pd.DataFrame:
    d = ajouter_numeriques(df)
    d["date_parsee"] = d["date"].map(parse_date)
    return d


def vue_ensemble(d: pd.DataFrame) -> pd.DataFrame:
    """D1 : lignes, colonnes fournies, période, doublons (exacts / d'ID / probables), dates futures."""
    lignes = []
    for s, g in d.groupby("source"):
        cols_fournies = [c for c in CHAMPS if (g[c] != "").any()]
        dates = g["date_parsee"].dropna()
        sans_id = [c for c in cols_fournies if c != "id"]
        lignes.append(dict(
            source=s, lignes=len(g), colonnes_fournies=len(cols_fournies),
            date_min=dates.min().date(), date_max=dates.max().date(),
            dates_futures=int((dates > AUJOURD_HUI).sum()),
            doublons_exacts=int(g.duplicated(subset=cols_fournies, keep="first").sum()),
            doublons_id=int(g.duplicated(subset="id", keep="first").sum()),
            doublons_probables_hors_id=int(g.duplicated(subset=sans_id, keep="first").sum()
                                           - g.duplicated(subset=cols_fournies, keep="first").sum()),
        ))
    return pd.DataFrame(lignes)


def effectifs(d: pd.DataFrame) -> pd.DataFrame:
    """D1 : effectifs par catégorielle, par source (valeurs brutes) + part dans la source."""
    morceaux = []
    for champ in ("categorie", "region", "statut", "transaction"):
        t = d.groupby(["source", champ]).size().rename("effectif").reset_index().rename(columns={champ: "modalite"})
        t["champ"] = champ
        t["part_source_pct"] = (100 * t.effectif / t.groupby("source").effectif.transform("sum")).round(1)
        morceaux.append(t)
    return pd.concat(morceaux)[["champ", "source", "modalite", "effectif", "part_source_pct"]]


def _manquant(d: pd.DataFrame, champ: str) -> pd.Series:
    """Manquant au sens large = vide OU non convertible (prix/surface/date) — compté séparément."""
    return d[champ] == ""


def manquants(d: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """D2 : manquants par source × champ, mécanisme (structurel / aléatoire / dépendant)."""
    conv = {"prix": d["prix_num"], "surface": d["surface_num"], "date": d["date_parsee"]}
    lignes = []
    for s, g in d.groupby("source"):
        for champ in CHAMPS_UTILES:
            vides = _manquant(g, champ)
            n, nv = len(g), int(vides.sum())
            non_conv = int((~vides & conv[champ].loc[g.index].isna()).sum()) if champ in conv else 0
            ligne = dict(source=s, champ=champ, n=n, vides=nv, pct_vides=round(100 * nv / n, 1),
                         non_convertibles=non_conv, pct_total_inutilisable=round(100 * (nv + non_conv) / n, 1))
            if nv == n:
                ligne.update(mecanisme="structurel (100 % absent dans la source)", variable_dependante="", p_value=np.nan)
            elif nv == 0 and non_conv == 0:
                ligne.update(mecanisme="complet", variable_dependante="", p_value=np.nan)
            else:
                manque = vides | (conv[champ].loc[g.index].isna() if champ in conv else False)
                best = (np.nan, "")
                for ref in ("categorie_cle", "statut", "transaction"):
                    if ref == champ or g.loc[g[ref] != "", ref].nunique() < 2:
                        continue
                    ct = pd.crosstab(manque[g[ref] != ""], g.loc[g[ref] != "", ref])
                    ct = ct.loc[:, ct.sum() >= 5]
                    if ct.shape[0] == 2 and ct.shape[1] >= 2:
                        p = st.chi2_contingency(ct)[1]
                        if np.isnan(best[0]) or p < best[0]:
                            best = (p, ref)
                if not np.isnan(best[0]) and best[0] < alpha:
                    ligne.update(mecanisme=f"dépendant de {best[1]} (MAR)", variable_dependante=best[1], p_value=round(best[0], 4))
                else:
                    ligne.update(mecanisme="aléatoire (MCAR plausible)", variable_dependante=best[1], p_value=round(best[0], 4) if not np.isnan(best[0]) else np.nan)
            lignes.append(ligne)
    return pd.DataFrame(lignes)


def qualite_par_source(d: pd.DataFrame) -> pd.DataFrame:
    """D8 : prix/surface/date inutilisables, non numériques, dates impossibles, doublons d'ID."""
    lignes = []
    for s, g in d.groupby("source"):
        plein_prix = g["prix"] != ""
        lignes.append(dict(
            source=s, n=len(g),
            pct_manquants_prix=round(100 * (g.prix == "").mean(), 1),
            pct_manquants_surface=round(100 * (g.surface == "").mean(), 1),
            pct_manquants_date=round(100 * (g.date == "").mean(), 1),
            prix_non_numeriques=int((plein_prix & ~g.prix.str.fullmatch(r"-?\d+(\.\d+)?")).sum()),
            prix_non_convertibles=int((plein_prix & g.prix_num.isna()).sum()),
            dates_non_interpretables=int(((g.date != "") & g.date_parsee.isna()).sum()),
            doublons_id=int(g.duplicated(subset="id", keep="first").sum()),
        ))
    return pd.DataFrame(lignes)


def doublons_inter_sources(d: pd.DataFrame) -> pd.DataFrame:
    """Doublons PROBABLES entre sources : même date, ville(casse), catégorie, prix et surface.

    Mesure seulement : aucune fusion sans preuve (règle métier). Les lignes d'une
    même source en doublon exact sont écartées avant (déjà comptées en D1).
    """
    v = d[(d.prix_num > 0) & (d.surface_num > 0) & d.date_parsee.notna()].drop_duplicates(
        subset=["source", "id"]).copy()
    v["cle"] = (v.date_parsee.dt.strftime("%Y-%m-%d") + "|" + v.ville.str.strip().str.lower()
                + "|" + v.categorie_cle + "|" + v.prix_num.round(0).astype(int).astype(str)
                + "|" + v.surface_num.round(1).astype(str))
    nb_src = v.groupby("cle").source.nunique()
    communs = nb_src[nb_src > 1].index
    return v[v.cle.isin(communs)].sort_values("cle")[["cle", "source", "id", "date", "ville", "categorie", "prix", "surface"]]


def main_d1_d2(racine: Path = Path(".")) -> dict:
    d = preparer(charger_corpus(racine))
    rep = racine / "reports"; rep.mkdir(exist_ok=True)
    out = dict(vue=vue_ensemble(d), effectifs=effectifs(d), manquants=manquants(d), qualite=qualite_par_source(d))
    out["vue"].to_csv(rep / "comp2_d1_vue_ensemble.csv", index=False)
    out["effectifs"].to_csv(rep / "comp2_d1_effectifs.csv", index=False)
    out["manquants"].to_csv(rep / "comp2_d2_manquants.csv", index=False)
    out["qualite"].to_csv(rep / "comp2_d8_qualite_par_source.csv", index=False)
    out["inter"] = doublons_inter_sources(d)
    out["inter"].to_csv(rep / "comp2_d1_doublons_probables_inter_sources.csv", index=False)
    out["d"] = d
    return out
