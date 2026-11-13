import re
from pathlib import Path

import pandas as pd
import pytest

from kerdata import comp7

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def r():
    return comp7.main(RACINE)


def test_tableau_ensembles(r):
    t = r["ensembles"].set_index("ensemble")
    assert t["count"].to_dict() == {"train": 1773, "val": 380, "test": 381}
    assert abs(t.loc["train", "pourcentage"] - 70) < 0.1 and abs(t.loc["val", "pourcentage"] - 15) < 0.1


def test_prerequis_tous_verifies(r):
    assert r["prerequis"].verifie.all() and len(r["prerequis"]) == 6


def test_aucun_identifiant_partage_entre_ensembles(r):
    assert (r["ids"].nombre == r["ids"].attendu).all()


def test_preuve_strategie_aleatoire_sans_dates_futures(r):
    s = r["strategie"]
    assert (s.p_value > 0.05).all() and (s.decision == "pas de tendance → split aléatoire").all()
    assert s.loc[s.echelle == "annuelle", "n_points"].iloc[0] == 8        # 2018-2025, la date de 2028 est exclue
    assert r["periodes"].set_index("source").loc["historique", "fin"].year == 2020


def test_chaque_categorie_est_presente_dans_chaque_ensemble(r):
    assert (r["eff_cat"].values >= 20).all()


def test_scelle_intact_et_falsification_detectee(r):
    assert r["scelle_intact"] is True
    _, v = comp7.charger(RACINE)
    ref = comp7.empreinte_test(v)
    modif = v.copy(); i = modif.index[modif.ensemble == "test"][0]; modif.loc[i, "prix"] += 1
    assert comp7.empreinte_test(modif)["sha256_contenu"] != ref["sha256_contenu"]
    deplace = v.copy(); deplace.loc[deplace.index[deplace.ensemble == "train"][0], "ensemble"] = "test"
    assert comp7.empreinte_test(deplace)["sha256_ligne_ids"] != ref["sha256_ligne_ids"]


def test_aucun_module_hors_split_et_comp7_ne_lit_le_test():
    interdit = re.compile(r"""ensemble\s*==\s*["']test["']""")
    for f in (RACINE / "src" / "kerdata").glob("*.py"):
        if f.name in {"split.py", "comp7.py"}:
            continue
        assert not interdit.search(f.read_text(encoding="utf-8")), f"{f.name} lit le jeu de test"
