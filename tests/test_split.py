from pathlib import Path

import pandas as pd
import pytest

from kerdata.split import ENSEMBLES, GRAINE, decouper, ecart_max

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def v():
    c = pd.read_csv(RACINE / "sortie" / "corpus_conserve.csv")
    return c[c.transaction == "vente"].reset_index(drop=True)


@pytest.fixture(scope="module")
def res(v):
    return decouper(v)


def test_ratios_70_15_15(res, v):
    ens, diag = res
    assert len(ens) == len(v) == sum(diag["effectifs"].values())
    for e, r in zip(ENSEMBLES, (0.70, 0.15, 0.15)):
        assert abs(diag["effectifs"][e] / len(v) - r) < 0.01


def test_chaque_ligne_dans_un_seul_ensemble(res):
    ens, _ = res
    assert set(ens) == set(ENSEMBLES)


def test_reproductible_avec_la_meme_graine(v, res):
    ens2, _ = decouper(v, GRAINE)
    assert (res[0] == ens2).all()
    ens3, _ = decouper(v, GRAINE + 1)
    assert not (res[0] == ens3).all()


def test_stratification_categorie_a_0_5_point(res, v):
    ens, diag = res
    assert ecart_max(v, ens, "categorie") <= 0.5 + 1e-9


def test_source_ajoutee_car_ecart_initial_superieur_a_2_points(res):
    _, diag = res
    assert diag["ecart_source_premiere_passe"] > 2.0
    assert diag["strategie"] == "categorie + source" and diag["ecart_source_final"] <= 2.0


def test_aucune_source_absente_ou_sous_representee(res, v):
    ens, _ = res
    t = pd.crosstab(v.source, ens)
    assert (t.values > 0).all() and v.source.nunique() == 5
