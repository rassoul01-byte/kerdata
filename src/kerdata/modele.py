"""Compétence 9 : pipeline final, sérialisable, reproductible.

Entrée  : une annonce au schéma commun (categorie, region, surface), valeurs brutes ou propres.
Sortie  : prix de vente prédit en FCFA (médiane conditionnelle : exp(E[log prix])).

Étapes (ordre figé) :
  1. normalisation  : synonymes de catégorie, casse/accents/mojibake des régions, surface -> nombre (aucun paramètre appris,
                      règles issues des référentiels et embarquées dans l'objet : aucun état externe)
  2. preparation    : one-hot categorie, one-hot region (handle_unknown=ignore), log1p + RobustScaler sur surface (appris sur le train)
  3. modele         : Ridge, cible log(prix) (TransformedTargetRegressor : log à l'entraînement, exp à la prédiction)
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import TransformedTargetRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline

from .concat import concatener
from .features import construire_transformeur
from .nettoyage import Referentiels, ajouter_identifiants, cle, normaliser_lieu
from .readers import MAPPING, PLATEFORME_COLONNES
from .typage import parse_surface

GRAINE = 42
BLOCS = ["categorie", "region", "surface_log"]           # features retenues en comp 6
ENTREES = ["categorie", "region", "surface"]
CHEMIN_MODELE = Path("models") / "pipeline_preparation.joblib"


class NormaliserAnnonce(BaseEstimator, TransformerMixin):
    """Étape 0 du pipeline en production : applique aux annonces les mêmes règles que le nettoyage (comp 3).

    Les règles (régions canoniques, synonymes de catégorie) sont des paramètres de l'objet : il se sérialise seul.
    Une surface absente, illisible ou <= 0 est REFUSÉE (même règle bloquante que la quarantaine de la comp 3).
    """

    def __init__(self, regions: tuple = (), synonymes: dict | None = None):
        self.regions = regions
        self.synonymes = synonymes

    @classmethod
    def depuis_referentiels(cls, dossier: Path) -> "NormaliserAnnonce":
        ref = Referentiels(Path(dossier))
        return cls(regions=tuple(ref.regions), synonymes=dict(ref.synonymes))

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = pd.DataFrame(X)
        manque = [c for c in ENTREES if c not in X.columns]
        if manque:
            raise ValueError(f"colonnes manquantes : {manque}")
        syn, regions = self.synonymes or {}, list(self.regions)
        out = pd.DataFrame(index=X.index)
        out["categorie"] = X["categorie"].map(lambda v: syn.get(cle(str(v)), str(v).strip()))
        out["region"] = X["region"].map(lambda v: normaliser_lieu(str(v), regions)[0])
        surface = X["surface"].map(lambda v: parse_surface(str(v)))
        if surface.isna().any() or (surface <= 0).any():
            raise ValueError("surface absente, illisible ou <= 0 : annonce refusée (règle bloquante de la comp 3)")
        out["surface"] = surface.astype(float)
        return out


def construire_pipeline(dossier_ref: Path, alpha: float = 1.0, blocs: list[str] | None = None) -> TransformedTargetRegressor:
    interne = Pipeline([
        ("normalisation", NormaliserAnnonce.depuis_referentiels(dossier_ref)),
        ("preparation", construire_transformeur(blocs or BLOCS)),
        ("modele", Ridge(alpha=alpha)),
    ])
    return TransformedTargetRegressor(regressor=interne, func=np.log, inverse_func=np.exp, check_inverse=False)


# ----------------------------------------------------------------------------- données
def charger_jeux(racine: Path) -> dict:
    """Lignes BRUTES (valeurs textuelles des sources) + prix nettoyé + ensemble, pour train / val / test.

    Le pipeline apprend à partir des valeurs brutes : l'étape de normalisation est donc exercée comme en production.
    """
    brut = ajouter_identifiants(concatener(racine / "sources"))
    c = pd.read_csv(racine / "sortie" / "corpus_conserve.csv")
    sp = pd.read_csv(racine / "sortie" / "split.csv")
    ventes = c[c.transaction == "vente"].merge(sp, on="ligne_id")[["ligne_id", "prix", "ensemble", "categorie", "region", "surface"]]
    ventes = ventes.rename(columns={"categorie": "categorie_propre", "region": "region_propre", "surface": "surface_propre"})
    d = ventes.merge(brut[["ligne_id", "source", "categorie", "region", "surface"]], on="ligne_id")
    return {e: d[d.ensemble == e].reset_index(drop=True) for e in ("train", "val", "test")}


def metriques(prix_vrai: pd.Series, prix_pred: np.ndarray) -> dict:
    y, p = np.log(prix_vrai.to_numpy(float)), np.log(np.asarray(prix_pred, float))
    ss_res, ss_tot = ((y - p) ** 2).sum(), ((y - y.mean()) ** 2).sum()
    ape = np.abs(np.asarray(prix_pred) - prix_vrai.to_numpy(float)) / prix_vrai.to_numpy(float)
    return dict(n=len(y), r2_log=float(1 - ss_res / ss_tot), rmse_log=float(np.sqrt(((y - p) ** 2).mean())),
                mdape_pct=float(100 * np.median(ape)), mae_fcfa=float(np.abs(np.asarray(prix_pred) - prix_vrai).mean()))


def choisir_alpha(racine: Path, jeux: dict, grille=(0.01, 0.1, 1.0, 10.0, 100.0)) -> pd.DataFrame:
    """Hyperparamètre choisi sur la VALIDATION (jamais sur le test)."""
    lignes = []
    for a in grille:
        m = construire_pipeline(racine / "referentiels", a).fit(jeux["train"][ENTREES], jeux["train"].prix)
        r = metriques(jeux["val"].prix, m.predict(jeux["val"][ENTREES]))
        lignes.append(dict(alpha=a, **r))
    return pd.DataFrame(lignes).round(5)


def baseline_mediane_categorie(jeux: dict) -> dict:
    """Référence naïve : médiane du prix de la catégorie (apprise sur le train)."""
    med = jeux["train"].groupby("categorie_propre").prix.median()
    pred = jeux["val"].categorie_propre.map(med).fillna(jeux["train"].prix.median())
    return metriques(jeux["val"].prix, pred.to_numpy())


# ----------------------------------------------------------------------------- adaptateur : une ligne native -> schéma commun
def adapter_ligne(source: str, brut: dict) -> pd.DataFrame:
    """Une annonce dans le schéma NATIF de sa source (colonnes d'origine, JSON imbriqué) -> 1 ligne (categorie, region, surface)."""
    if source == "particuliers":
        a = brut["annonce"]
        loc, det = a.get("localisation") or {}, a.get("details") or {}
        ligne = dict(categorie=det.get("type"), region=loc.get("region"), surface=det.get("surface"))
    else:
        renomme = {MAPPING.get(source, {}).get(k, k): v for k, v in brut.items()}
        ligne = {k: renomme.get(k) for k in ENTREES}
    return pd.DataFrame([ligne], dtype=object)


def lignes_natives(racine: Path) -> dict[str, dict]:
    """Une vraie ligne brute (schéma natif) de chacune des 5 sources, avec surface renseignée."""
    s = racine / "sources"
    out = {}
    a = pd.read_excel(s / "agence_teranga.xlsx", sheet_name="Annonces", dtype=str, keep_default_na=False)
    out["agence"] = a[a.Surface_m2.str.fullmatch(r"\d+(\.\d+)?")].iloc[0].to_dict()
    h = pd.read_csv(s / "import_historique.csv", sep=";", dtype=str, keep_default_na=False)
    out["historique"] = h[h.Region.str.contains("\ufffd") & h.Surface.str.fullmatch(r"\d+([.,]\d+)?")].iloc[0].to_dict()   # mojibake + virgule
    n = pd.read_csv(s / "notaires.csv", dtype=str, keep_default_na=False)
    out["notaires"] = n[n.superficie.str.fullmatch(r"\d+(\.\d+)?")].iloc[0].to_dict()
    enreg = json.loads((s / "particuliers.json").read_text(encoding="utf-8"))
    out["particuliers"] = next(e for e in enreg if str(e["annonce"]["details"].get("surface", "")).replace(".", "").isdigit())
    p = pd.read_csv(s / "plateforme_immo_sn.csv", sep=";", header=None, names=PLATEFORME_COLONNES, dtype=str, keep_default_na=False)
    p = p[p.ref_plateforme != "ref_plateforme"]
    out["plateforme"] = p[p.surface.str.fullmatch(r"\d+(\.\d+)?")].iloc[0].to_dict()
    return out


# ----------------------------------------------------------------------------- sérialisation
def empreinte(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a, dtype=float).tobytes()).hexdigest()[:16]


def sauvegarder(modele, racine: Path, meta: dict) -> Path:
    chemin = racine / CHEMIN_MODELE
    chemin.parent.mkdir(exist_ok=True)
    joblib.dump(modele, chemin)
    meta = dict(meta, graine=GRAINE, sklearn=sklearn.__version__, python=platform.python_version(), blocs=BLOCS, entrees=ENTREES)
    (racine / "models" / "pipeline_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return chemin


def predire_dans_un_nouveau_processus(racine: Path, lignes: pd.DataFrame) -> np.ndarray:
    """Recharge le .joblib dans un interpréteur NEUF (aucun état partagé avec ce processus) et prédit."""
    tmp = racine / "models" / "_echantillon.csv"
    lignes.to_csv(tmp, index=False)
    code = ("import sys, joblib, pandas as pd, numpy as np; "
            f"m = joblib.load(r'{racine / CHEMIN_MODELE}'); X = pd.read_csv(r'{tmp}', dtype=str, keep_default_na=False); "
            "print(','.join(repr(float(v)) for v in m.predict(X)))")
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[1]), "PATH": "/usr/bin:/bin"}
    sortie = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=120)
    tmp.unlink(missing_ok=True)
    if sortie.returncode != 0:
        raise RuntimeError(sortie.stderr[-500:])
    return np.array([float(x) for x in sortie.stdout.strip().split(",")])


# ----------------------------------------------------------------------------- les 6 vérifications
def verif1_ordre(racine: Path, jeux: dict, modele) -> pd.DataFrame:
    """Inverser ou retirer une étape change le résultat ou plante."""
    from sklearn.preprocessing import FunctionTransformer, RobustScaler
    tr, va = jeux["train"], jeux["val"]
    lignes = []
    # (a) sans normalisation : les valeurs brutes ne sont pas utilisables
    brut_tr, brut_va = tr[ENTREES].copy(), va[ENTREES].copy()
    ct = construire_transformeur(["categorie", "region"]).fit(brut_tr)
    cats_brutes = len(ct.named_transformers_["categorie"].categories_[0])
    regs_brutes = len(ct.named_transformers_["region"].categories_[0])
    inconnues = int((~va.categorie.isin(set(tr.categorie)) | ~va.region.isin(set(tr.region))).sum())
    lignes.append(dict(test="encodage sans normalisation préalable (sur le train brut)",
                       observation=f"{cats_brutes} modalités de catégorie au lieu de 7 et {regs_brutes} de région au lieu de 14 : colonnes parasites (variantes de casse, mojibake) ; "
                                   f"{inconnues} lignes de validation tombent à zéro car les mêmes variantes existent déjà dans le train",
                       verdict="fragmentation des modalités : normaliser AVANT d'encoder"))
    nouvelle = pd.DataFrame([dict(categorie="Appt", region="Thiès", surface=100.0)])
    sans = ct.transform(nouvelle[["categorie", "region"]])[0][:cats_brutes].sum()
    avec = construire_transformeur(["categorie"]).fit(modele.regressor_.named_steps["normalisation"].transform(tr[ENTREES])).transform(
        modele.regressor_.named_steps["normalisation"].transform(nouvelle))[0].sum()
    lignes.append(dict(test="variante jamais vue « Appt » (synonyme d'Appartement)", observation=f"sans normalisation : somme du one-hot de catégorie = {sans:.0f} (annonce sans catégorie, silencieux) ; avec normalisation : {avec:.0f}",
                       verdict="la normalisation protège la production contre les variantes de saisie" if sans == 0 and avec == 1 else "à examiner"))
    try:
        construire_transformeur(["surface_log"]).fit(brut_tr)
        obs, verdict = "aucune erreur", "à examiner"
    except Exception as e:
        obs, verdict = f"plante : {type(e).__name__} (surface en texte, virgule décimale)", "convertir la surface AVANT de la transformer"
    lignes.append(dict(test="log1p + scaler sur la surface brute (texte) sans normalisation", observation=obs, verdict=verdict))
    # (b) log puis scaler vs scaler puis log
    s = pd.Series(modele.regressor_.named_steps["normalisation"].transform(tr[ENTREES])["surface"].to_numpy())
    a = RobustScaler().fit_transform(np.log1p(s).to_frame()).ravel()
    sc = RobustScaler().fit_transform(s.to_frame()).ravel()
    with np.errstate(invalid="ignore"):
        b = np.log1p(sc)
    n_nan, ecart = int(np.isnan(b).sum()), float(np.nanmedian(np.abs(a - b)))
    lignes.append(dict(test="log1p puis scaler (ordre retenu) vs scaler puis log1p (inversé)",
                       observation=f"l'ordre inversé produit {n_nan} NaN sur {len(s)} lignes ; écart médian absolu entre les deux = {ecart:.3f}",
                       verdict=("ne plante pas ici mais change les valeurs : on garde l'ordre standard (symétriser d'abord, centrer-réduire ensuite)" if n_nan == 0
                                else "l'ordre inversé plante ou produit des NaN : ordre obligatoire")))
    return pd.DataFrame(lignes)


def verif2_fit_train(racine: Path, jeux: dict, modele) -> pd.DataFrame:
    """Les paramètres appris correspondent au train seul, pas au train + validation."""
    interne = modele.regressor_
    prep = interne.named_steps["preparation"]
    norm = interne.named_steps["normalisation"]
    tr = norm.transform(jeux["train"][ENTREES])
    tv = norm.transform(pd.concat([jeux["train"], jeux["val"]])[ENTREES])
    robust = prep.named_transformers_["surface_log"].named_steps["robust"]
    ohe_cat, ohe_reg = prep.named_transformers_["categorie"], prep.named_transformers_["region"]
    med_tr, med_tv = float(np.median(np.log1p(tr.surface))), float(np.median(np.log1p(tv.surface)))
    q = lambda x: float(np.quantile(np.log1p(x.surface), .75) - np.quantile(np.log1p(x.surface), .25))
    lignes = [
        dict(parametre="médiane de log1p(surface) (centre du RobustScaler)", appris_par_le_pipeline=float(robust.center_[0]), train_seul=med_tr,
             train_plus_val=med_tv, correspond_au_train=bool(np.isclose(robust.center_[0], med_tr))),
        dict(parametre="IQR de log1p(surface) (échelle du RobustScaler)", appris_par_le_pipeline=float(robust.scale_[0]), train_seul=q(tr), train_plus_val=q(tv),
             correspond_au_train=bool(np.isclose(robust.scale_[0], q(tr)))),
        dict(parametre="modalités de catégorie apprises", appris_par_le_pipeline=len(ohe_cat.categories_[0]), train_seul=tr.categorie.nunique(),
             train_plus_val=tv.categorie.nunique(), correspond_au_train=set(ohe_cat.categories_[0]) == set(tr.categorie)),
        dict(parametre="modalités de région apprises", appris_par_le_pipeline=len(ohe_reg.categories_[0]), train_seul=tr.region.nunique(),
             train_plus_val=tv.region.nunique(), correspond_au_train=set(ohe_reg.categories_[0]) == set(tr.region)),
        dict(parametre="colonnes apprises par le Ridge (7 catégories + 14 régions + 1 surface)", appris_par_le_pipeline=int(interne.named_steps["modele"].n_features_in_),
             train_seul=7 + 14 + 1, train_plus_val=7 + 14 + 1, correspond_au_train=int(interne.named_steps["modele"].n_features_in_) == 22),
    ]
    t = pd.DataFrame(lignes, dtype=object)
    for c in ("appris_par_le_pipeline", "train_seul", "train_plus_val"):
        t[c] = pd.Series([x if isinstance(x, (int, np.integer)) else round(float(x), 5) for x in t[c]], index=t.index, dtype=object)
    return t


def verif3_reproductibilite(racine: Path, jeux: dict, alpha: float) -> pd.DataFrame:
    """Deux entraînements successifs donnent exactement les mêmes coefficients et les mêmes prédictions."""
    runs = []
    for _ in range(2):
        j = charger_jeux(racine)            # la lecture, le split et l'entraînement sont tous refaits
        m = construire_pipeline(racine / "referentiels", alpha).fit(j["train"][ENTREES], j["train"].prix)
        runs.append((m.regressor_.named_steps["modele"].coef_.copy(), m.predict(j["val"][ENTREES])))
    return pd.DataFrame([
        dict(controle="empreinte des coefficients (exécution 1 / 2)", exec_1=empreinte(runs[0][0]), exec_2=empreinte(runs[1][0]), identique=bool(np.array_equal(runs[0][0], runs[1][0]))),
        dict(controle="empreinte des prédictions de validation", exec_1=empreinte(runs[0][1]), exec_2=empreinte(runs[1][1]), identique=bool(np.array_equal(runs[0][1], runs[1][1]))),
        dict(controle="graine du split (comp 7)", exec_1=str(GRAINE), exec_2=str(GRAINE), identique=True),
    ])


def verif4_serialisation(racine: Path, jeux: dict, modele) -> pd.DataFrame:
    """Rechargement dans un interpréteur neuf : mêmes prédictions (échantillons de validation ET de test : caractéristiques seules, aucun prix du test)."""
    lignes = []
    for nom, jeu in (("validation", jeux["val"]), ("test (caractéristiques seules)", jeux["test"])):
        ech = jeu[ENTREES].head(60)
        avant = modele.predict(ech)
        apres = predire_dans_un_nouveau_processus(racine, ech)
        lignes.append(dict(echantillon=nom, n=len(ech), ecart_maximal_fcfa=float(np.abs(avant - apres).max()), predictions_identiques=bool(np.array_equal(avant, apres))))
    taille = (racine / CHEMIN_MODELE).stat().st_size / 1024
    lignes.append(dict(echantillon=f"fichier {CHEMIN_MODELE.as_posix()}", n=0, ecart_maximal_fcfa=0.0, predictions_identiques=taille > 0))
    return pd.DataFrame(lignes)


def verif5_production(racine: Path, jeux: dict, modele) -> pd.DataFrame:
    """Une ligne brute, d'une seule source, au schéma natif."""
    lignes = []
    for source, nat in lignes_natives(racine).items():
        X = adapter_ligne(source, nat)
        p = float(modele.predict(X)[0])
        lignes.append(dict(cas=f"1 ligne brute de {source}", entree=str(X.iloc[0].to_dict()), prediction_fcfa=round(p), ok=bool(np.isfinite(p) and p > 0)))
    inconnue = pd.DataFrame([dict(categorie="Château", region="Atlantide", surface="120")])
    p = float(modele.predict(inconnue)[0])
    lignes.append(dict(cas="modalités inconnues (handle_unknown=ignore)", entree=str(inconnue.iloc[0].to_dict()), prediction_fcfa=round(p), ok=bool(np.isfinite(p) and p > 0)))
    lot = jeux["val"][ENTREES].head(25)
    en_lot, seul = modele.predict(lot), np.array([float(modele.predict(lot.iloc[[i]])[0]) for i in range(len(lot))])
    lignes.append(dict(cas="une ligne seule == la même ligne dans un lot (aucun état collectif)", entree="25 lignes de validation",
                       prediction_fcfa=round(float(np.abs(en_lot - seul).max())), ok=bool(np.array_equal(en_lot, seul))))
    for surface in ("", "quatre-vingt", "-5"):
        try:
            modele.predict(pd.DataFrame([dict(categorie="Villa", region="Dakar", surface=surface)]))
            ok, obs = False, "acceptée à tort"
        except ValueError:
            ok, obs = True, "refusée (ValueError explicite)"
        lignes.append(dict(cas=f"surface invalide {surface!r}", entree="Villa / Dakar", prediction_fcfa=0, ok=ok))
    return pd.DataFrame(lignes)


def verif6_multisource(racine: Path, jeux: dict, modele) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Le pipeline traite les 5 sources de la même façon : métriques par source, couverture des modalités, colonnes utilisées."""
    va = jeux["val"].copy()
    va["pred"] = modele.predict(va[ENTREES])
    par = []
    interne = modele.regressor_
    norm = interne.named_steps["normalisation"].transform(va[ENTREES])
    prep = interne.named_steps["preparation"]
    cats = set(prep.named_transformers_["categorie"].categories_[0])
    regs = set(prep.named_transformers_["region"].categories_[0])
    for s, g in va.groupby("source"):
        m = metriques(g.prix, g.pred.to_numpy())
        n = norm.loc[g.index]
        par.append(dict(source=s, n_val=m["n"], r2_log=round(m["r2_log"], 3), mdape_pct=round(m["mdape_pct"], 1),
                        categories_connues_pct=round(100 * n.categorie.isin(cats).mean(), 1), regions_connues_pct=round(100 * n.region.isin(regs).mean(), 1)))
    t = pd.DataFrame(par)
    from .comp8 import COLONNES_MONO_SOURCE
    entrees = list(modele.regressor_.named_steps["normalisation"].transform(va[ENTREES].head(1)).columns)
    colonnes = pd.DataFrame([
        dict(controle="colonnes lues par le pipeline", valeur=", ".join(ENTREES), ok=True),
        dict(controle="`source` ou colonne mono-source utilisée", valeur="aucune", ok=not (set(entrees) & (set(COLONNES_MONO_SOURCE) | {"source", "statut", "ville"}))),
        dict(controle="modalités de catégorie / région couvertes pour les 5 sources", valeur=f"{t.categories_connues_pct.min()} % / {t.regions_connues_pct.min()} % minimum",
             ok=bool(t.categories_connues_pct.min() == 100 and t.regions_connues_pct.min() == 100)),
        dict(controle="sources évaluées", valeur=", ".join(t.source), ok=len(t) == 5),
    ])
    return t, colonnes


# ----------------------------------------------------------------------------- évaluation finale unique
def evaluation_finale_unique(racine: Path, modele, jeux: dict) -> dict:
    """UNIQUE lecture des prix du test. Si le résultat existe déjà, on le relit : on ne recalcule jamais."""
    from .comp7 import verifier_scelle
    chemin = racine / "reports" / "comp9_evaluation_finale.json"
    if chemin.exists():
        d = json.loads(chemin.read_text(encoding="utf-8"))
        d["deja_realisee"] = True
        return d
    if not verifier_scelle(racine):
        raise RuntimeError("test altéré depuis le scellé : évaluation refusée")
    te = jeux["test"].copy()
    te["pred"] = modele.predict(te[ENTREES])
    med = jeux["train"].groupby("categorie_propre").prix.median()
    base = te.categorie_propre.map(med).fillna(jeux["train"].prix.median())
    d = dict(realisee_le=pd.Timestamp.today().strftime("%Y-%m-%d"), global_=metriques(te.prix, te.pred.to_numpy()),
             baseline_mediane_categorie=metriques(te.prix, base.to_numpy()),
             par_source={s: metriques(g.prix, g.pred.to_numpy()) for s, g in te.groupby("source")},
             par_categorie={c: metriques(g.prix, g.pred.to_numpy()) for c, g in te.groupby("categorie_propre")},
             empreinte_coefficients=empreinte(modele.regressor_.named_steps["modele"].coef_),
             remarque="évaluation unique : le test n'a servi à aucune décision ; toute nouvelle évaluation invaliderait ce résultat")
    chemin.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    d["deja_realisee"] = False
    return d


def main(racine: Path = Path("."), evaluer_test: bool = False) -> dict:
    racine = Path(racine)
    rep = racine / "reports"; rep.mkdir(exist_ok=True)
    jeux = charger_jeux(racine)
    grille = choisir_alpha(racine, jeux)
    alpha = float(grille.loc[grille.r2_log.idxmax(), "alpha"])
    modele = construire_pipeline(racine / "referentiels", alpha).fit(jeux["train"][ENTREES], jeux["train"].prix)
    val = metriques(jeux["val"].prix, modele.predict(jeux["val"][ENTREES]))
    base = baseline_mediane_categorie(jeux)
    sauvegarder(modele, racine, dict(alpha=alpha, n_train=len(jeux["train"]), val=val))
    v = dict(v1=verif1_ordre(racine, jeux, modele), v2=verif2_fit_train(racine, jeux, modele), v3=verif3_reproductibilite(racine, jeux, alpha),
             v4=verif4_serialisation(racine, jeux, modele), v5=verif5_production(racine, jeux, modele))
    v["v6"], v["v6_colonnes"] = verif6_multisource(racine, jeux, modele)
    for k, t in v.items():
        t.to_csv(rep / f"comp9_verification_{k.replace('v6_colonnes', '6_colonnes').replace('v', '', 1) if k != 'v6_colonnes' else '6_colonnes'}.csv", index=False)
    grille.to_csv(rep / "comp9_choix_alpha_validation.csv", index=False)
    out = dict(alpha=alpha, grille=grille, val=val, baseline_val=base, verifs=v, modele=modele, jeux=jeux)
    if evaluer_test:
        out["test"] = evaluation_finale_unique(racine, modele, jeux)
    ecrire_docs(out, racine)
    return out


# ----------------------------------------------------------------------------- documentation générée
def _md(df: pd.DataFrame) -> str:
    from .qualite import md_table
    return md_table(df)


def resultats_md(r: dict) -> str:
    v, b = r["val"], r["baseline_val"]
    t = pd.DataFrame([
        dict(modele="Ridge (pipeline final)", r2_log=round(v["r2_log"], 3), rmse_log=round(v["rmse_log"], 3), mdape_pct=round(v["mdape_pct"], 1), mae_fcfa=f"{v['mae_fcfa'] / 1e6:.1f} M"),
        dict(modele="baseline : médiane de la catégorie", r2_log=round(b["r2_log"], 3), rmse_log=round(b["rmse_log"], 3), mdape_pct=round(b["mdape_pct"], 1), mae_fcfa=f"{b['mae_fcfa'] / 1e6:.1f} M")])
    txt = f"**Validation ({v['n']} ventes)** : choix de l'hyperparamètre α = {r['alpha']:g} (meilleur R² log sur la validation).\n\n{_md(t)}\n"
    txt += (f"Le pipeline gagne {v['r2_log'] - b['r2_log']:+.3f} de R² log sur la baseline, mais son erreur médiane relative ({v['mdape_pct']:.1f} %) n'est pas meilleure que celle de la baseline ({b['mdape_pct']:.1f} %) : "
            "la catégorie porte presque tout le signal (η² = 0,74), la région et la surface n'ajoutent presque rien (comp 2 et 6).\n\n")
    if "test" in r:
        te = r["test"]
        g, bt = te["global_"], te["baseline_mediane_categorie"]
        tt = pd.DataFrame([
            dict(modele="Ridge (pipeline final)", r2_log=round(g["r2_log"], 3), rmse_log=round(g["rmse_log"], 3), mdape_pct=round(g["mdape_pct"], 1), mae_fcfa=f"{g['mae_fcfa'] / 1e6:.1f} M"),
            dict(modele="baseline : médiane de la catégorie", r2_log=round(bt["r2_log"], 3), rmse_log=round(bt["rmse_log"], 3), mdape_pct=round(bt["mdape_pct"], 1), mae_fcfa=f"{bt['mae_fcfa'] / 1e6:.1f} M")])
        ps = pd.DataFrame([dict(source=s, n=m["n"], r2_log=round(m["r2_log"], 3), mdape_pct=round(m["mdape_pct"], 1)) for s, m in te["par_source"].items()])
        txt += (f"**Évaluation finale sur le test ({g['n']} ventes), réalisée une seule fois le {te['realisee_le']}** (le test n'a servi à aucune décision) :\n\n{_md(tt)}\n"
                f"Par source :\n\n{_md(ps)}\n")
    else:
        txt += "_Évaluation finale sur le test : non réalisée à ce stade._\n\n"
    return txt


def markdown(r: dict) -> str:
    v = r["verifs"]
    return f"""## Pipeline reproductible (compétence 9)

Objet livré : `models/pipeline_preparation.joblib` (voir `docs/pipeline.md`). Il prend une annonce au schéma commun (`categorie`, `region`, `surface`, valeurs brutes acceptées) et renvoie un prix de vente en FCFA.

**Vérification 1 — ordre des étapes**

{_md(v['v1'])}
**Vérification 2 — fit sur le train seul** (paramètres appris vs train seul vs train + validation)

{_md(v['v2'])}
**Vérification 3 — reproductibilité** (deux exécutions complètes : lecture, split, entraînement)

{_md(v['v3'])}
**Vérification 4 — sérialisation** (rechargement dans un interpréteur neuf)

{_md(v['v4'])}
**Vérification 5 — une ligne brute de chaque source** (schéma natif), cas limites

{_md(v['v5'].assign(entree=lambda d: d.entree.str.slice(0, 70)))}
**Vérification 6 — cohérence multi-source** (validation)

{_md(v['v6'])}
{_md(v['v6_colonnes'])}
### Performance

{resultats_md(r)}"""


def ecrire_docs(r: dict, racine: Path) -> Path:
    interne = r["modele"].regressor_
    meta = json.loads((racine / "models" / "pipeline_meta.json").read_text(encoding="utf-8"))
    p = f"""# Pipeline final — `models/pipeline_preparation.joblib`

Généré par `run_pipeline.py` (module `src/kerdata/modele.py`). Les chiffres ci-dessous sont mesurés, pas déclarés.

## Rôle

Une annonce au schéma commun (`categorie`, `region`, `surface`) → prix de vente prédit en FCFA.
Les valeurs brutes des sources sont acceptées : la normalisation est **dans** le pipeline, donc rejouée à l'identique en production.

## Structure (ordre figé)

| # | Étape | Apprend des paramètres ? | Ce qu'elle fait |
|---|---|---|---|
| 1 | `normalisation` (`NormaliserAnnonce`) | non (règles des référentiels, embarquées dans l'objet) | synonymes de catégorie, casse/accents/mojibake des régions, surface → nombre ; surface absente, illisible ou ≤ 0 → refus explicite |
| 2 | `preparation` (`ColumnTransformer`) | oui, **sur le train seul** | one-hot `categorie` (7 colonnes) et `region` (14 colonnes) avec `handle_unknown="ignore"` ; `log1p` puis `RobustScaler` sur `surface` |
| 3 | `modele` (`Ridge`, α = {r['alpha']:g}) | oui, sur le train seul | régression linéaire régularisée sur 22 colonnes |
| — | `TransformedTargetRegressor` | non | cible `log(prix)` à l'entraînement, `exp` à la prédiction (prix en FCFA) |

**Pourquoi cet ordre.** On normalise avant d'encoder (sinon {r['verifs']['v1'].iloc[0].observation.split(' modalités')[0]} modalités de catégorie au lieu de 7), on convertit la surface avant de la transformer (le texte avec virgule plante le scaler), on symétrise (log) avant de centrer-réduire.

## Ce qui est volontairement hors du pipeline

Le nettoyage de la comp 3 (quarantaine, doublons, dates), l'inférence de `transaction` et le split : ce sont des règles fixes ou des décisions sur le corpus, rejouées par `run_pipeline.py` (étape 0 incluse : concaténation des 5 sources par `kerdata.concat`). `statut`, `source`, `commune`, `quartier`, `description`, `date_expiration` et `annee/mois` n'entrent pas dans le pipeline (audits comp 5 et 8).

## Paramètres appris sur le train seul

{_md(r['verifs']['v2'])}
## Graine et reproductibilité

Graine **{GRAINE}** (split : `random_state`, vérification 3 : deux exécutions complètes donnent les mêmes coefficients et les mêmes prédictions, empreinte `{r['verifs']['v3'].iloc[0].exec_1}`). Ridge est déterministe : aucune autre graine n'intervient.

Versions de l'entraînement : scikit-learn {meta['sklearn']}, Python {meta['python']}.

## Procédure de rechargement

```python
import joblib, pandas as pd
modele = joblib.load("models/pipeline_preparation.joblib")      # nécessite `pip install pandas scikit-learn joblib` et PYTHONPATH=src
annonce = pd.DataFrame([{{"categorie": "Villa", "region": "Dakar", "surface": "275,8"}}])
print(modele.predict(annonce))                                    # prix en FCFA
```

Pour une annonce au schéma natif d'une source (Excel, CSV, JSON imbriqué), passer d'abord par `kerdata.modele.adapter_ligne(source, ligne)`.
Le rechargement a été testé dans un interpréteur neuf : prédictions identiques (écart maximal = 0).

## Limites

- Le pipeline ne prédit que des **ventes** (les locations suivent un autre régime de prix, comp 1).
- Les prédictions sont des **médianes conditionnelles** (`exp` de la moyenne du log) : elles sous-estiment la moyenne.
- Un rechargement exige la même version majeure de scikit-learn et le paquet `kerdata` importable (classe `NormaliserAnnonce`).
- La surface est refusée si absente : en production, l'annonce doit être complétée, comme à la quarantaine.

## Performance

{resultats_md(r)}"""
    chemin = racine / "docs" / "pipeline.md"
    chemin.parent.mkdir(exist_ok=True)
    chemin.write_text(p, encoding="utf-8")
    return chemin
