from pathlib import Path

import pandas as pd
import pytest

from kerdata.comp6 import SEUIL, charger_train, mesurer

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def res():
    train = charger_train(RACINE)
    return train, mesurer(train).set_index("variable")


def test_seul_le_train_est_lu(res):
    train, _ = res
    assert len(train) == 1773 and set(train.ensemble) == {"train"}


def test_baseline_categorie_r2_attendu(res):
    _, t = res
    assert t.loc["region", "r2_base"] == pytest.approx(0.7458, abs=0.002)


def test_mirage_prix_m2_et_surface_reconstitue_la_cible(res):
    _, t = res
    assert t.loc["prix_m2 + surface_log", "r2_avec"] > 0.99
    assert t.loc["ratio_prix_fourchette", "r2_avec"] > 0.95
    assert t.loc["prix_m2", "gain"] > 0.1
    for v in ("prix_m2", "prix_m2 + surface_log", "ratio_prix_fourchette", "est_hors_fourchette"):
        assert t.loc[v, "decision"] == "REJETÉE (fuite)"


def test_une_fuite_peut_passer_le_seuil_seul_donc_le_rejet_est_de_principe(res):
    _, t = res
    assert t.loc["est_hors_fourchette", "gain"] > SEUIL
    assert t.loc["est_hors_fourchette", "decision"] == "REJETÉE (fuite)"


def test_source_et_statut_sans_gain_et_exclus(res):
    _, t = res
    for v in ("source", "statut"):
        assert t.loc[v, "gain"] < SEUIL and t.loc[v, "decision"].startswith("EXCLUE")


def test_distance_dakar_redondante_avec_region(res):
    _, t = res
    assert abs(t.loc["distance_dakar_km", "gain"]) < 1e-3 and t.loc["distance_dakar_km", "decision"] == "EXCLUE (redondante)"


def test_surface_gardee_par_regle_mais_alerte_foret(res):
    _, t = res
    assert t.loc["surface_log", "decision"].startswith("GARDER (neutre")
    assert t.loc["surface_log", "gain_foret"] < -SEUIL and "ALERTE" in t.loc["surface_log", "justification"]
    assert t.loc["surface_log", "r2_seul"] > 0.1            # R² seul trompeur (composition), gain nul


def test_decisions_finales_alignees_sur_la_fiche(res):
    _, t = res
    gardees = t[t.decision.str.startswith("GARDER")].index.tolist()
    assert gardees == ["region", "surface_log"]
    for v in ("annee", "mois", "chambres_sdb", "ville_frequence", "surface_x_categorie", "surface_par_chambre"):
        assert t.loc[v, "decision"].startswith("EXCLURE")
