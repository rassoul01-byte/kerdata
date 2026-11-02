"""Compétence 5 : audits des variables avant encodage (statut, source, commune, région) et cartographie.

Tout est calculé sur le segment `vente` du corpus conservé (comp 3). Aucune valeur écrite en dur :
chaque décision cite la mesure qui la fonde.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

from .viz import ventes


def preparer(conserve: pd.DataFrame) -> pd.DataFrame:
    v = ventes(conserve)
    v["y"] = np.log(v.prix)
    v["prix_std"] = v.prix / v.groupby("categorie").prix.transform("median")   # prix relatif à sa catégorie
    v["ly"] = np.log(v.prix_std)
    dt = pd.to_datetime(v.date)
    v["annee"], v["mois"] = dt.dt.year, dt.dt.month
    v["statut"] = v.statut.fillna("(vide)")
    return v


def eta2(df: pd.DataFrame, col: str, y: str) -> tuple[float, float, float]:
    """(eta², omega² corrigé du nombre de groupes, p-value ANOVA)."""
    g = df.groupby(col)[y]
    n, k = len(df), g.ngroups
    sst = ((df[y] - df[y].mean()) ** 2).sum()
    ssb = sum(len(x) * (x.mean() - df[y].mean()) ** 2 for _, x in g)
    msw = (sst - ssb) / (n - k)
    omega = (ssb - (k - 1) * msw) / (sst + msw)
    p = st.f_oneway(*[x.to_numpy() for _, x in g])[1]
    return ssb / sst, omega, p


def cramer_v(a: pd.Series, b: pd.Series) -> float:
    ct = pd.crosstab(a, b)
    return float(np.sqrt(st.chi2_contingency(ct, correction=False)[0] / (ct.values.sum() * (min(ct.shape) - 1))))


def audit_statut(v: pd.DataFrame) -> dict:
    s = v[v.statut != "(vide)"]
    e, w, p = eta2(s, "statut", "ly")
    return dict(
        effectifs=v.statut.value_counts().to_dict(), eta2=e, omega2=w, p_anova=p,
        medianes_prix_std=s.groupby("statut").prix_std.median().round(3).to_dict(),
        v_source_statut=cramer_v(v.source, v.statut), v_statut_categorie=cramer_v(s.statut, s.categorie),
        pct_vide_par_source=(v.statut == "(vide)").groupby(v.source).mean().mul(100).round(1).to_dict(),
        n_vendu=int((v.statut == "Vendu").sum()),
    )


def audit_source(v: pd.DataFrame) -> dict:
    e, w, p = eta2(v, "source", "ly")
    eb, _, _ = eta2(v, "source", "y")
    return dict(eta2_prix_std=e, omega2_prix_std=w, p_anova=p, eta2_prix_brut=eb,
                v_source_categorie=cramer_v(v.source, v.categorie), v_source_statut=cramer_v(v.source, v.statut),
                v_source_transaction_origine=cramer_v(v.source, v.transaction_origine))


def audit_commune_region(v: pd.DataFrame) -> dict:
    vc = v.ville.value_counts()
    e_v, w_v, p_v = eta2(v, "ville", "ly")
    e_r, w_r, p_r = eta2(v, "region", "ly")
    return dict(
        n_villes=len(vc), n_villes_moins_10=int((vc < 10).sum()), part_lignes_villes_moins_10=100 * vc[vc < 10].sum() / len(v),
        eff_mediane=float(vc.median()), eff_min=int(vc.min()), omega2_ville=w_v, eta2_ville=e_v,
        n_regions=v.region.nunique(), eff_min_region=int(v.region.value_counts().min()), omega2_region=w_r, eta2_region=e_r, p_region=p_r,
        gain_ville_vs_region=w_v - w_r, villes_multi_regions=int((v.groupby("ville").region.nunique() > 1).sum()),
    )


def audit_temps(v: pd.DataFrame) -> dict:
    return dict(eta2_annee=eta2(v, "annee", "ly")[0], eta2_mois=eta2(v, "mois", "ly")[0],
                p_annee=eta2(v, "annee", "ly")[2], p_mois=eta2(v, "mois", "ly")[2])


def audit_numeriques(v: pd.DataFrame) -> dict:
    return dict(skew_surface=st.skew(v.surface), skew_log1p_surface=st.skew(np.log1p(v.surface)),
                prix_min=float(v.prix.min()), surface_min=float(v.surface.min()), surface_max=float(v.surface.max()),
                pct_chambres_vide=100 * v.chambres.isna().mean(), pct_sdb_vide=100 * v.sdb.isna().mean())


def tableau_variables(v: pd.DataFrame, a: dict) -> pd.DataFrame:
    s, so, cr, t, n = a["statut"], a["source"], a["cr"], a["temps"], a["num"]
    L = [
        ("prix (cible)", "numérique", "—", "—", "non", "log(prix) ; pas de scaler (c'est la cible)",
         f"skew {st.skew(v.prix):.2f} → {st.skew(v.y):.2f} ; prix minimum = {n['prix_min']:.0f} > 0, le log est défini"),
        ("transaction", "catégorielle binaire", v.transaction.nunique(), "non", "oui",
         "EXCLUE (constante sur le segment vente)", "le modèle porte sur les ventes (comp 1, décision 1.6) : une seule valeur, variance nulle ; binaire 0/1 si un modèle commun était fait"),
        ("categorie", "catégorielle", v.categorie.nunique(), "non", "oui", "one-hot (7 colonnes), handle_unknown=ignore",
         "pas d'ordre ; porte l'essentiel du signal (η² = 0,74, comp 2) ; label encoding interdit (faux ordre)"),
        ("region", "catégorielle", cr["n_regions"], "non", "oui", "one-hot (14 colonnes), handle_unknown=ignore",
         f"effectif minimum {cr['eff_min_region']} ; explique ω² = {100 * cr['omega2_region']:.1f} % du prix relatif (p = {cr['p_region']:.1e})"),
        ("ville (commune)", "catégorielle", cr["n_villes"], "non", "oui", "EXCLUE du one-hot (frequency à tester en comp 6)",
         f"emboîtée dans région (exception : {cr['villes_multi_regions']} ville à 2 régions, les lignes Dakar/Ziguinchor signalées en comp 3) ; gain ω² ville vs région = {100 * cr['gain_ville_vs_region']:.1f} point pour {cr['n_villes']} colonnes"),
        ("statut", "catégorielle", len(s["effectifs"]), "non", "NON (Vendu = information postérieure à la mise en vente)", "EXCLUE (fuite type 2)",
         f"V(source, statut) = {s['v_source_statut']:.2f} : proxy de la source (fuite type 4) ; aucun lien avec le prix relatif (η² = {s['eta2']:.4f}, p = {s['p_anova']:.2f})"),
        ("source", "catégorielle", v.source.nunique(), "non", "NON (identifiant de flux)", "EXCLUE (audit seulement)",
         f"η² sur le prix relatif = {so['eta2_prix_std']:.4f} (aucun signal) ; V(source, catégorie) = {so['v_source_categorie']:.2f} : proxy de composition"),
        ("transaction_origine", "catégorielle", v.transaction_origine.nunique(), "non", "NON (métadonnée de nettoyage)", "EXCLUE (fuite type 4)",
         f"V(source, transaction_origine) = {so['v_source_transaction_origine']:.2f} : reconstitue la source"),
        ("surface", "numérique", "—", "—", "oui", "log1p puis RobustScaler",
         f"skew {n['skew_surface']:.2f} → {n['skew_log1p_surface']:.2f} ; outliers conservés (comp 3) → échelle robuste ; seule, non prédictive (Simpson, comp 2/4)"),
        ("chambres", "numérique entière", "—", "—", "oui", "imputation par catégorie (fit train) puis RobustScaler",
         f"{n['pct_chambres_vide']:.1f} % vides, structurels (plateforme 100 %) ; aucun indicateur de manque (révélerait la source)"),
        ("sdb", "numérique entière", "—", "—", "oui", "imputation par catégorie (fit train) puis RobustScaler",
         f"{n['pct_sdb_vide']:.1f} % vides, structurels (notaires 100 %) ; aucun indicateur de manque"),
        ("date → annee, mois", "temporelle", "—", "cyclique (mois)", "oui", "annee (StandardScaler) + mois en sin/cos ; candidats, élagage en comp 6",
         f"aucun signal : η² annee = {t['eta2_annee']:.4f}, mois = {t['eta2_mois']:.4f} ; cohérent avec l'absence de tendance (comp 2)"),
        ("id, ligne_id", "identifiant", "—", "—", "non", "EXCLUES", "identifiants : aucune information sur le bien"),
    ]
    return pd.DataFrame(L, columns=["variable", "type", "cardinalite", "ordre", "dispo_en_prod", "encodage_ou_scaler", "justification"])


def auditer(conserve: pd.DataFrame) -> dict:
    v = preparer(conserve)
    a = dict(statut=audit_statut(v), source=audit_source(v), cr=audit_commune_region(v), temps=audit_temps(v), num=audit_numeriques(v))
    a["tableau"] = tableau_variables(v, a)
    a["v"] = v
    return a


def main(racine: Path = Path(".")) -> dict:
    a = auditer(pd.read_csv(racine / "sortie" / "corpus_conserve.csv"))
    rep = racine / "reports"; rep.mkdir(exist_ok=True)
    a["tableau"].to_csv(rep / "comp5_tableau_variables.csv", index=False)
    plats = {f"{k}.{kk}": vv for k in ("statut", "source", "cr", "temps", "num") for kk, vv in a[k].items() if not isinstance(vv, dict)}
    pd.Series(plats).to_csv(rep / "comp5_audits_mesures.csv", header=["valeur"])
    return a


if __name__ == "__main__":
    pd.set_option("display.width", 250, "display.max_colwidth", 120)
    print(main()["tableau"][["variable", "encodage_ou_scaler"]].to_string(index=False))
