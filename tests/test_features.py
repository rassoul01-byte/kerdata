from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kerdata.features import (FrequenceVille, Pieces, SurfaceParCategorie, SurfaceParChambre, ajouter_derivees,
                              construire_transformeur)

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def train():
    c = pd.read_csv(RACINE / "sortie" / "corpus_conserve.csv")
    sp = pd.read_csv(RACINE / "sortie" / "split.csv")
    v = c[c.transaction == "vente"].merge(sp, on="ligne_id")
    return ajouter_derivees(v[v.ensemble == "train"])


def test_distance_dakar_est_une_fonction_exacte_de_la_region(train):
    assert train.groupby("region").distance_dakar_km.nunique().max() == 1
    assert train.region.nunique() == train.distance_dakar_km.round(6).nunique()
    assert train[train.region == "Dakar"].distance_dakar_km.max() == pytest.approx(0, abs=1e-6)
    assert 230 < train[train.region == "Ziguinchor"].distance_dakar_km.iloc[0] < 300


def test_colonnes_de_fuite_presentes_seulement_si_prix_fourni(train):
    assert {"prix_m2_log", "ratio_prix_fourchette", "est_hors_fourchette"} <= set(train.columns)
    fuites = ["prix", "prix_m2_log", "ratio_prix_fourchette", "est_hors_fourchette"]
    prod = ajouter_derivees(train.drop(columns=fuites))          # comme en production : le prix n'existe pas
    assert not {"prix_m2_log", "ratio_prix_fourchette", "est_hors_fourchette"} & set(prod.columns)


def test_frequence_ville_inconnue_vaut_zero():
    f = FrequenceVille().fit(pd.DataFrame({"ville": ["a", "a", "b"]}))
    assert f.transform(pd.DataFrame({"ville": ["a", "b", "zzz"]})).ravel().tolist() == pytest.approx([np.log1p(2), np.log1p(1), 0.0])


def test_interaction_une_colonne_par_categorie_nulle_hors_categorie():
    X = pd.DataFrame({"categorie": ["A", "B", "A"], "surface": [50.0, 80.0, 120.0]})
    t = SurfaceParCategorie().fit(X).transform(X)
    assert t.shape == (3, 2) and t[0, 1] == 0 and t[1, 0] == 0 and t[0, 0] != 0


def test_densite_et_pieces_sans_nan_malgre_chambres_manquantes(train):
    sub = train[["categorie", "surface", "chambres", "sdb"]].copy()
    assert sub.chambres.isna().any()
    assert not np.isnan(SurfaceParChambre().fit(sub[["categorie", "surface", "chambres"]]).transform(sub[["categorie", "surface", "chambres"]])).any()
    assert not np.isnan(Pieces().fit(sub[["categorie", "chambres", "sdb"]]).transform(sub[["categorie", "chambres", "sdb"]])).any()


def test_construire_transformeur_dimensions(train):
    t = construire_transformeur(["categorie", "region"]).fit(train)
    assert t.transform(train).shape == (len(train), 7 + 14)
    t2 = construire_transformeur(["categorie", "surface_log", "mois", "surface_x_categorie"]).fit(train)
    assert t2.transform(train).shape[1] == 7 + 1 + 2 + 7
