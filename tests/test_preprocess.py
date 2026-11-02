from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kerdata.preprocess import (COLONNES_ENTREE, ImputeurParGroupe, cible,
                                construire_preprocesseur, transformer)

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def jeux():
    c = pd.read_csv(RACINE / "sortie" / "corpus_conserve.csv")
    sp = pd.read_csv(RACINE / "sortie" / "split.csv")
    v = c[c.transaction == "vente"].merge(sp, on="ligne_id")
    return v[v.ensemble == "train"], v[v.ensemble == "val"]


@pytest.fixture(scope="module")
def pre(jeux):
    return construire_preprocesseur().fit(jeux[0][COLONNES_ENTREE])


def test_matrice_27_colonnes_sans_nan(pre, jeux):
    X = transformer(pre, jeux[1])
    assert X.shape[1] == 27 and not X.isna().any().any()
    assert X.filter(regex="^categorie_").shape[1] == 7 and X.filter(regex="^region_").shape[1] == 14


def test_colonnes_exclues_absentes(pre, jeux):
    X = transformer(pre, jeux[1])
    for interdit in ("statut", "source", "ville", "transaction", "id"):
        assert not any(interdit in c for c in X.columns)


def test_modalites_inconnues_ignorees_sans_erreur(pre, jeux):
    inc = jeux[1].head(2).copy()
    inc["categorie"], inc["region"] = ["Château", "Villa"], ["Dakar", "Atlantide"]
    X = transformer(pre, inc)
    assert X.iloc[0].filter(regex="^categorie_").sum() == 0 and X.iloc[1].filter(regex="^region_").sum() == 0


def test_imputeur_utilise_les_medianes_du_train_sans_indicateur(jeux):
    train = jeux[0]
    imp = ImputeurParGroupe().fit(train)
    manque = train.assign(chambres=np.nan, sdb=np.nan)
    out = imp.transform(manque)
    assert not out[["chambres", "sdb"]].isna().any().any()
    attendu = train.groupby("categorie").chambres.median()
    assert (out.groupby("categorie").chambres.first() == attendu).all()
    assert out.shape[1] == train.shape[1]            # aucune colonne « indicateur » ajoutée


def test_imputeur_categorie_inconnue_prend_la_mediane_globale(jeux):
    train = jeux[0]
    imp = ImputeurParGroupe().fit(train)
    x = train.head(1).assign(categorie="Château", chambres=np.nan, sdb=np.nan)
    assert imp.transform(x).chambres.iloc[0] == train.chambres.median()


def test_cible_log_prix_et_refus_des_prix_non_positifs(jeux):
    y = cible(jeux[0])
    assert np.allclose(np.exp(y), jeux[0].prix)
    with pytest.raises(AssertionError):
        cible(jeux[0].assign(prix=0))
