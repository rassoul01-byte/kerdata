"""Compétence 6 : gain de chaque candidate mesuré en validation croisée (k = 5) sur le TRAIN uniquement.

Méthode : baseline `categorie` ; une candidate à la fois ; gain = R²(base + candidate) − R²(base), plis appariés ;
seuil ±0,01. Modèle principal : Ridge. Confirmation : forêt aléatoire (pour ne pas décider sur un seul modèle).
Le validation et le test ne sont jamais lus ici.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, cross_val_score
from sklearn.pipeline import Pipeline

from .features import ajouter_derivees, construire_transformeur

GRAINE = 42
K = 5
SEUIL = 0.01
SEUIL_FUITE = 0.95          # un R² au-delà est implausible pour un prix : on soupçonne une fuite

# nom, type, blocs, base, idée métier, risque, sens métier fort ?, rejet de principe
CANDIDATES = [
    dict(nom="region", type="existante", blocs=["region"], base=["categorie"], metier=True,
         idee="la localisation influence le prix", risque="faible (14 modalités, effectif min 161)"),
    dict(nom="surface_log", type="existante", blocs=["surface_log"], base=["categorie"], metier=True,
         idee="la taille du bien", risque="Simpson : pente globale trompeuse, nulle dans chaque catégorie (comp 2/4)"),
    dict(nom="annee", type="existante", blocs=["annee"], base=["categorie"], metier=False,
         idee="effet marché annuel", risque="aucune tendance (Mann-Kendall p > 0,05, comp 2)"),
    dict(nom="mois", type="existante", blocs=["mois"], base=["categorie"], metier=False,
         idee="saisonnalité", risque="aucune preuve de saisonnalité"),
    dict(nom="chambres_sdb", type="existante", blocs=["chambres_sdb"], base=["categorie"], metier=False,
         idee="confort du bien", risque="26,8 % et 15,4 % de manques structurels imputés ; aucune relation intra-catégorie (comp 2)"),
    dict(nom="distance_dakar_km", type="créée", blocs=["distance_dakar_km"], base=["categorie", "region"], metier=False,
         idee="proximité de la capitale", risque="redondante : fonction exacte de `region` (une paire de coordonnées par région)"),
    dict(nom="ville_frequence", type="créée", blocs=["ville_frequence"], base=["categorie", "region"], metier=False,
         idee="taille de marché de la commune (frequency encoding, alternative au one-hot)", risque="bruit ; la commune est emboîtée dans la région (comp 5)"),
    dict(nom="surface_x_categorie", type="créée", blocs=["surface_x_categorie"], base=["categorie"], metier=False,
         idee="une pente de surface par catégorie (réponse au paradoxe de Simpson)", risque="7 colonnes ; pentes intra-catégorie ≈ 0"),
    dict(nom="surface_par_chambre", type="créée", blocs=["surface_par_chambre"], base=["categorie"], metier=False,
         idee="densité d'occupation", risque="dépend de `chambres`, structurellement manquante pour 26,8 %"),
    dict(nom="prix_m2", type="fuite (test)", blocs=["prix_m2"], base=["categorie"], metier=False, principe="fuite type 1 : contient `prix`",
         idee="prix au m²", risque="contient la cible"),
    dict(nom="prix_m2 + surface_log", type="fuite (test)", blocs=["prix_m2", "surface_log"], base=["categorie"], metier=False, principe="fuite type 1 : contient `prix`",
         idee="prix au m² accompagné de la surface (log prix = log prix_m2 + log surface)", risque="reconstitue la cible exactement"),
    dict(nom="ratio_prix_fourchette", type="fuite (test)", blocs=["ratio_prix_fourchette"], base=["categorie"], metier=False, principe="fuite type 1 : contient `prix`",
         idee="position du prix dans la fourchette de sa catégorie", risque="contient la cible"),
    dict(nom="est_hors_fourchette", type="fuite (test)", blocs=["est_hors_fourchette"], base=["categorie"], metier=False, principe="fuite type 1 : dérivé de `prix`",
         idee="signal d'anomalie", risque="dérivé de la cible ; redondant avec les avertissements de la comp 3"),
    dict(nom="source", type="audit", blocs=["source"], base=["categorie"], metier=False, principe="fuite type 4 : identifiant de flux",
         idee="effet du flux de données", risque="proxy de la qualité du flux, pas du bien"),
    dict(nom="statut", type="audit", blocs=["statut"], base=["categorie"], metier=False, principe="fuite types 2 et 4 : connu après la mise en vente, proxy de la source",
         idee="état de la vente", risque="information postérieure à la prédiction"),
]


def charger_train(racine: Path = Path(".")) -> pd.DataFrame:
    c = pd.read_csv(racine / "sortie" / "corpus_conserve.csv")
    sp = pd.read_csv(racine / "sortie" / "split.csv")
    v = c[c.transaction == "vente"].merge(sp, on="ligne_id")
    train = v[v.ensemble == "train"].reset_index(drop=True)
    assert set(train.ensemble) == {"train"}, "seul le train peut être lu ici"
    return ajouter_derivees(train, racine)


def _modele(nom: str):
    if nom == "ridge":
        return Ridge(alpha=1.0)
    return RandomForestRegressor(n_estimators=150, min_samples_leaf=3, random_state=GRAINE, n_jobs=-1)


def scores(df: pd.DataFrame, y: pd.Series, blocs: list[str], modele: str = "ridge") -> np.ndarray:
    pipe = Pipeline([("ct", construire_transformeur(blocs)), ("m", _modele(modele))])
    return cross_val_score(pipe, df, y, cv=KFold(K, shuffle=True, random_state=GRAINE), scoring="r2")


def decider(c: dict, gain: float, gain_rf: float, r2_avec: float) -> tuple[str, str]:
    """-> (décision, justification chiffrée)."""
    g = f"gain Ridge {gain:+.4f}, forêt {gain_rf:+.4f}"
    if c["type"].startswith("fuite") and (r2_avec > SEUIL_FUITE or gain > 0.05):
        return "REJETÉE (fuite)", f"mirage confirmé : R² = {r2_avec:.3f} ({g}) ; {c['principe']}"
    if c["type"].startswith("fuite"):
        return "REJETÉE (fuite)", f"rejet de principe : {c['principe']} ; le gain mesuré ({g}) ne change rien"
    if c["type"] == "audit":
        return "EXCLUE (principe)", f"{c['principe']} ; {g}"
    if c["nom"] == "distance_dakar_km":
        return "EXCLUE (redondante)" if gain < SEUIL else "À RÉÉVALUER", f"{c['risque']} ; {g} vs catégorie + région"
    if gain > SEUIL:
        return "GARDER", f"gain > +{SEUIL} ({g})"
    if gain < -SEUIL:
        return "EXCLURE", f"gain < −{SEUIL} ({g})"
    if c["metier"]:
        alerte = (f" ; ALERTE : la forêt perd {abs(gain_rf):.3f} de R² avec cette variable, à exclure si le modèle final est à base d'arbres"
                  if gain_rf < -SEUIL else "")
        return "GARDER (neutre, sens métier fort)", f"gain neutre ({g}) mais sens métier fort : {c['idee']} ; à réévaluer{alerte}"
    return "EXCLURE (neutre, sens métier faible)", f"gain neutre ({g}) et sens métier faible : {c['risque']}"


def mesurer(train: pd.DataFrame) -> pd.DataFrame:
    y = np.log(train["prix"])
    base_cache: dict[tuple, np.ndarray] = {}

    def sc(blocs, m):
        k = (tuple(blocs), m)
        if k not in base_cache:
            base_cache[k] = scores(train, y, blocs, m)
        return base_cache[k]

    lignes = []
    for c in CANDIDATES:
        b, ex = c["base"], c["blocs"]
        avec, base = sc(b + ex, "ridge"), sc(b, "ridge")
        avec_rf, base_rf = sc(b + ex, "rf"), sc(b, "rf")
        gain, gain_rf = float((avec - base).mean()), float((avec_rf - base_rf).mean())
        gain_cat = float((sc(["categorie"] + ex, "ridge") - sc(["categorie"], "ridge")).mean())
        dec, just = decider(c, gain, gain_rf, float(avec.mean()))
        lignes.append(dict(
            variable=c["nom"], type=c["type"], base="+".join(b), r2_seul=float(sc(ex, "ridge").mean()), r2_base=float(base.mean()),
            r2_avec=float(avec.mean()), gain=gain, gain_ecart_type_plis=float((avec - base).std()), gain_vs_categorie=gain_cat,
            gain_foret=gain_rf, decision=dec, justification=just, idee_metier=c["idee"], risque=c["risque"]))
    return pd.DataFrame(lignes)


def features_retenues(tab: pd.DataFrame) -> list[str]:
    garde = tab[tab.decision.str.startswith("GARDER")].variable.tolist()
    return ["categorie"] + garde


def dictionnaire(tab: pd.DataFrame, retenues: list[str]) -> pd.DataFrame:
    meta = {
        "categorie": ("colonne du corpus", "catégorielle", "one-hot, handle_unknown=ignore", "oui"),
        "region": ("colonne du corpus", "catégorielle", "one-hot, handle_unknown=ignore", "oui"),
        "surface_log": ("colonne du corpus", "numérique", "log1p puis RobustScaler", "oui"),
        "annee": ("dérivée de `date`", "numérique", "StandardScaler", "oui"),
        "mois": ("dérivée de `date`", "cyclique", "sin/cos sur 12", "oui"),
        "chambres_sdb": ("colonnes du corpus", "numérique", "imputation médiane par catégorie (fit pli) puis RobustScaler", "oui"),
        "distance_dakar_km": ("dérivée de `region` (coordonnées du référentiel)", "numérique", "haversine vs Dakar, StandardScaler", "oui"),
        "ville_frequence": ("dérivée de `ville`", "numérique", "log(1 + effectif dans le pli)", "oui"),
        "surface_x_categorie": ("interaction categorie × surface_log", "numérique (7 colonnes)", "pente de surface par catégorie", "oui"),
        "surface_par_chambre": ("dérivée de `surface`, `chambres`", "numérique", "log1p(surface / (chambres + 1)), robuste", "oui"),
        "prix_m2": ("dérivée de `prix` / `surface`", "numérique", "log(prix / surface)", "NON (contient la cible)"),
        "prix_m2 + surface_log": ("dérivée de `prix`", "numérique", "log(prix / surface) + log1p(surface)", "NON (contient la cible)"),
        "ratio_prix_fourchette": ("dérivée de `prix`", "numérique", "(prix − min) / (max − min) de la catégorie", "NON (contient la cible)"),
        "est_hors_fourchette": ("dérivée de `prix`", "binaire", "prix hors fourchette référentiel", "NON (contient la cible)"),
        "source": ("colonne du corpus", "catégorielle", "one-hot", "NON (identifiant de flux)"),
        "statut": ("colonne du corpus", "catégorielle", "one-hot", "NON (postérieur à la vente)"),
    }
    base = pd.DataFrame([dict(variable="categorie", type="baseline", r2_seul=np.nan, gain=np.nan, decision="GARDER (baseline)",
                              justification="porte l'essentiel du signal (η² = 0,74, comp 2)")])
    t = pd.concat([base, tab], ignore_index=True)
    out = pd.DataFrame({
        "feature": t.variable,
        "origine": t.variable.map(lambda v: meta[v][0]), "type": t.variable.map(lambda v: meta[v][1]),
        "transformation": t.variable.map(lambda v: meta[v][2]), "disponible_en_production": t.variable.map(lambda v: meta[v][3]),
        "r2_seul_cv_train": t.r2_seul.round(4), "gain_cv_train": t.gain.round(4), "decision": t.decision,
        "retenue_modele_final": t.variable.isin(retenues), "justification": t.justification})
    return out


def main(racine: Path = Path(".")) -> dict:
    racine = Path(racine)
    train = charger_train(racine)
    tab = mesurer(train)
    ret = features_retenues(tab)
    rep = racine / "reports"; rep.mkdir(exist_ok=True)
    tab.round(5).to_csv(rep / "comp6_candidates.csv", index=False)
    dictionnaire(tab, ret).to_csv(rep / "dictionnaire_features.csv", index=False)
    (rep / "features_retenues.json").write_text(json.dumps(
        dict(retenues=ret, seuil=SEUIL, k=K, graine=GRAINE, rejetees=tab[~tab.decision.str.startswith("GARDER")].variable.tolist()),
        ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(tab=tab, retenues=ret, n_train=len(train))


if __name__ == "__main__":
    pd.set_option("display.width", 250, "display.max_colwidth", 70)
    r = main()
    print(r["tab"][["variable", "r2_seul", "gain", "gain_ecart_type_plis", "gain_foret", "decision"]].round(4).to_string(index=False))
    print("retenues :", r["retenues"])


def markdown(tab: pd.DataFrame, retenues: list[str], n_train: int) -> str:
    from .qualite import md_table
    t = tab[["variable", "type", "base", "r2_seul", "r2_avec", "gain", "gain_foret", "decision"]].copy()
    for c in ("r2_seul", "r2_avec", "gain", "gain_foret"):
        t[c] = t[c].map(lambda x: f"{x:+.4f}" if c.startswith("gain") else f"{x:.4f}")
    base = tab.r2_base.iloc[0]
    return f"""## Feature engineering (compétence 6)

CV à {K} plis sur le **train seul** ({n_train} lignes), baseline `categorie` : R² = {base:.4f}. Une candidate à la fois, seuil ±{SEUIL}, graine {GRAINE}.
Les fuites sont créées volontairement pour constater le mirage : `prix_m2 + surface_log` atteint R² = {tab.set_index('variable').loc['prix_m2 + surface_log', 'r2_avec']:.4f}.

{md_table(t)}
**Features retenues : {", ".join(retenues)}.** Dictionnaire complet : `reports/dictionnaire_features.csv`.
"""
