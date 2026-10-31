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


# ---------------------------------------------------------------------------
# D3 : prix par catégorie ; D4 : relations numériques ; D5 : paradoxe de Simpson
# (segment `vente`, valeurs > 0, sans nettoyage supplémentaire)
# ---------------------------------------------------------------------------
from .typage import parse_entier  # noqa: E402


def base_ventes(d: pd.DataFrame) -> pd.DataFrame:
    v = d[(d.segment == "vente") & (d.prix_num > 0)].copy()
    v["chambres_num"] = v["chambres"].map(parse_entier)
    v["sdb_num"] = v["sdb"].map(parse_entier)
    return v


def prix_par_categorie(v: pd.DataFrame) -> pd.DataFrame:
    """D3 : dispersion de prix par catégorie (brut, ventes)."""
    ref = pd.read_csv(Path(__file__).resolve().parents[2] / "referentiels" / "referentiel_categories.csv")
    ref["cle"] = ref.categorie.str.lower()
    lignes = []
    for c, g in v.groupby("categorie_cle"):
        p = g.prix_num
        q1, q3 = p.quantile(.25), p.quantile(.75)
        r = ref[ref.cle == c]
        lignes.append(dict(
            categorie=c, n=len(p), mediane=p.median(), q1=q1, q3=q3, iqr_sur_mediane=(q3 - q1) / p.median(),
            cv=p.std() / p.mean(), min=p.min(), max=p.max(),
            hors_fourchette_ref=int(((p < r.prix_min_indicatif.iloc[0]) | (p > r.prix_max_indicatif.iloc[0])).sum()) if len(r) else np.nan))
    return pd.DataFrame(lignes).sort_values("cv", ascending=False).round(3)


def _corr(x: pd.Series, y: pd.Series) -> dict:
    ok = x.notna() & y.notna() & (x > 0) & (y > 0)
    x, y = x[ok], y[ok]
    if len(x) < 8:
        return dict(n=len(x), pearson=np.nan, p_pearson=np.nan, spearman=np.nan, p_spearman=np.nan,
                    pearson_log=np.nan, p_pearson_log=np.nan)
    rp, pp = st.pearsonr(x, y); rs, ps = st.spearmanr(x, y)
    rl, pl = st.pearsonr(np.log(x), np.log(y))
    return dict(n=len(x), pearson=rp, p_pearson=pp, spearman=rs, p_spearman=ps,
                pearson_log=rl, p_pearson_log=pl)


def correlations_prix_surface(v: pd.DataFrame) -> pd.DataFrame:
    """D4 + D5 : corrélations prix~surface, global puis par catégorie et par source."""
    lignes = [dict(niveau="global", groupe="toutes catégories", **_corr(v.surface_num, v.prix_num))]
    for c, g in v.groupby("categorie_cle"):
        lignes.append(dict(niveau="catégorie", groupe=c, **_corr(g.surface_num, g.prix_num)))
    for s, g in v.groupby("source"):
        lignes.append(dict(niveau="source", groupe=s, **_corr(g.surface_num, g.prix_num)))
    return pd.DataFrame(lignes).round(4)


def vif(v: pd.DataFrame, colonnes=("surface_num", "chambres_num", "sdb_num")) -> pd.DataFrame:
    """D4 : VIF sur les numériques disponibles (lignes complètes)."""
    x = v[list(colonnes)].dropna()
    x = x[(x > 0).all(axis=1)]
    out = []
    for c in colonnes:
        autres = [k for k in colonnes if k != c]
        A = np.column_stack([np.ones(len(x))] + [x[k] for k in autres])
        beta, *_ = np.linalg.lstsq(A, x[c], rcond=None)
        r2 = 1 - ((x[c] - A @ beta) ** 2).sum() / ((x[c] - x[c].mean()) ** 2).sum()
        out.append(dict(variable=c, n=len(x), r2_vs_autres=round(r2, 4), vif=round(1 / (1 - r2), 3)))
    return pd.DataFrame(out)


def correlations_autres(v: pd.DataFrame) -> pd.DataFrame:
    """D4 : Spearman prix~chambres et prix~sdb, global puis par catégorie (même test que Simpson)."""
    lignes = []
    for var in ("chambres_num", "sdb_num"):
        groupes = [("global", "toutes catégories", v)] + [("catégorie", c, g) for c, g in v.groupby("categorie_cle")]
        for niveau, cle, g in groupes:
            x = g[[var, "prix_num"]].dropna()
            x = x[x[var] > 0]
            if len(x) >= 8 and x[var].nunique() > 1:
                rs, ps = st.spearmanr(x[var], x.prix_num)
                lignes.append(dict(variable=var.replace("_num", ""), niveau=niveau, groupe=cle, n=len(x),
                                   spearman=round(rs, 4), p_value=round(ps, 4)))
    return pd.DataFrame(lignes)


def figures_d2(d: pd.DataFrame, v: pd.DataFrame, dossier: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dossier.mkdir(parents=True, exist_ok=True)
    # Fig 1 : manquants (structurels vs aléatoires), source × champ
    m = manquants(d)
    m["pct"] = m.pct_total_inutilisable
    mat = m.pivot(index="champ", columns="source", values="pct").reindex(CHAMPS_UTILES)
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(mat.values, cmap="Reds", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(mat.shape[1]), mat.columns, rotation=30); ax.set_yticks(range(mat.shape[0]), mat.index)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            ax.text(j, i, f"{mat.values[i, j]:.0f}" if mat.values[i, j] >= 1 else ("<1" if mat.values[i, j] > 0 else ""),
                    ha="center", va="center", fontsize=8, color="black" if mat.values[i, j] < 60 else "white")
    ax.set_title("Valeurs inutilisables (%) par source et champ\n100 % = structurel (source qui ne fournit pas le champ)")
    fig.colorbar(im, label="%"); fig.tight_layout(); fig.savefig(dossier / "comp2_manquants.png", dpi=110); plt.close(fig)
    # Fig 2 : prix par catégorie (ventes, échelle log)
    ordre = v.groupby("categorie_cle").prix_num.median().sort_values().index
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.boxplot([v[v.categorie_cle == c].prix_num / 1e6 for c in ordre], tick_labels=ordre, vert=True, showfliers=True)
    ax.set_yscale("log"); ax.set_ylabel("prix de vente (M FCFA, échelle log)"); ax.tick_params(axis="x", rotation=30)
    ax.set_title("Prix de vente par catégorie (brut, sans nettoyage)"); fig.tight_layout()
    fig.savefig(dossier / "comp2_prix_par_categorie.png", dpi=110); plt.close(fig)
    # Fig 3 : Simpson
    x = v[v.surface_num > 0]
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    couleurs = dict(zip(sorted(x.categorie_cle.unique()), plt.cm.tab10.colors))
    for c, g in x.groupby("categorie_cle"):
        ax[0].scatter(np.log(g.surface_num), np.log(g.prix_num), s=6, alpha=.4, color=couleurs[c], label=c)
        if len(g) > 8:
            b = np.polyfit(np.log(g.surface_num), np.log(g.prix_num), 1); xs = np.linspace(np.log(g.surface_num).min(), np.log(g.surface_num).max(), 20)
            ax[0].plot(xs, np.polyval(b, xs), color=couleurs[c], lw=2)
    ax[0].set(xlabel="log(surface)", ylabel="log(prix)", title="Par catégorie : droites quasi plates")
    ax[0].legend(fontsize=7, markerscale=2)
    ax[1].scatter(np.log(x.surface_num), np.log(x.prix_num), s=6, alpha=.3, color="grey")
    b = np.polyfit(np.log(x.surface_num), np.log(x.prix_num), 1); xs = np.linspace(np.log(x.surface_num).min(), np.log(x.surface_num).max(), 20)
    ax[1].plot(xs, np.polyval(b, xs), color="red", lw=2)
    r = np.corrcoef(np.log(x.surface_num), np.log(x.prix_num))[0, 1]
    ax[1].set(xlabel="log(surface)", title=f"Global : r = {r:.2f} (effet de composition)")
    fig.suptitle("Paradoxe de Simpson : prix ~ surface (ventes)"); fig.tight_layout()
    fig.savefig(dossier / "comp2_simpson_prix_surface.png", dpi=110); plt.close(fig)


def main_d3_d5(racine: Path = Path(".")) -> dict:
    d = preparer(charger_corpus(racine)); v = base_ventes(d)
    rep = racine / "reports"; rep.mkdir(exist_ok=True)
    out = dict(prix_cat=prix_par_categorie(v), corr=correlations_prix_surface(v), vif=vif(v), autres=correlations_autres(v))
    out["prix_cat"].to_csv(rep / "comp2_d3_prix_par_categorie.csv", index=False)
    out["corr"].to_csv(rep / "comp2_d4_d5_correlations_prix_surface.csv", index=False)
    out["vif"].to_csv(rep / "comp2_d4_vif.csv", index=False)
    out["autres"].to_csv(rep / "comp2_d4_correlations_chambres_sdb.csv", index=False)
    figures_d2(d, v, rep / "figures")
    return out
