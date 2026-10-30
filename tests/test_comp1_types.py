from pathlib import Path

import pytest

from kerdata.comp1 import tableau_types
from kerdata.concat import concatener

SRC = Path(__file__).resolve().parent.parent / "sources"


@pytest.fixture(scope="module")
def types():
    return tableau_types(concatener(SRC)).set_index(["source", "champ"])


def test_plateforme_prix_chiffres(types):
    r = types.loc[("plateforme", "prix")]
    assert (r.n_convertibles, r.n_non_convertibles, r.n_vides) == (65, 6, 0)


def test_particuliers_surface_mots_et_vides(types):
    r = types.loc[("particuliers", "surface")]
    assert (r.n_non_convertibles, r.n_vides) == (4, 75)


def test_agence_valeurs_hors_regle(types):
    assert types.loc[("agence", "prix")].n_hors_regle == 5
    assert types.loc[("agence", "surface")].n_hors_regle == 4


def test_notaires_dates_impossibles(types):
    assert types.loc[("notaires", "date")].n_non_convertibles == 6


def test_colonnes_absentes_detectees(types):
    assert types.loc[("plateforme", "chambres")].type_reel == "absent"
    assert types.loc[("notaires", "sdb")].type_reel == "absent"
