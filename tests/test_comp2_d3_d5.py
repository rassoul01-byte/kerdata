from pathlib import Path

import pytest

from kerdata.comp1 import charger_corpus
from kerdata.comp2 import (base_ventes, correlations_prix_surface, preparer,
                           prix_par_categorie, vif)

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def v():
    return base_ventes(preparer(charger_corpus(RACINE)))


def test_base_ventes_n(v):
    assert len(v) == 2608 and (v.prix_num > 0).all() and (v.segment == "vente").all()


def test_simpson_actif_global_vs_categories(v):
    c = correlations_prix_surface(v).set_index(["niveau", "groupe"])
    assert c.loc[("global", "toutes catégories"), "spearman"] > 0.4
    par_cat = c.xs("catégorie", level="niveau").dropna(subset=["spearman"])
    assert len(par_cat) == 7
    assert (par_cat.spearman.abs() < 0.2).all()
    assert (par_cat.p_spearman > 0.05).all()


def test_pearson_spearman_divergent_au_global(v):
    g = correlations_prix_surface(v).set_index("niveau").loc["global"]
    assert g.pearson < 0.1 < 0.4 < g.spearman


def test_vif_numeriques_non_redondantes(v):
    assert (vif(v).vif < 1.1).all()


def test_prix_par_categorie_dispersion(v):
    t = prix_par_categorie(v).set_index("categorie")
    assert t.loc["villa", "mediane"] > 10 * t.loc["chambre", "mediane"]
    assert t.loc["local commercial", "cv"] > t.loc["chambre", "cv"]
