"""Compétence 6 : briques de features. Tout ce qui est APPRIS (modalités, médianes, fréquences, échelles) l'est dans
`fit`, donc dans le pli d'entraînement de la validation croisée ; les colonnes dérivées ne dépendent d'aucun apprentissage.

Deux familles :
- candidates légitimes (aucune information sur le prix),
- candidates de FUITE créées volontairement pour constater le mirage (contiennent `prix`) : jamais utilisées en production.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, RobustScaler, StandardScaler

from .preprocess import ImputeurParGroupe

RACINE = Path(__file__).resolve().parents[2]


def _haversine(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


def ajouter_derivees(df: pd.DataFrame, racine: Path = RACINE) -> pd.DataFrame:
    """Colonnes dérivées sans apprentissage. Les colonnes `prix_m2_log`, `ratio_prix_fourchette`, `est_hors_fourchette`
    contiennent `prix` : elles n'existent QUE pour le test de fuite."""
    d = df.copy()
    dt = pd.to_datetime(d["date"])
    d["annee"], d["mois_sin"], d["mois_cos"] = dt.dt.year, np.sin(2 * np.pi * dt.dt.month / 12), np.cos(2 * np.pi * dt.dt.month / 12)
    geo = pd.read_csv(racine / "referentiels" / "referentiel_geographique.csv").drop_duplicates("region").set_index("region")
    dakar = geo.loc["Dakar"]
    d["distance_dakar_km"] = _haversine(dakar.lat_centre, dakar.lon_centre, d["region"].map(geo.lat_centre), d["region"].map(geo.lon_centre))
    d["statut_f"] = d["statut"].fillna("(vide)") if "statut" in d else "(vide)"
    if "prix" in d:
        cat = pd.read_csv(racine / "referentiels" / "referentiel_categories.csv").set_index("categorie")
        pmin, pmax = d["categorie"].map(cat.prix_min_indicatif), d["categorie"].map(cat.prix_max_indicatif)
        d["prix_m2_log"] = np.log(d["prix"] / d["surface"])                       # FUITE type 1
        d["ratio_prix_fourchette"] = (d["prix"] - pmin) / (pmax - pmin)           # FUITE type 1
        d["est_hors_fourchette"] = ((d["prix"] < pmin) | (d["prix"] > pmax)).astype(float)   # FUITE type 1 (dérivé de prix)
    return d


class FrequenceVille(BaseEstimator, TransformerMixin):
    """Frequency encoding : log(1 + effectif de la ville dans le pli d'entraînement). Ville inconnue -> 0."""

    def fit(self, X, y=None):
        self.freq_ = pd.DataFrame(X).iloc[:, 0].value_counts().to_dict()
        return self

    def transform(self, X):
        return np.log1p(pd.DataFrame(X).iloc[:, 0].map(self.freq_).fillna(0).to_numpy(float)).reshape(-1, 1)


class SurfaceParCategorie(BaseEstimator, TransformerMixin):
    """Interaction categorie × surface_log : une pente de surface par catégorie (Simpson : la pente globale est trompeuse)."""

    def fit(self, X, y=None):
        X = pd.DataFrame(X, columns=["categorie", "surface"])
        ls = np.log1p(X["surface"].astype(float))
        self.med_, self.iqr_ = ls.median(), (ls.quantile(.75) - ls.quantile(.25)) or 1.0
        self.cats_ = sorted(X["categorie"].unique())
        return self

    def transform(self, X):
        X = pd.DataFrame(X, columns=["categorie", "surface"])
        z = ((np.log1p(X["surface"].astype(float)) - self.med_) / self.iqr_).to_numpy()
        return np.column_stack([z * (X["categorie"] == c).to_numpy() for c in self.cats_])


class SurfaceParChambre(BaseEstimator, TransformerMixin):
    """Densité : log1p(surface / (chambres + 1)), chambres imputée par catégorie (apprise dans le pli)."""

    def fit(self, X, y=None):
        X = pd.DataFrame(X, columns=["categorie", "surface", "chambres"])
        self.imp_ = ImputeurParGroupe(colonnes=("chambres",)).fit(X)
        r = self._r(X)
        self.med_, self.iqr_ = np.median(r), (np.quantile(r, .75) - np.quantile(r, .25)) or 1.0
        return self

    def _r(self, X):
        X = self.imp_.transform(X)
        return np.log1p(X["surface"].astype(float) / (X["chambres"].astype(float) + 1)).to_numpy()

    def transform(self, X):
        return ((self._r(pd.DataFrame(X, columns=["categorie", "surface", "chambres"])) - self.med_) / self.iqr_).reshape(-1, 1)


class Pieces(BaseEstimator, TransformerMixin):
    """chambres + sdb : imputation par catégorie (pli d'entraînement) puis RobustScaler, sans indicateur de manque."""

    def fit(self, X, y=None):
        X = pd.DataFrame(X, columns=["categorie", "chambres", "sdb"])
        self.imp_ = ImputeurParGroupe().fit(X)
        self.sc_ = RobustScaler().fit(self.imp_.transform(X)[["chambres", "sdb"]].astype(float))
        return self

    def transform(self, X):
        X = self.imp_.transform(pd.DataFrame(X, columns=["categorie", "chambres", "sdb"]))
        return self.sc_.transform(X[["chambres", "sdb"]].astype(float))


def _log1p_robust():
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import FunctionTransformer
    return Pipeline([("log1p", FunctionTransformer(np.log1p)), ("robust", RobustScaler())])


def bloc(nom: str):
    """Nom de bloc -> (transformateur, colonnes). Un bloc = une candidate."""
    ohe = lambda: OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    table = {
        "categorie": (ohe(), ["categorie"]),
        "region": (ohe(), ["region"]),
        "surface_log": (_log1p_robust(), ["surface"]),
        "annee": (StandardScaler(), ["annee"]),
        "mois": ("passthrough", ["mois_sin", "mois_cos"]),
        "chambres_sdb": (Pieces(), ["categorie", "chambres", "sdb"]),
        "distance_dakar_km": (StandardScaler(), ["distance_dakar_km"]),
        "ville_frequence": (FrequenceVille(), ["ville"]),
        "surface_x_categorie": (SurfaceParCategorie(), ["categorie", "surface"]),
        "surface_par_chambre": (SurfaceParChambre(), ["categorie", "surface", "chambres"]),
        "prix_m2": (StandardScaler(), ["prix_m2_log"]),
        "ratio_prix_fourchette": (StandardScaler(), ["ratio_prix_fourchette"]),
        "est_hors_fourchette": ("passthrough", ["est_hors_fourchette"]),
        "source": (ohe(), ["source"]),
        "statut": (ohe(), ["statut_f"]),
    }
    return table[nom]


def construire_transformeur(blocs: list[str]) -> ColumnTransformer:
    return ColumnTransformer([(n, *bloc(n)) for n in blocs], remainder="drop", verbose_feature_names_out=False)
