from pathlib import Path

import pandas as pd
import pytest

from kerdata.comp1 import charger_corpus  # noqa: F401
from kerdata.comp2 import (doublons_inter_sources, manquants, preparer,
                           qualite_par_source, vue_ensemble)
from kerdata.concat import concatener

SRC = Path(__file__).resolve().parent.parent / "sources"


@pytest.fixture(scope="module")
def d():
    return preparer(concatener(SRC))


def test_plateforme_doublons_exacts_et_dates_futures(d):
    v = vue_ensemble(d).set_index("source")
    assert v.loc["plateforme", "doublons_exacts"] == 15
    assert v.loc["plateforme", "doublons_id"] == 15
    assert v.loc["plateforme", "dates_futures"] == 5
    assert v.drop("plateforme").doublons_exacts.sum() == 0


def test_periodes_par_source(d):
    v = vue_ensemble(d).set_index("source")
    assert str(v.loc["historique", "date_max"]) == "2020-01-01"
    assert str(v.loc["plateforme", "date_max"]) == "2028-12-01"


def test_manquants_structurels(d):
    m = manquants(d).set_index(["source", "champ"])
    assert m.loc[("notaires", "sdb"), "mecanisme"].startswith("structurel")
    assert m.loc[("plateforme", "chambres"), "mecanisme"].startswith("structurel")
    assert m.loc[("historique", "statut"), "mecanisme"].startswith("structurel")


def test_manquants_prix_pas_de_circularite_avec_segment(d):
    m = manquants(d).set_index(["source", "champ"])
    assert m.loc[("notaires", "prix"), "variable_dependante"] != "segment"
    assert m.loc[("historique", "prix"), "variable_dependante"] != "segment"
    assert m.loc[("notaires", "prix"), "vides"] == 14


def test_qualite_par_source(d):
    q = qualite_par_source(d).set_index("source")
    assert q.loc["particuliers", "pct_manquants_surface"] == 10.3
    assert q.loc["notaires", "dates_non_interpretables"] == 6
    assert q.loc["plateforme", "doublons_id"] == 15


def test_aucun_doublon_probable_inter_sources_sur_cle_stricte(d):
    assert len(doublons_inter_sources(d)) == 0
