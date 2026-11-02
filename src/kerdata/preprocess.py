"""Compétence 5 : préprocesseur sklearn. Aucun paramètre n'est appris hors du train (fit sur train, transform ailleurs).

Entrées utilisées : categorie, region, surface, chambres, sdb, date.
Exclues par audit (voir docs/justifications.md 5.1 à 5.5) : statut, source, ville, transaction, transaction_origine, identifiants.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, RobustScaler, StandardScaler

COLONNES_ENTREE = ["categorie", "region", "surface", "chambres", "sdb", "date"]
CAT = ["categorie", "region"]


def cible(df: pd.DataFrame) -> pd.Series:
    """y = log(prix). Le log exige prix > 0 (garanti par la quarantaine de la comp 3)."""
    assert (df["prix"] > 0).all(), "log(prix) impossible : prix <= 0"
    return np.log(df["prix"]).rename("log_prix")


class ImputeurParGroupe(BaseEstimator, TransformerMixin):
    """Médiane par catégorie, apprise sur le train. Catégorie inconnue -> médiane globale du train.
    Volontairement SANS indicateur de manque : le manque est structurel (lié à la source), l'indicateur la révélerait."""

    def __init__(self, groupe: str = "categorie", colonnes=("chambres", "sdb")):
        self.groupe = groupe
        self.colonnes = colonnes

    def fit(self, X: pd.DataFrame, y=None):
        self.medianes_ = {c: X.groupby(self.groupe)[c].median().to_dict() for c in self.colonnes}
        self.globale_ = {c: float(X[c].median()) for c in self.colonnes}
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        X = X.copy()
        for c in self.colonnes:
            valeurs = X[self.groupe].map(self.medianes_[c])
            valeurs = valeurs.where(valeurs.notna(), self.globale_[c])    # catégorie jamais vue au fit
            X[c] = X[c].astype(float).where(X[c].notna(), valeurs)
        return X

    def get_feature_names_out(self, names=None):
        return np.array(list(names) if names is not None else [])


class ExtraireDate(BaseEstimator, TransformerMixin):
    """date -> annee, mois_sin, mois_cos (mois cyclique : décembre est proche de janvier)."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        d = pd.to_datetime(pd.DataFrame(X).iloc[:, 0])
        m = d.dt.month
        return np.column_stack([d.dt.year, np.sin(2 * np.pi * m / 12), np.cos(2 * np.pi * m / 12)])

    def get_feature_names_out(self, names=None):
        return np.array(["annee", "mois_sin", "mois_cos"])


def construire_preprocesseur() -> Pipeline:
    ct = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT),
            ("surface", Pipeline([("log1p", FunctionTransformer(np.log1p, feature_names_out=lambda _, n: ["surface_log"])),
                                  ("robust", RobustScaler())]), ["surface"]),
            ("pieces", RobustScaler(), ["chambres", "sdb"]),
            ("annee", Pipeline([("extraire", ExtraireDate()), ("scaler", ColumnTransformer(
                [("std", StandardScaler(), [0]), ("cyc", "passthrough", [1, 2])]))]), ["date"]),
        ],
        remainder="drop", verbose_feature_names_out=False,
    )
    return Pipeline([("imputer", ImputeurParGroupe()), ("ct", ct)])


def noms_features(pre: Pipeline) -> list[str]:
    ct = pre.named_steps["ct"]
    noms: list[str] = []
    for nom, trans, cols in ct.transformers_:
        if nom == "cat":
            noms += list(trans.get_feature_names_out(cols))
        elif nom == "surface":
            noms += ["surface_log"]
        elif nom == "pieces":
            noms += ["chambres", "sdb"]
        elif nom == "annee":
            noms += ["annee", "mois_sin", "mois_cos"]
    return noms


def transformer(pre: Pipeline, df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(pre.transform(df[COLONNES_ENTREE]), columns=noms_features(pre), index=df.index)
