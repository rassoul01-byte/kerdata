from pathlib import Path

import numpy as np
import pytest

from kerdata.comp1 import SEUIL_LOYER_VENTE, ajouter_numeriques, prix_vs_log
from kerdata.concat import concatener

SRC = Path(__file__).resolve().parent.parent / "sources"


@pytest.fixture(scope="module")
def d():
    return ajouter_numeriques(concatener(SRC))


def test_seuil_loyer_vente_sans_erreur_sur_transactions_connues(d):
    connu = d[(d.segment_origine == "connue") & (d.prix_num > 0)]
    predit = np.where(connu.prix_num < SEUIL_LOYER_VENTE, "location", "vente")
    assert (predit == connu.transaction).all()


def test_aucun_prix_dans_la_zone_grise(d):
    assert not d.prix_num.between(1_800_000, 5_100_000).any()


def test_prix_negatifs_ou_vides_ont_segment_inconnu(d):
    sans_prix = d[~(d.prix_num > 0) & (d.segment_origine != "connue")]
    assert (sans_prix.segment == "inconnu").all()
    assert sans_prix.groupby("source").size().to_dict() == {"agence": 5, "historique": 10, "notaires": 14}


def test_skew_prix_vs_log_sur_les_ventes(d):
    r = prix_vs_log(d).set_index("population").loc["segment vente"]
    assert r.skew_brut == pytest.approx(1.864, abs=0.01)
    assert abs(r.skew_log) < 0.5 < 1 < r.skew_brut


def test_melange_ventes_locations_degrade_le_skew_du_log(d):
    r = prix_vs_log(d).set_index("population")
    assert r.loc["global (ventes+locations mélangées)", "skew_log"] < -1
