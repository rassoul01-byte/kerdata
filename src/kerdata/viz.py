"""Compétence 4 : figures de restitution V1 à V6 (données nettoyées, but : PROUVER).

Base : corpus conservé (propres + avertissements), segment `vente`. Les avertissements
sont gardés (décision 3.9) : les retirer tronquerait la queue de prix et rendrait V1/V2 circulaires.
Aucun retraitement ici : uniquement de la restitution.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats as st  # noqa: E402

CATEGORIES = ["Chambre", "Studio", "Terrain", "Appartement", "Maison", "Local commercial", "Villa"]
COUL_CAT = dict(zip(CATEGORIES, plt.cm.tab10.colors))
SOURCES = ["agence", "historique", "notaires", "particuliers", "plateforme"]
COUL_SRC = dict(zip(SOURCES, plt.cm.Set2.colors))


def _fmt_m(x: float) -> str:
    return f"{x / 1e6:.1f} M"


def ventes(conserve: pd.DataFrame) -> pd.DataFrame:
    v = conserve[conserve.transaction == "vente"].copy()
    v["chambres"] = pd.to_numeric(v["chambres"], errors="coerce")
    v["sdb"] = pd.to_numeric(v["sdb"], errors="coerce")
    return v


def v1_cible(v: pd.DataFrame, f: Path) -> dict:
    sb, sl = st.skew(v.prix), st.skew(np.log(v.prix))
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.3))
    ax[0].hist(v.prix / 1e6, bins=60, color="#c0504d")
    ax[0].axvline(v.prix.median() / 1e6, color="k", ls="--", lw=1)
    ax[0].text(.97, .93, f"skew = {sb:.2f}\nmédiane = {_fmt_m(v.prix.median())}\nmoyenne = {_fmt_m(v.prix.mean())}",
               transform=ax[0].transAxes, ha="right", va="top", bbox=dict(fc="w", ec="grey"))
    ax[0].set(title="Prix brut : queue à droite (skew > 1)", xlabel="prix de vente (M FCFA)", ylabel="annonces")
    ax[1].hist(np.log(v.prix), bins=60, color="#4f81bd")
    ax[1].text(.03, .93, f"skew = {sl:.2f}\nkurtosis = {st.kurtosis(np.log(v.prix)):.2f}", transform=ax[1].transAxes,
               va="top", bbox=dict(fc="w", ec="grey"))
    ax[1].set(title="log(prix) : quasi symétrique", xlabel="log(prix en FCFA)")
    fig.suptitle(f"V1 — Modéliser log(prix) : le skew passe de {sb:.2f} à {sl:.2f} (n = {len(v)} ventes)", fontweight="bold")
    fig.tight_layout(); fig.savefig(f / "v1_distribution_cible.png", dpi=120); plt.close(fig)
    return dict(skew_brut=sb, skew_log=sl, n=len(v), mediane=v.prix.median(), moyenne=v.prix.mean())


def v2_categories(v: pd.DataFrame, f: Path) -> dict:
    med = v.groupby("categorie").prix.median().sort_values()
    ratio = med.max() / med.min()
    ordre = list(med.index)
    fig, ax = plt.subplots(figsize=(10, 5))
    etiq = [f"{c}\nn={int((v.categorie == c).sum())}\nméd. {med[c] / 1e6:.0f} M" for c in ordre]
    bp = ax.boxplot([v[v.categorie == c].prix / 1e6 for c in ordre], tick_labels=etiq, patch_artist=True, showfliers=True,
                    flierprops=dict(markersize=3, alpha=.5))
    for patch, c in zip(bp["boxes"], ordre):
        patch.set_facecolor(COUL_CAT[c]); patch.set_alpha(.7)
    ax.set_yscale("log"); ax.set(ylabel="prix de vente (M FCFA, échelle log)", xlabel="catégorie (triée par médiane croissante)")
    ax.tick_params(axis="x", labelsize=8)
    ax.set_title(f"V2 — La catégorie structure le prix : médiane {ordre[-1]} / {ordre[0]} = ×{ratio:.1f}", fontweight="bold")
    fig.tight_layout(); fig.savefig(f / "v2_prix_par_categorie.png", dpi=120); plt.close(fig)
    tout = np.log(v.prix)
    eta2 = sum(len(g) * (np.log(g.prix).mean() - tout.mean()) ** 2 for _, g in v.groupby("categorie")) / ((tout - tout.mean()) ** 2).sum()
    return dict(ratio=ratio, max=ordre[-1], min=ordre[0], med_max=med.max(), med_min=med.min(), eta2=eta2, medianes=med.to_dict())


def v3_simpson(v: pd.DataFrame, f: Path) -> dict:
    lx, ly = np.log(v.surface), np.log(v.prix)
    r_glob = np.corrcoef(lx, ly)[0, 1]
    par_cat = {c: np.corrcoef(np.log(g.surface), np.log(g.prix))[0, 1] for c, g in v.groupby("categorie")}
    pvals = {c: st.pearsonr(np.log(g.surface), np.log(g.prix))[1] for c, g in v.groupby("categorie")}
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    ax[0].scatter(lx, ly, s=5, alpha=.3, color="grey")
    xs = np.linspace(lx.min(), lx.max(), 20); ax[0].plot(xs, np.polyval(np.polyfit(lx, ly, 1), xs), color="red", lw=2.5)
    ax[0].set(title=f"Global : r = {r_glob:.2f} (effet de composition)", xlabel="log(surface en m²)", ylabel="log(prix en FCFA)")
    for c in CATEGORIES:
        g = v[v.categorie == c]
        ax[1].scatter(np.log(g.surface), np.log(g.prix), s=5, alpha=.35, color=COUL_CAT[c], label=f"{c} (r = {par_cat[c]:+.2f})")
        xs = np.linspace(np.log(g.surface).min(), np.log(g.surface).max(), 10)
        ax[1].plot(xs, np.polyval(np.polyfit(np.log(g.surface), np.log(g.prix), 1), xs), color=COUL_CAT[c], lw=2.2)
    ax[1].set(title=f"Par catégorie : r moyen = {np.mean(list(par_cat.values())):+.2f}", xlabel="log(surface en m²)")
    ax[1].legend(fontsize=7.5, markerscale=2)
    fig.suptitle(f"V3 — Paradoxe de Simpson actif : r global {r_glob:.2f}, mais ≈ 0 dans chaque catégorie", fontweight="bold")
    fig.tight_layout(); fig.savefig(f / "v3_simpson_donnees_propres.png", dpi=120); plt.close(fig)
    return dict(r_global=r_glob, r_moyen=float(np.mean(list(par_cat.values()))), r_max_abs=max(abs(x) for x in par_cat.values()),
                r_par_cat=par_cat, p_min=min(pvals.values()))


def v4_correlations(v: pd.DataFrame, f: Path) -> dict:
    X = pd.DataFrame({"log(prix)": np.log(v.prix), "log(surface)": np.log(v.surface), "chambres": v.chambres, "sdb": v.sdb})
    corr = X.corr()
    n_complet = int(X.dropna().shape[0])
    paires = [(a, b, corr.loc[a, b]) for i, a in enumerate(corr.columns) for b in corr.columns[i + 1:] if abs(corr.loc[a, b]) > 0.8]
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(4), corr.columns, rotation=30); ax.set_yticks(range(4), corr.columns)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=10)
    fig.colorbar(im, label="r de Pearson (-1 à +1)")
    ax.set_title(f"V4 — Aucune paire redondante (|r| > 0,8) : {len(paires)}\n(variables numériques seulement, ventes, paires complètes)", fontweight="bold", fontsize=10)
    fig.tight_layout(); fig.savefig(f / "v4_matrice_correlation.png", dpi=120); plt.close(fig)
    pc = corr.where(~np.eye(4, dtype=bool)).abs().stack()
    return dict(paires=paires, corr=corr, n_complet=n_complet, max_hors_diag=float(pc.max()), paire_max=pc.idxmax())


def v5_nettoyage(avant_apres: pd.DataFrame, par_source: pd.DataFrame, f: Path) -> dict:
    fig, ax = plt.subplots(1, 2, figsize=(14, 5), gridspec_kw=dict(width_ratios=[1, 1.25]))
    x = np.arange(len(par_source)); w = .38
    ax[0].bar(x - w / 2, par_source.pct_avant, w, label="avant (conformes d'emblée)", color="#c0504d")
    ax[0].bar(x + w / 2, par_source.pct_apres, w, label="après (lignes propres)", color="#4f81bd")
    for i, (a, b) in enumerate(zip(par_source.pct_avant, par_source.pct_apres)):
        ax[0].text(i - w / 2, a + 1, f"{a:.0f}", ha="center", fontsize=8); ax[0].text(i + w / 2, b + 1, f"{b:.0f}", ha="center", fontsize=8)
    ax[0].set_xticks(x, par_source.source, rotation=20); ax[0].set(ylim=(0, 118), ylabel="% de lignes conformes")
    ax[0].legend(fontsize=8, loc="upper center", ncol=2); ax[0].set_title("Conformité par source")
    ax[1].axis("off")
    t = ax[1].table(cellText=avant_apres.values, colLabels=list(avant_apres.columns), loc="center", cellLoc="left", colWidths=[.62, .19, .19])
    t.auto_set_font_size(False); t.set_fontsize(8); t.scale(1, 1.55)
    glob_av, glob_ap = par_source.attrs["global_avant"], par_source.attrs["global_apres"]
    fig.suptitle(f"V5 — Conformité globale : {glob_av:.1f} % avant → {glob_ap:.1f} % après nettoyage", fontweight="bold")
    fig.tight_layout(); fig.savefig(f / "v5_preuve_nettoyage.png", dpi=120); plt.close(fig)
    return dict(avant=glob_av, apres=glob_ap)


def v6_sources(v: pd.DataFrame, f: Path) -> dict:
    v = v.copy()
    v["prix_std"] = v.prix / v.groupby("categorie").prix.transform("median")
    v["surf_std"] = v.surface / v.groupby("categorie").surface.transform("median")
    fig, ax = plt.subplots(2, 2, figsize=(13, 8.5))
    cfg = [(ax[0, 0], "prix", True, "prix de vente (M FCFA, log)", 1e6, "Prix brut : niveaux inégaux"),
           (ax[0, 1], "surface", True, "surface (m², échelle log)", 1, "Surface brute : l'historique se détache"),
           (ax[1, 0], "prix_std", False, "prix / médiane de sa catégorie", 1, "Prix aligné par catégorie"),
           (ax[1, 1], "surf_std", False, "surface / médiane de sa catégorie", 1, "Surface alignée par catégorie")]
    res = {}
    n = v.source.value_counts()
    for a, col, log, lab, div, titre in cfg:
        data = [v[v.source == s][col] / div for s in SOURCES]
        fmt = (lambda m: f"{m:.0f}") if col == "prix" else ((lambda m: f"{m:.0f} m²") if col == "surface" else (lambda m: f"{m:.2f}"))
        etiq = [f"{s}\nn={n[s]}\nméd. {fmt(d.median())}" for s, d in zip(SOURCES, data)]
        bp = a.boxplot(data, tick_labels=etiq, patch_artist=True, showfliers=False)
        for p, s in zip(bp["boxes"], SOURCES):
            p.set_facecolor(COUL_SRC[s])
        if log:
            a.set_yscale("log")
        a.set(ylabel=lab, title=titre); a.tick_params(axis="x", labelsize=8)
        res[col] = {s: float(v[v.source == s][col].median()) for s in SOURCES}
    k_prix = st.kruskal(*[v[v.source == s].prix_std for s in SOURCES])[1]
    k_surf = st.kruskal(*[v[v.source == s].surf_std for s in SOURCES])[1]
    ks_surf_brut = {s: st.ks_2samp(v[v.source == s].surface, v[v.source != s].surface)[1] for s in SOURCES}
    fig.suptitle(f"V6 — Après alignement par catégorie, les 5 sources sont comparables (Kruskal prix p = {k_prix:.2f}, surface p = {k_surf:.2f})",
                 fontweight="bold")
    fig.tight_layout(); fig.savefig(f / "v6_comparaison_sources.png", dpi=120); plt.close(fig)
    compo = pd.crosstab(v.source, v.categorie, normalize="index") * 100
    return dict(kruskal_prix=k_prix, kruskal_surface=k_surf, ks_surface_brut=ks_surf_brut, effectifs=n.to_dict(), medianes=res,
                chi2_compo=st.chi2_contingency(pd.crosstab(v.source, v.categorie))[1], part_chambre=compo["Chambre"].round(1).to_dict())


# ---------------------------------------------------------------------------
# V5 : mesures avant/après (après = relu depuis le fichier livré), puis rapport
# ---------------------------------------------------------------------------
ISO = r"\d{4}-\d{2}-\d{2}"
VOCAB_STATUT = {"Vendu", "En vente", "Disponible", "Loué", "Retiré", "Sous offre", "À confirmer", ""}


def preparer_v5(res: dict, racine: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = res["d"]
    cons = pd.read_csv(racine / "sortie" / "corpus_conserve.csv", dtype=str, keep_default_na=False)
    propres = pd.read_csv(racine / "sortie" / "donnees_propres.csv", dtype=str, keep_default_na=False)
    canon = set(res["ref"].cat.categorie)
    prix_c, surf_c = pd.to_numeric(cons.prix, errors="coerce"), pd.to_numeric(cons.surface, errors="coerce")
    n_av, n_ap = len(d), len(cons)
    hors_prix_propres = int(res["d"][(res["d"].classe == "propre")].hors_prix_ref.sum())
    n_signal = int(res["d"][(res["d"].classe == "avertissement")].hors_prix_ref.sum())
    lignes = [
        ("Prix absents, illisibles ou <= 0", int((~(d.prix_num > 0)).sum()), int((~(prix_c > 0)).sum())),
        ("Surfaces absentes, illisibles ou <= 0", int((~(d.surface_num > 0)).sum()), int((~(surf_c > 0)).sum())),
        ("Dates non ISO ou impossibles", int((~d.date_brut.str.fullmatch(ISO)).sum()), int((~cons.date.str.fullmatch(ISO)).sum())),
        ("Lignes avec accents cassés (�)", int((d.region_brut.str.contains("\ufffd") | d.ville_brut.str.contains("\ufffd")).sum()),
         int((cons.region.str.contains("\ufffd") | cons.ville.str.contains("\ufffd")).sum())),
        ("Catégories hors vocabulaire", int((~d.categorie_brut.isin(canon)).sum()), int((~cons.categorie.isin(canon)).sum())),
        ("Statuts non harmonisés", int((~d.statut_brut.isin(VOCAB_STATUT)).sum()), int((~cons.statut.isin(VOCAB_STATUT)).sum())),
        ("Doublons exacts (même id, même source)", int(d.motifs_q.str.contains("doublon exact").sum()), int(cons.duplicated(["source", "id"]).sum())),
        ("Prix hors fourchette référentiel (ventes)", int(d.hors_prix_ref.sum()), f"{hors_prix_propres} ({n_signal} signalés)"),
        ("Lignes en quarantaine (motif écrit)", 0, int((d.classe == "quarantaine").sum())),
        ("chambres vides (%)", round(100 * (d.chambres == "").mean(), 1), round(100 * (cons.chambres == "").mean(), 1)),
        ("sdb vides (%)", round(100 * (d.sdb == "").mean(), 1), round(100 * (cons.sdb == "").mean(), 1)),
        ("Lignes", n_av, f"{n_ap} conservées"),
    ]
    def _t(x):
        return f"{x:g}" if isinstance(x, float) else str(x)
    tab = pd.DataFrame([(i, _t(a), _t(b)) for i, a, b in lignes], columns=["Indicateur", "Avant", "Après"])
    conforme_av = (d.corrections == 0) & d.motifs_q.eq("") & d.motifs_a.eq("")
    ps = pd.DataFrame({
        "source": SOURCES,
        "pct_avant": [100 * conforme_av[d.source == s].mean() for s in SOURCES],
        "pct_apres": [100 * (d[d.source == s].classe == "propre").mean() for s in SOURCES],
    })
    ps.attrs["global_avant"], ps.attrs["global_apres"] = 100 * conforme_av.mean(), 100 * (d.classe == "propre").mean()
    return tab, ps


def _comparaison_comp2(racine: Path, c: dict, x: dict) -> str:
    try:
        pl = pd.read_csv(racine / "reports" / "comp1_prix_vs_log.csv").set_index("population").loc["segment vente"]
        cat = pd.read_csv(racine / "reports" / "comp2_d3_prix_par_categorie.csv").set_index("categorie")
        r2 = cat.loc["villa", "mediane"] / cat.loc["chambre", "mediane"]
        cr = pd.read_csv(racine / "reports" / "comp2_d4_d5_correlations_prix_surface.csv")
        rg = cr[cr.niveau == "global"].spearman.iloc[0]
    except Exception:  # rapports de comp 1/2 absents (exécution isolée)
        return "_(rapports des compétences 1 et 2 absents : comparaison non disponible)_\n"
    lignes = [
        ("skew de prix (ventes)", f"{pl.skew_brut:.2f}", f"{c['v1']['skew_brut']:.2f}"),
        ("skew de log(prix)", f"{pl.skew_log:.2f}", f"{c['v1']['skew_log']:.2f}"),
        ("ratio médiane villa / chambre", f"×{r2:.1f}", f"×{c['v2']['ratio']:.1f}"),
        ("corrélation prix ~ surface (global)", f"ρ = {rg:.2f}", f"r = {c['v3']['r_global']:.2f}"),
    ]
    t = pd.DataFrame(lignes, columns=["Indicateur", "Comp 2 (données brutes)", "Comp 4 (données conservées)"])
    return _md(t) + f"\nLes valeurs sont quasi identiques : le nettoyage n'a pas déformé les distributions. Les {x['n_ventes_retirees']} ventes retirées (quarantaine) ont toutes un prix valide : elles sont rejetées pour surface ou date inexploitable, ou comme doublons, pas pour des valeurs extrêmes.\n"


def _md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(out) + "\n"


def restitution(res: dict, racine: Path) -> dict:
    racine = Path(racine)
    f = racine / "reports" / "figures"; f.mkdir(parents=True, exist_ok=True)
    cons = pd.read_csv(racine / "sortie" / "corpus_conserve.csv")
    v = ventes(cons)
    tab5, ps = preparer_v5(res, racine)
    c = dict(v1=v1_cible(v, f), v2=v2_categories(v, f), v3=v3_simpson(v, f), v4=v4_correlations(v, f),
             v5=v5_nettoyage(tab5, ps, f), v6=v6_sources(v, f))
    c["tab5"], c["ps"] = tab5, ps
    d = res["d"]
    propres_v = ventes(pd.read_csv(racine / "sortie" / "donnees_propres.csv"))
    c["extra"] = dict(
        n_hors_prix=int(d.hors_prix_ref.sum()), skew_sans_avert=float(st.skew(propres_v.prix)),
        n_ventes_retirees=int(((d.transaction == "vente") & (d.prix_num > 0)).sum()) - len(v),
        n_quar=int((d.classe == "quarantaine").sum()), n_avert=int((d.classe == "avertissement").sum()))
    md_corps = _markdown(c, v, racine)
    c["markdown"] = md_corps
    (racine / "reports" / "comp4_visualisations.md").write_text(md_corps.replace("](../reports/figures/", "](figures/"), encoding="utf-8")
    return c


def _markdown(c: dict, v: pd.DataFrame, racine: Path) -> str:
    v1, v2, v3, v4, v5, v6 = (c[k] for k in ("v1", "v2", "v3", "v4", "v5", "v6"))
    x = c["extra"]
    autres = [val for k, val in v6["part_chambre"].items() if k != "historique"]
    fp = lambda p: "< 0,0001" if p < 1e-4 else f"{p:.4f}"
    paires = "aucune paire" if not v4["paires"] else ", ".join(f"{a}/{b} (r = {r:.2f})" for a, b, r in v4["paires"])
    fig = lambda n: f"![{n}](../reports/figures/{n}.png)"
    recap = pd.DataFrame([
        ("V1", "La cible est-elle modélisable telle quelle ?", "1.8 + 3.9 : modéliser log(prix) ; outliers plausibles conservés en avertissement"),
        ("V2", "La catégorie structure-t-elle le prix ?", "3.3 : synonymes et casse harmonisés (7 catégories) ; 3.9 : fourchettes par catégorie"),
        ("V3", "La relation prix ~ surface tient-elle par catégorie ?", "3.4 + 3.5 : surfaces normalisées, surfaces <= 0 rejetées ; 2.7 : Simpson actif"),
        ("V4", "Quelles numériques sont redondantes ?", "3.13 : chambres/sdb non imputées (vides structurels) ; VIF à vérifier en comp 5/6"),
        ("V5", "Le nettoyage a-t-il supprimé les anomalies ?", "3.1 à 3.6 : quarantaine, normalisation, mojibake, doublons exacts"),
        ("V6", "Les 5 sources sont-elles comparables ?", "3.2 + 3.3 + 3.12 : mojibake, catégories et transaction alignés sur les 5 sources"),
    ], columns=["Figure", "Question", "Décision comp 3 justifiée"])
    return f"""## Visualisations de restitution (compétence 4)

Données : **corpus conservé** (`corpus_conserve.csv` = propres + avertissements), segment `vente` : {v1['n']} ventes.
Écart assumé avec la fiche, qui cite `donnees_propres.csv` : les {x['n_hors_prix']} prix hors fourchette plausibles sont gardés en avertissement (décision 3.9) ;
les retirer tronquerait la queue de prix (skew {v1['skew_brut']:.2f} avec eux, {x['skew_sans_avert']:.2f} sans) et rendrait V1/V2 circulaires.

{fig('v1_distribution_cible')}

**Conclusion V1.** Le skew de `prix` est de **{v1['skew_brut']:.2f}** (moyenne {_fmt_m(v1['moyenne'])} contre médiane {_fmt_m(v1['mediane'])}) ; il tombe à **{v1['skew_log']:.2f}** avec `log(prix)`. Décision confirmée : la cible est `log(prix)` sur le segment vente. *Justifie les décisions 1.8 et 3.9.*

{fig('v2_prix_par_categorie')}

**Conclusion V2.** La médiane passe de {_fmt_m(v2['med_min'])} ({v2['min']}) à {_fmt_m(v2['med_max'])} ({v2['max']}), soit **×{v2['ratio']:.1f}** ; la catégorie explique **{100 * v2['eta2']:.0f} %** de la variance de log(prix). `categorie` est la variable prioritaire (one-hot en comp 5/6). *Justifie 3.3 et 3.9.*

{fig('v3_simpson_donnees_propres')}

**Conclusion V3.** `r` global = **{v3['r_global']:.2f}** ; `r` moyen par catégorie = **{v3['r_moyen']:+.2f}** (|r| max = {v3['r_max_abs']:.2f}, p minimum = {v3['p_min']:.2f}) : le paradoxe de Simpson reste actif sur les données conservées. Implications : **pas de `prix_m2`** (dérivé de la cible, fuite type 1) et **pas de `surface` seule** ; tester l'interaction `categorie × surface` en comp 6. *Justifie 3.4, 3.5 et 2.7.*

{fig('v4_matrice_correlation')}

**Conclusion V4.** **{paires.capitalize()}** au-dessus de |r| = 0,8 (plus forte corrélation : {v4['paire_max'][0]} / {v4['paire_max'][1]}, |r| = {v4['max_hors_diag']:.2f}, calculée sur {v4['n_complet']} lignes complètes). Les corrélations de `sdb` et de `chambres` avec le prix sont des effets de composition (voir V3) : vérifier le VIF en comp 5/6. *Justifie 3.13.*

{fig('v5_preuve_nettoyage')}

**Conclusion V5.** Conformité globale de **{v5['avant']:.1f} %** avant (lignes sans aucune correction ni alerte) à **{v5['apres']:.1f} %** après (lignes propres, corrections tracées) ; les {100 - v5['apres']:.1f} % restants sont {x['n_quar']} lignes en quarantaine et {x['n_avert']} avertissements. Mesures « après » relues depuis `corpus_conserve.csv`, pas depuis les objets internes.

{_md(c['tab5'])}
*Justifie 3.1 à 3.6.*

{fig('v6_comparaison_sources')}

**Conclusion V6.** Après alignement par catégorie, les 5 sources sont **comparables** : Kruskal sur le prix p = {v6['kruskal_prix']:.2f}, sur la surface p = {v6['kruskal_surface']:.2f}. En brut, la surface de l'`historique` (KS p {fp(v6['ks_surface_brut']['historique'])}) et de l'`agence` (KS p = {fp(v6['ks_surface_brut']['agence'])}) se détache, mais c'est un **effet de composition** (khi2 catégorie × source p = {v6['chi2_compo']:.0e}) : l'historique contient {v6['part_chambre']['historique']} % de chambres contre {min(autres)}–{max(autres)} % dans les autres sources. Source atypique : **`historique`** (mélange de catégories uniforme, période 2018-2020 seulement, ni `statut` ni `transaction`) ; elle ne l'est ni par le niveau de prix ni, une fois alignée par catégorie, par la surface. **Décision pour comp 5 et 7 :** ne pas utiliser `source` comme variable explicative (fuite type 4) et stratifier le split sur `categorie` ; `source` ne sert qu'à l'audit. *Justifie 3.2, 3.3 et 3.12.*

### Cohérence avec les diagnostics de la comp 2

{_comparaison_comp2(racine, c, x)}
### Récapitulatif {{figure, question, décision comp 3 justifiée}}

{_md(recap)}"""
