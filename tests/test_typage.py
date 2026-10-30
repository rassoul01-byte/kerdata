import numpy as np
import pandas as pd
import pytest

from kerdata.typage import parse_date, parse_entier, parse_prix, parse_surface


@pytest.mark.parametrize("brut,attendu", [
    ("65575000", 65575000), ("26 620 000", 26620000), ("65575000 FCFA", 65575000),
    ("147.52 millions", 147520000), ("12,500,000", 12500000), ("395000000.0", 395000000)])
def test_prix_convertibles(brut, attendu):
    assert parse_prix(brut) == pytest.approx(attendu)


@pytest.mark.parametrize("brut", ["", "N/A", "None FCFA", "à négocier"])
def test_prix_non_convertibles(brut):
    assert np.isnan(parse_prix(brut))


def test_surface_virgule_decimale_et_mots():
    assert parse_surface("367,4") == pytest.approx(367.4)
    assert np.isnan(parse_surface("quatre-vingt"))
    assert np.isnan(parse_surface(""))


def test_date_formats_et_impossible():
    assert parse_date("2023-12-16") == pd.Timestamp("2023-12-16")
    assert parse_date("02/12/2023") == pd.Timestamp("2023-12-02")
    assert pd.isna(parse_date("32/13/2024"))


def test_entier():
    assert parse_entier("3") == 3 and np.isnan(parse_entier(""))
