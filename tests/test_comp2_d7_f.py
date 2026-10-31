from pathlib import Path

import pytest

from kerdata.comp1 import charger_corpus
from kerdata.comp2 import (aberrants_diagnostic, base_ventes, coherence_geographique,
                           preparer, croiser_variables)

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def d():
    return preparer(charger_corpus(RACINE))


def test_anova_categorie_explique_l_essentiel_du_prix(d):
    t = croiser_variables(d, base_ventes(d)).set_index("mesure_effet")
    assert t.loc["eta²", "effet"] == pytest.approx(0.743, abs=0.01)
    assert t.loc["eta²", "p_value"] < 0.001


def test_khi2_categorie_region_significatif_mais_effet_faible(d):
    t = croiser_variables(d, base_ventes(d)).set_index("mesure_effet")
    assert t.loc["V de Cramér", "p_value"] < 0.05
    assert t.loc["V de Cramér", "effet"] < 0.1


def test_aberrants_vs_referentiel(d):
    a = aberrants_diagnostic(d)
    assert a.prix_sous_min.sum() == 1 and a.prix_au_dessus_max.sum() == 79
    assert a.surface_sous_min.sum() == 0 and a.surface_au_dessus_max.sum() == 3


def test_coherence_geo_et_mojibake_recuperable(d):
    g = coherence_geographique(d).set_index("mesure")["valeur"]
    assert g["lignes avec accents cassés (�)"] == 208
    assert g["paires incohérentes hors mojibake"] == 4
    assert g["region : formes cassées récupérables sans ambiguïté"] == 3
    assert g["ville : formes cassées récupérables sans ambiguïté"] == 11
