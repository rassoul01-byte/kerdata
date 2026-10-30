"""Compétence 1 : types réels, statistiques descriptives, distribution de prix/surface."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from .typage import CONVERTISSEURS

TYPE_ATTENDU = {
    "id": "text", "date": "date", "transaction": "catégorie",
    "categorie": "catégorie", "region": "catégorie", "ville": "catégorie",
    "prix": "numérique ou texte", "surface": "numérique ou texte",
    "chambres": "entier (hors dictionnaire)", "sdb": "entier (hors dictionnaire)",
    "statut": "catégorie",
}
_PROPRE = {
    "prix": r"-?\d+(\.\d+)?", "surface": r"-?\d+(\.\d+)?",
    "chambres": r"\d+", "sdb": r"\d+", "date": r"\d{4}-\d{2}-\d{2}",
}


def tableau_types(df: pd.DataFrame) -> pd.DataFrame:
    """{source, champ, type attendu, type réel, écart, action} + compteurs."""
    lignes = []
    for source, g in df.groupby("source"):
        for champ, attendu in TYPE_ATTENDU.items():
            col = g[champ]
            n, vides = len(col), int((col == "").sum())
            ligne = dict(source=source, champ=champ, type_attendu=attendu, n=n,
                         n_vides=vides, n_propres=np.nan, n_convertibles=np.nan,
                         n_non_convertibles=np.nan, n_hors_regle=np.nan)
            if vides == n:
                reel, ecart, action = "absent", "colonne non fournie par la source", "à traiter en comp 3 (champ absent)"
            elif champ in CONVERTISSEURS:
                plein = col[col != ""]
                propres = int(plein.str.fullmatch(_PROPRE[champ]).sum())
                conv = plein.map(CONVERTISSEURS[champ])
                reussis = int(conv.notna().sum())
                non_conv = len(plein) - reussis
                a_convertir = reussis - propres
                ligne.update(n_propres=propres, n_convertibles=a_convertir,
                             n_non_convertibles=non_conv)
                if champ in ("prix", "surface"):
                    ligne["n_hors_regle"] = int((conv.dropna() <= 0).sum())
                reel = "numérique" if propres == len(plein) and not non_conv else "texte mixte"
                morceaux = []
                if a_convertir: morceaux.append(f"{a_convertir} à convertir (réparable)")
                if non_conv: morceaux.append(f"{non_conv} non convertibles (structurel)")
                if vides: morceaux.append(f"{vides} vides")
                hors = 0 if pd.isna(ligne["n_hors_regle"]) else int(ligne["n_hors_regle"])
                if hors: morceaux.append(f"{hors} valeurs <= 0")
                ecart = "; ".join(morceaux) or "aucun"
                if reel == "numérique" and not vides and not hors:
                    action = "type confirmé"
                elif non_conv or vides or hors:
                    action = "convertir + traiter le reste en comp 3"
                else:
                    action = "convertir (réparable)"
            else:  # catégorielles / identifiants
                brut = col[col != ""]
                norm = brut.str.strip().str.lower()
                reel = "texte"
                ecart = f"{brut.nunique()} modalités brutes -> {norm.nunique()} après casse/espaces"
                if vides: ecart += f"; {vides} vides"
                action = "type confirmé" if brut.nunique() == norm.nunique() and not vides \
                    else "normaliser/traiter en comp 3"
            ligne.update(type_reel=reel, ecart=ecart, action=action)
            lignes.append(ligne)
    cols = ["source", "champ", "type_attendu", "type_reel", "ecart", "action",
            "n", "n_vides", "n_propres", "n_convertibles", "n_non_convertibles", "n_hors_regle"]
    return pd.DataFrame(lignes)[cols]


def charger_corpus(racine: Path = Path(".")) -> pd.DataFrame:
    return pd.read_csv(racine / "sortie" / "corpus_brut_concatene.csv",
                       dtype=str, keep_default_na=False)


def figures(d: pd.DataFrame, dossier: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dossier.mkdir(parents=True, exist_ok=True)
    v = d[d.prix_num > 0]
    ventes = v[v.segment == "vente"].prix_num
    # 1) prix brut vs log, ventes
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].hist(ventes / 1e6, bins=60, color="#c0504d")
    ax[0].set(title=f"Ventes : prix brut (skew = {_st.skew(ventes):.2f})", xlabel="prix (M FCFA)", ylabel="annonces")
    ax[1].hist(np.log(ventes), bins=60, color="#4f81bd")
    ax[1].set(title=f"Ventes : log(prix) (skew = {_st.skew(np.log(ventes)):.2f})", xlabel="log(prix)")
    fig.tight_layout(); fig.savefig(dossier / "comp1_prix_vs_log_ventes.png", dpi=110); plt.close(fig)
    # 2) pourquoi segmenter : log(prix) global (bimodal)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(np.log(v.prix_num), bins=70, color="#7f7f7f")
    ax.set(title=f"log(prix) toutes transactions (skew = {_st.skew(np.log(v.prix_num)):.2f}) : 2 populations",
           xlabel="log(prix)", ylabel="annonces")
    fig.tight_layout(); fig.savefig(dossier / "comp1_log_prix_global_bimodal.png", dpi=110); plt.close(fig)
    # 3) QQ-plots log(prix)
    fig, ax = plt.subplots(1, 3, figsize=(14, 4))
    for a, (nom, x) in zip(ax, [("log(prix) ventes", np.log(ventes)),
                                ("log(prix) locations", np.log(v[v.segment == "location"].prix_num)),
                                ("log(prix) global", np.log(v.prix_num))]):
        _st.probplot(x, dist="norm", plot=a); a.set_title(f"QQ-plot {nom}")
    fig.tight_layout(); fig.savefig(dossier / "comp1_qqplots_log_prix.png", dpi=110); plt.close(fig)
    # 4) surface
    s = d[d.surface_num > 0].surface_num
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].hist(s, bins=60, color="#9bbb59"); ax[0].set(title=f"surface brute (skew = {_st.skew(s):.2f})", xlabel="m²")
    ax[1].hist(np.log(s), bins=60, color="#8064a2"); ax[1].set(title=f"log(surface) (skew = {_st.skew(np.log(s)):.2f})", xlabel="log(m²)")
    fig.tight_layout(); fig.savefig(dossier / "comp1_surface.png", dpi=110); plt.close(fig)


def main(racine: Path = Path(".")) -> dict:
    brut = charger_corpus(racine)
    rep = racine / "reports"; rep.mkdir(exist_ok=True)
    t = tableau_types(brut); t.to_csv(rep / "comp1_types_par_source.csv", index=False)
    d = ajouter_numeriques(brut)
    sd = stats_descriptives(d); sd.to_csv(rep / "comp1_stats_descriptives.csv", index=False)
    pl = prix_vs_log(d); pl.to_csv(rep / "comp1_prix_vs_log.csv", index=False)
    tn = tests_normalite(d); tn.to_csv(rep / "comp1_normalite_shapiro.csv", index=False)
    mr = modalites_rares(brut); mr.to_csv(rep / "comp1_modalites_rares.csv", index=False)
    figures(d, rep / "figures")
    return dict(types=t, stats=sd, prix_vs_log=pl, normalite=tn, rares=mr, d=d)




# ---------------------------------------------------------------------------
# Blocs 2 à 5 : statistiques, distribution de prix/surface, modalités rares
# ---------------------------------------------------------------------------
from scipy import stats as _st  # noqa: E402

# Le corpus ne contient AUCUN prix entre 1,76 M et 5,15 M FCFA : un seuil à
# 3 M sépare loyers et ventes sans erreur sur les 1537 lignes à transaction connue.
SEUIL_LOYER_VENTE = 3_000_000


def ajouter_numeriques(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute prix_num, surface_num, categorie_cle (casse/espaces) et segment."""
    out = df.copy()
    out["prix_num"] = out["prix"].map(CONVERTISSEURS["prix"])
    out["surface_num"] = out["surface"].map(CONVERTISSEURS["surface"])
    out["categorie_cle"] = out["categorie"].str.strip().str.lower()
    connue = out["transaction"].isin(["vente", "location"])
    infere = np.where(out["prix_num"] < SEUIL_LOYER_VENTE, "location", "vente")
    out["segment"] = np.where(connue, out["transaction"], infere)
    out["segment_origine"] = np.where(connue, "connue", "inférée_par_prix")
    sans_prix_valide = ~(out["prix_num"] > 0)
    out.loc[sans_prix_valide & ~connue, ["segment", "segment_origine"]] = ["inconnu", "inconnue"]
    return out


def resume(s: pd.Series) -> dict:
    s = s.dropna()
    if len(s) < 3:
        return dict(count=len(s), mean=np.nan, median=np.nan, std=np.nan, q1=np.nan,
                    q3=np.nan, skew=np.nan, kurtosis=np.nan)
    return dict(count=len(s), mean=s.mean(), median=s.median(), std=s.std(),
                q1=s.quantile(.25), q3=s.quantile(.75),
                skew=_st.skew(s), kurtosis=_st.kurtosis(s))


def stats_descriptives(d: pd.DataFrame) -> pd.DataFrame:
    """count, mean, median, std, Q1, Q3, skew, kurtosis ; prix et surface (valeurs > 0)."""
    lignes = []
    for var in ("prix_num", "surface_num"):
        v = d[d[var] > 0]
        groupes = [("global", "tous", v)]
        groupes += [("source", s, g) for s, g in v.groupby("source")]
        groupes += [("segment", s, g) for s, g in v.groupby("segment") if s != "inconnu"]
        groupes += [("source×segment", f"{s}|{t}", g) for (s, t), g in v.groupby(["source", "segment"]) if t != "inconnu"]
        if var == "prix_num":
            vv = v[v.segment == "vente"]
            groupes += [("catégorie (ventes)", c, g) for c, g in vv.groupby("categorie_cle")]
            groupes += [("source×catégorie (ventes)", f"{s}|{c}", g) for (s, c), g in vv.groupby(["source", "categorie_cle"])]
        for niveau, cle, g in groupes:
            lignes.append(dict(variable=var.replace("_num", ""), niveau=niveau, groupe=cle,
                               n_lignes=len(g), **resume(g[var])))
    return pd.DataFrame(lignes).round(3)


def prix_vs_log(d: pd.DataFrame) -> pd.DataFrame:
    """Skew de prix brut vs log(prix), global puis par segment (livrable 3)."""
    v = d[d.prix_num > 0]
    lignes = []
    for nom, g in [("global (ventes+locations mélangées)", v)] + \
            [(f"segment {s}", g) for s, g in v.groupby("segment") if s != "inconnu"] + \
            [(f"ventes — {s}", g) for s, g in v[v.segment == "vente"].groupby("source")]:
        p = g.prix_num
        lignes.append(dict(population=nom, n=len(p), mean=p.mean(), median=p.median(),
                           ratio_mean_median=p.mean() / p.median(),
                           skew_brut=_st.skew(p), skew_log=_st.skew(np.log(p)),
                           kurtosis_brut=_st.kurtosis(p), kurtosis_log=_st.kurtosis(np.log(p))))
    return pd.DataFrame(lignes).round(3)


def tests_normalite(d: pd.DataFrame, n_ech: int = 500, graine: int = 42) -> pd.DataFrame:
    """Shapiro (échantillon) sur prix et log(prix), par segment."""
    lignes = []
    for seg in ("vente", "location"):
        p = d[(d.prix_num > 0) & (d.segment == seg)].prix_num
        ech = p.sample(min(n_ech, len(p)), random_state=graine)
        for nom, x in (("prix", ech), ("log(prix)", np.log(ech))):
            w, pv = _st.shapiro(x)
            lignes.append(dict(segment=seg, variable=nom, n_total=len(p), n_echantillon=len(x),
                               W=w, p_value=pv, normal_a_5pct=bool(pv > .05)))
    return pd.DataFrame(lignes).round(4)


def modalites_rares(df: pd.DataFrame, seuil: int = 10) -> pd.DataFrame:
    """Modalités brutes < seuil (effectif global ET par source) — décision en comp 3."""
    lignes = []
    for champ in ("categorie", "region", "ville", "statut", "transaction"):
        brut = df[df[champ] != ""]
        glob = brut[champ].value_counts()
        for m, n in glob[glob < seuil].items():
            srcs = brut[brut[champ] == m]["source"].value_counts().to_dict()
            lignes.append(dict(champ=champ, modalite=m, effectif_global=int(n), portee="global", sources=srcs))
        par = brut.groupby(["source", champ]).size()
        for (s, m), n in par[par < seuil].items():
            if glob[m] >= seuil:
                lignes.append(dict(champ=champ, modalite=m, effectif_global=int(glob[m]),
                                   portee=f"rare dans {s} ({n})", sources={s: int(n)}))
    return pd.DataFrame(lignes)


if __name__ == "__main__":
    r = main()
    pd.set_option("display.width", 250, "display.max_colwidth", 80)
    print(r["prix_vs_log"].to_string(index=False))
