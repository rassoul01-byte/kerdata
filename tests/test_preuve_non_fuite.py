from pathlib import Path

import pandas as pd
import pytest

from kerdata.comp5 import preuve_non_fuite

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def p():
    return preuve_non_fuite(pd.read_csv(RACINE / "sortie" / "corpus_conserve.csv"), pd.read_csv(RACINE / "sortie" / "split.csv"))


def ligne(p, ajust, var):
    return p[(p.ajustement.str.startswith(ajust)) & (p.variable == var)].iloc[0]


def test_fit_train_annee_centree_sur_train_pas_sur_val(p):
    r = ligne(p, "fit sur train (", "annee")
    assert abs(r.moyenne_train) < 1e-9 and abs(r.moyenne_val) > 1e-4


def test_fit_train_surface_mediane_nulle_sur_train_pas_sur_val(p):
    r = ligne(p, "fit sur train (", "surface_log")
    assert abs(r.mediane_train) < 1e-9 and abs(r.mediane_val) > 1e-3


def test_signature_de_fuite_si_fit_sur_validation(p):
    assert abs(ligne(p, "fit sur validation", "annee").moyenne_val) < 1e-9
    assert abs(ligne(p, "fit sur validation", "surface_log").mediane_val) < 1e-9


def test_fit_global_ne_centre_ni_train_ni_val(p):
    r = ligne(p, "fit sur train+val", "annee")
    assert abs(r.moyenne_train) > 1e-4 and abs(r.moyenne_val) > 1e-4
