import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kerdata.modele import (ENTREES, NormaliserAnnonce, adapter_ligne, charger_jeux, construire_pipeline, lignes_natives, main)

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def r():
    return main(RACINE)                       # evaluer_test=False : le test reste intouché


@pytest.fixture(scope="module")
def norm():
    return NormaliserAnnonce.depuis_referentiels(RACINE / "referentiels")


def test_normalisation_variantes_et_mojibake(norm):
    X = pd.DataFrame({"categorie": ["VILLA", "Appt", " studio "], "region": ["thiès", "Thi\ufffds", "KÉDOUGOU"], "surface": ["150,5", 80, "40.0"]})
    o = norm.transform(X)
    assert o.categorie.tolist() == ["Villa", "Appartement", "Studio"]
    assert o.region.tolist() == ["Thiès", "Thiès", "Kédougou"] and o.surface.tolist() == [150.5, 80.0, 40.0]


@pytest.mark.parametrize("surface", ["", "quatre-vingt", "-5", "0"])
def test_surface_invalide_refusee(norm, surface):
    with pytest.raises(ValueError, match="surface"):
        norm.transform(pd.DataFrame([dict(categorie="Villa", region="Dakar", surface=surface)]))


def test_colonne_manquante_refusee(norm):
    with pytest.raises(ValueError, match="colonnes manquantes"):
        norm.transform(pd.DataFrame([dict(categorie="Villa", region="Dakar")]))


def test_jeux_tailles_et_equivalence_brut_propre(r):
    j = r["jeux"]
    assert {k: len(v) for k, v in j.items()} == {"train": 1773, "val": 380, "test": 381}
    va = j["val"]
    propre = va.rename(columns={"categorie": "x", "region": "y", "surface": "z"}).rename(
        columns={"categorie_propre": "categorie", "region_propre": "region", "surface_propre": "surface"})[ENTREES]
    assert np.allclose(r["modele"].predict(va[ENTREES]), r["modele"].predict(propre))      # brut == propre


def test_modele_predit_des_prix_positifs_en_fcfa_et_bat_la_baseline(r):
    p = r["modele"].predict(r["jeux"]["val"][ENTREES])
    assert (p > 1e6).all() and (p < 2e9).all()
    assert r["alpha"] == 1.0 and r["val"]["r2_log"] > r["baseline_val"]["r2_log"] and r["val"]["r2_log"] < 0.95


def test_verification_2_fit_sur_le_train_seul(r):
    v2 = r["verifs"]["v2"]
    assert v2.correspond_au_train.all()
    assert v2.iloc[0].appris_par_le_pipeline != pytest.approx(v2.iloc[0].train_plus_val, abs=1e-6)       # ≠ train+val


def test_verification_3_reproductibilite(r):
    assert r["verifs"]["v3"].identique.all()


def test_verification_4_serialisation_dans_un_nouveau_processus(r):
    v4 = r["verifs"]["v4"]
    assert v4.predictions_identiques.all() and (v4.ecart_maximal_fcfa == 0).all()
    assert (RACINE / "models" / "pipeline_preparation.joblib").exists() and (RACINE / "models" / "pipeline_meta.json").exists()


def test_verification_5_une_ligne_par_source_et_cas_limites(r):
    v5 = r["verifs"]["v5"]
    assert v5.ok.all() and len(v5) == 10
    assert sum(v5.cas.str.startswith("1 ligne brute")) == 5


def test_verification_6_multisource(r):
    assert r["verifs"]["v6_colonnes"].ok.all()
    v6 = r["verifs"]["v6"]
    assert len(v6) == 5 and (v6.categories_connues_pct == 100).all() and (v6.r2_log > 0.5).all()


def test_cinq_schemas_natifs_acceptes():
    for s, nat in lignes_natives(RACINE).items():
        X = adapter_ligne(s, nat)
        assert list(X.columns) == ENTREES and X.shape == (1, 3) and X.notna().all().all()


def test_seules_deux_fonctions_lisent_le_jeu_de_test():
    arbre = ast.parse((RACINE / "src" / "kerdata" / "modele.py").read_text(encoding="utf-8"))
    lecteurs = set()
    for f in [n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef)]:
        for n in ast.walk(f):
            if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value == "test" and getattr(n.value, "id", "") == "jeux":
                lecteurs.add(f.name)
    assert lecteurs == {"verif4_serialisation", "evaluation_finale_unique"}


def test_relancer_main_sans_evaluation_n_ecrase_pas_les_resultats_du_test(r):
    doc = (RACINE / "docs" / "pipeline.md").read_text(encoding="utf-8")
    if (RACINE / "reports" / "comp9_evaluation_finale.json").exists():
        assert "réalisée une seule fois" in doc and "non réalisée à ce stade" not in doc
        assert r["test"]["deja_realisee"] is True
