from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kerdata.comp1 import charger_corpus
from kerdata.comp2 import (base_ventes, mann_kendall, preparer, preparer_temps,
                           tendance_robustesse)

RACINE = Path(__file__).resolve().parent.parent


def test_mann_kendall_detecte_une_tendance_croissante():
    r = mann_kendall(pd.Series(np.arange(20) + np.random.default_rng(0).normal(0, .1, 20)))
    assert r["tau"] > 0.9 and r["p_value"] < 0.001 and r["pente_sen"] > 0.8


def test_mann_kendall_serie_aleatoire_non_significative():
    r = mann_kendall(pd.Series(np.random.default_rng(1).normal(size=60)))
    assert r["p_value"] > 0.05


def test_pas_de_tendance_sur_les_ventes_a_toutes_les_echelles():
    t = preparer_temps(base_ventes(preparer(charger_corpus(RACINE))))
    assert len(t) == 2597
    r = tendance_robustesse(t)
    assert len(r) == 4 and not r.tendance_significative_5pct.any()
    assert t.mois.nunique() == 96
