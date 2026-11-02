from pathlib import Path

import pandas as pd
import pytest

from kerdata.comp5 import auditer, eta2, cramer_v

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def a():
    return auditer(pd.read_csv(RACINE / "sortie" / "corpus_conserve.csv"))


def test_statut_proxy_de_la_source_sans_signal_prix(a):
    s = a["statut"]
    assert s["v_source_statut"] > 0.5
    assert s["eta2"] < 0.01 and s["p_anova"] > 0.05
    assert s["pct_vide_par_source"]["historique"] == 100.0


def test_source_sans_signal_sur_le_prix_relatif(a):
    assert a["source"]["eta2_prix_std"] < 0.005 and a["source"]["p_anova"] > 0.05


def test_commune_aucune_ville_rare_et_gain_negligeable(a):
    c = a["cr"]
    assert c["n_villes"] == 46 and c["n_villes_moins_10"] == 0
    # 1 seule exception : Dakar rattachée à Ziguinchor sur les 4 lignes incohérentes signalées en comp 3
    assert c["villes_multi_regions"] == 1
    assert c["gain_ville_vs_region"] < 0.01 and c["omega2_region"] > 0.02


def test_surface_log1p_symetrise(a):
    assert a["num"]["skew_surface"] > 1 and abs(a["num"]["skew_log1p_surface"]) < 0.2
    assert a["num"]["prix_min"] > 0


def test_tableau_decisions(a):
    t = a["tableau"].set_index("variable")
    assert t.loc["statut", "encodage_ou_scaler"].startswith("EXCLUE")
    assert t.loc["source", "encodage_ou_scaler"].startswith("EXCLUE")
    assert t.loc["categorie", "encodage_ou_scaler"].startswith("one-hot")
    assert len(t) == 13


def test_eta2_et_cramer_cas_connus():
    df = pd.DataFrame({"g": ["a"] * 50 + ["b"] * 50, "y": [0.0] * 50 + [1.0] * 50})
    e, w, p = eta2(df, "g", "y")
    assert e == pytest.approx(1.0) and cramer_v(df.g, df.y) == pytest.approx(1.0)
