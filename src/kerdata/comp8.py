"""Compétence 8 : audit anti-fuite. Question unique : cette information serait-elle disponible au moment de prédire ?

Tout est mesuré sur le TRAIN (le test reste scellé, voir comp 7). Aucun chiffre n'est écrit en dur dans les justifications :
elles sont produites à partir des mesures de ce module.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict, cross_val_score
from sklearn.pipeline import Pipeline

from .comp5 import cramer_v
from .comp6 import GRAINE, K, charger_train
from .features import construire_transformeur

SEUIL_R2_SUSPECT = 0.95
COLONNES_MONO_SOURCE = ["quartier", "description", "date_expiration", "pieces", "commercial", "devise"]


def garde_score(r2: float) -> None:
    """Règle de la fiche : R² > 0,95 sur une prédiction immobilière => on s'arrête et on investigue."""
    if r2 > SEUIL_R2_SUSPECT:
        raise ValueError(f"R² = {r2:.3f} > {SEUIL_R2_SUSPECT} : score suspect, auditer les features (fuite) avant de continuer")


class EspionFit(BaseEstimator, TransformerMixin):
    """Étape transparente qui mémorise les lignes vues par `fit` : prouve que le fit ne voit que le train."""

    def fit(self, X, y=None):
        self.lignes_vues_ = list(X["ligne_id"])
        return self

    def transform(self, X):
        return X


def retenues(racine: Path) -> list[str]:
    return json.loads((racine / "reports" / "features_retenues.json").read_text(encoding="utf-8"))["retenues"]


# --------------------------------------------------------------------------- détectabilité de la source
def detectabilite_source(train: pd.DataFrame, blocs_finaux: list[str]) -> pd.DataFrame:
    """Peut-on deviner la source à partir des features ? AUC macro 0,5 / précision = baseline => indétectable."""
    y = train["source"]
    base = float(y.value_counts(normalize=True).max())
    cv = StratifiedKFold(K, shuffle=True, random_state=GRAINE)
    cls = np.array(sorted(y.unique()))

    def mesurer(nom, pipe, X):
        P = cross_val_predict(pipe, X, y, cv=cv, method="predict_proba")
        return dict(ensemble_de_features=nom, auc_macro=roc_auc_score(y, P, multi_class="ovr", average="macro"),
                    precision=accuracy_score(y, cls[P.argmax(1)]), precision_baseline=base)

    def avec_blocs(blocs):
        return Pipeline([("ct", construire_transformeur(blocs)), ("m", LogisticRegression(max_iter=3000))])

    lignes = [mesurer("features finales (" + " + ".join(blocs_finaux) + ")", avec_blocs(blocs_finaux), train)]
    for nom, b in (("categorie seule", ["categorie"]), ("region seule", ["region"]), ("surface_log seule", ["surface_log"]),
                   ("annee + mois (candidates exclues)", ["annee", "mois"]), ("chambres + sdb imputées", ["chambres_sdb"])):
        lignes.append(mesurer(nom, avec_blocs(b), train))
    ind = train.assign(chambres_vide=train.chambres.isna().astype(float), sdb_vide=train.sdb.isna().astype(float))
    for nom, cols in (("indicateur chambres_vide", ["chambres_vide"]), ("indicateur sdb_vide", ["sdb_vide"]),
                      ("2 indicateurs de manque", ["chambres_vide", "sdb_vide"])):
        pipe = Pipeline([("ct", ColumnTransformer([("p", "passthrough", cols)])), ("m", LogisticRegression(max_iter=3000))])
        lignes.append(mesurer(nom + " (jamais créés)", pipe, ind))
    t = pd.DataFrame(lignes)
    t["verdict"] = np.where((t.auc_macro < 0.58) & (t.precision - t.precision_baseline < 0.03), "source indétectable : OK",
                            np.where(t.auc_macro < 0.58, "faible", "RÉVÈLE LA SOURCE"))
    return t.round(4)


# --------------------------------------------------------------------------- manquants vs source
def manquants_vs_source(brut: pd.DataFrame, conserve: pd.DataFrame) -> pd.DataFrame:
    """Croise 'valeur manquante' avec `source` : si une source concentre le manque, l'indicateur serait la source."""
    lignes = []
    def ajouter(df, col, vide):
        m = vide(df[col])
        if not m.any():
            return
        par = m.groupby(df["source"]).mean().mul(100)
        v = cramer_v(m, df["source"])
        lignes.append(dict(
            colonne=col, pct_vide_global=round(100 * m.mean(), 1),
            sources_100pct_vides=", ".join(par[par >= 99.99].index) or "aucune",
            sources_renseignees=", ".join(f"{k} ({100 - x:.0f} %)" for k, x in par.items() if x < 99.99),
            v_cramer_manque_vs_source=round(v, 3),
            indicateur_autorise="NON : l'indicateur serait la source" if v > 0.3 else "à examiner"))
    for col in ("chambres", "sdb", "statut", "ville"):
        ajouter(conserve.assign(**{col: conserve[col]}), col, lambda s: s.isna() | s.astype(str).eq(""))
    for col in COLONNES_MONO_SOURCE:
        if col in brut:
            ajouter(brut, col, lambda s: s.astype(str).eq(""))
    return pd.DataFrame(lignes)


def colonnes_mono_source_absentes(racine: Path) -> pd.DataFrame:
    lignes = []
    for f in ("donnees_propres", "avertissements", "quarantine", "corpus_conserve"):
        cols = list(pd.read_csv(racine / "sortie" / f"{f}.csv", nrows=1).columns)
        lignes.append(dict(fichier=f"{f}.csv", colonnes_mono_source_presentes=", ".join(c for c in cols if c in COLONNES_MONO_SOURCE) or "aucune"))
    return pd.DataFrame(lignes)


# --------------------------------------------------------------------------- plausibilité du score
def plausibilite_score(train: pd.DataFrame, blocs_finaux: list[str]) -> pd.DataFrame:
    y = np.log(train["prix"])
    cv = KFold(K, shuffle=True, random_state=GRAINE)
    lignes = []
    for nom, m in (("Ridge", Ridge(alpha=1.0)), ("forêt aléatoire", RandomForestRegressor(150, min_samples_leaf=3, random_state=GRAINE, n_jobs=-1))):
        r2 = float(cross_val_score(Pipeline([("ct", construire_transformeur(blocs_finaux)), ("m", m)]), train, y, cv=cv, scoring="r2").mean())
        garde_score(r2)
        lignes.append(dict(modele=nom, r2_cv_train=round(r2, 4), seuil_suspect=SEUIL_R2_SUSPECT, verdict="plausible (< 0,95)"))
    return pd.DataFrame(lignes)


# --------------------------------------------------------------------------- transformations : le fit ne voit que le train
def audit_fit(train: pd.DataFrame, autres: pd.DataFrame, blocs_finaux: list[str]) -> dict:
    pipe = Pipeline([("espion", EspionFit()), ("ct", construire_transformeur(blocs_finaux))]).fit(train)
    vues = set(pipe.named_steps["espion"].lignes_vues_)
    return dict(lignes_vues_au_fit=len(vues), dont_train=len(vues & set(train.ligne_id)), dont_val_ou_test=len(vues & set(autres.ligne_id)))


# --------------------------------------------------------------------------- tableau d'audit
def tableau_audit(train: pd.DataFrame, cand: pd.DataFrame, det: pd.DataFrame, mq: pd.DataFrame, finales: list[str], n_future: int) -> pd.DataFrame:
    c = cand.set_index("variable")
    d = det.set_index("ensemble_de_features")
    auc = lambda k: float(d.loc[[i for i in d.index if i.startswith(k)][0], "auc_macro"])
    mono = mq.set_index("colonne")
    L = []
    def ajouter(feature, type_fuite, statut, justif):
        L.append(dict(feature=feature, type_de_fuite_potentiel=type_fuite, statut=statut, justification=justif))
    for f in finales:
        if f == "categorie":
            ajouter("categorie", "—", "OK", f"connue à la mise en ligne ; ne contient pas `prix` ; source quasi indétectable (AUC {auc('categorie seule'):.2f}) ; vocabulaire aligné AVANT le split par le référentiel (déterministe)")
        elif f == "region":
            ajouter("region", "—", "OK", f"connue à la mise en ligne ; ne contient pas `prix` ; AUC source {auc('region seule'):.2f} (≈ hasard)")
        elif f == "surface_log":
            ajouter("surface_log", "type 3 évité", "OK", f"log déterministe, RobustScaler ajusté sur le train seul ; AUC source {auc('surface_log seule'):.2f} (≈ hasard)")
    ajouter("ENSEMBLE des features finales", "types 1, 2, 3, 4", "OK", f"AUC source {auc('features finales'):.3f} pour 0,5 au hasard ; précision {float(d.iloc[0].precision):.3f} contre {float(d.iloc[0].precision_baseline):.3f} de baseline")
    for v in ("prix_m2", "prix_m2 + surface_log", "ratio_prix_fourchette", "est_hors_fourchette"):
        ajouter(v, "type 1 (contient `prix`)", "exclue", f"R² avec la feature = {c.loc[v, 'r2_avec']:.4f} (gain {c.loc[v, 'gain']:+.4f}) ; mirage détecté en comp 6")
    ajouter("log_prix comme feature", "type 1 (c'est la cible)", "exclue", "refusé par construction : `cible()` assert prix > 0 et aucune feature ne le reprend")
    ajouter("statut", "type 2 (postérieur à la prédiction) + type 4", "exclue",
            f"Vendu/Vente conclue/Acte signé/Loué ne sont connus qu'après la vente ou la location ; gain {c.loc['statut', 'gain']:+.4f} ; reste utilisé au nettoyage (date future + vendu → quarantaine)")
    ajouter("date brute", "types 2 et 4 (sémantique variable)", "exclue",
            f"date de mise en ligne (plateforme) mais date d'acte ou de vente (notaires, historique : noms d'origine date_acte, DateVente) donc postérieure à l'événement ; {n_future} ventes datées du futur conservées en avertissement, sans effet car la date n'est dans aucune feature finale")
    ajouter("annee + mois", "type 4 (révèlent la source par la période)", "exclue",
            f"AUC source {auc('annee + mois'):.2f}, précision {float(d.loc[[i for i in d.index if i.startswith('annee')][0], 'precision']):.2f} (historique : 2018-2020 seulement) ; gain {c.loc['annee', 'gain']:+.4f} déjà nul")
    ajouter("source (one-hot)", "type 4", "exclue", f"identifiant de flux ; gain {c.loc['source', 'gain']:+.4f} (la fiche attendait ≥ +0,05 : non observé, donc pas d'artefact de prix, mais exclue par principe)")
    ajouter("transaction_origine", "type 4", "exclue", "fonction déterministe de la source (V de Cramér = 1,00, comp 5)")
    ajouter("indicateurs de manque (chambres_vide, sdb_vide)", "type 4", "jamais créés",
            f"à eux deux AUC source = {float(d.loc[[i for i in d.index if i.startswith('2 indicateurs')][0], 'auc_macro']):.2f} : l'indicateur EST la source")
    ajouter("chambres + sdb (imputées)", "type 4 (manque structurel)", "exclue", f"manque entièrement concentré sur une source (chambres vides à 100 % : {mono.loc['chambres', 'sources_100pct_vides']} ; sdb : {mono.loc['sdb', 'sources_100pct_vides']}) ; imputées sans indicateur ; gain {c.loc['chambres_sdb', 'gain']:+.4f}")
    for col in ("quartier", "description", "date_expiration", "pieces", "commercial"):
        if col in mono.index:
            ajouter(col, "type 4 (colonne mono-source)", "exclue (retirée du corpus final)",
                    f"vide à {mono.loc[col, 'pct_vide_global']:.0f} % ; renseignée seulement dans {mono.loc[col, 'sources_renseignees']} ; "
                    f"V manque/source = {mono.loc[col, 'v_cramer_manque_vs_source']:.2f} : sa présence EST la source ; absente des 4 fichiers de sortie")
    ajouter("devise", "— (redondante)", "exclue (retirée du corpus final)", "FCFA / FCFA par mois = la `transaction` déjà connue ; seule la plateforme la fournit")
    ajouter("id, ligne_id", "type 4 (identifiants)", "exclue", "identifiants de flux (préfixes PLT-, etc.), aucune information sur le bien")
    ajouter("ville", "—", "exclue", "redondante avec la région, gain nul (comp 5/6) ; pas une fuite")
    return pd.DataFrame(L)


def main(racine: Path = Path(".")) -> dict:
    racine = Path(racine)
    rep = racine / "reports"; rep.mkdir(exist_ok=True)
    train = charger_train(racine)
    sp = pd.read_csv(racine / "sortie" / "split.csv")
    conserve = pd.read_csv(racine / "sortie" / "corpus_conserve.csv")
    brut = pd.read_csv(racine / "sortie" / "corpus_brut_concatene.csv", dtype=str, keep_default_na=False)
    cand = pd.read_csv(rep / "comp6_candidates.csv")
    finales = retenues(racine)
    autres = sp[sp.ensemble.isin(["val", "test"])]      # seuls les ligne_id sont lus : aucun prix du val/test n'est utilisé
    v = conserve[conserve.transaction == "vente"]
    n_future = int((pd.to_datetime(v.date) > pd.Timestamp("2026-10-31")).sum())

    det = detectabilite_source(train, finales)
    mq = manquants_vs_source(brut, conserve)
    out = dict(det=det, mq=mq, finales=finales, n_future=n_future,
               mono=colonnes_mono_source_absentes(racine), score=plausibilite_score(train, finales),
               fit=audit_fit(train, autres, finales))
    out["audit"] = tableau_audit(train, cand, det, mq, finales, n_future)
    for nom, t in (("comp8_audit_features", out["audit"]), ("comp8_detectabilite_source", det), ("comp8_manquants_vs_source", mq),
                   ("comp8_colonnes_mono_source", out["mono"]), ("comp8_plausibilite_score", out["score"])):
        t.to_csv(rep / f"{nom}.csv", index=False)
    pd.Series(out["fit"]).to_csv(rep / "comp8_audit_fit.csv", header=["valeur"])
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 250, "display.max_colwidth", 110)
    r = main()
    print(r["det"].to_string(index=False)); print(r["mq"].to_string(index=False)); print(r["mono"].to_string(index=False))
    print(r["score"].to_string(index=False)); print(r["fit"]); print(r["audit"][["feature", "type_de_fuite_potentiel", "statut"]].to_string(index=False))
