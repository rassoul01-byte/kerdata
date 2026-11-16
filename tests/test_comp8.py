from pathlib import Path

import pandas as pd
import pytest

from kerdata.comp8 import EspionFit, audit_fit, garde_score, main
from kerdata.comp6 import charger_train
from kerdata.features import construire_transformeur
from sklearn.pipeline import Pipeline

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def r():
    return main(RACINE)


def test_garde_score_bloque_un_r2_suspect():
    garde_score(0.75)
    with pytest.raises(ValueError, match="suspect"):
        garde_score(0.9999)


def test_features_finales_ne_revelent_pas_la_source(r):
    d = r["det"].set_index("ensemble_de_features")
    f = d.iloc[0]
    assert f.auc_macro < 0.58 and f.precision - f.precision_baseline < 0.03 and f.verdict.startswith("source indétectable")


def test_annee_mois_et_indicateurs_de_manque_revelent_la_source(r):
    d = r["det"].set_index("ensemble_de_features")
    for k in d.index:
        if k.startswith(("annee", "2 indicateurs", "indicateur chambres", "indicateur sdb")):
            assert d.loc[k, "verdict"] == "RÉVÈLE LA SOURCE", k
    assert d[d.index.str.startswith("2 indicateurs")].auc_macro.iloc[0] > 0.8


def test_manques_structurels_et_colonnes_mono_source(r):
    m = r["mq"].set_index("colonne")
    for c in ("chambres", "sdb", "statut", "quartier", "date_expiration", "pieces", "devise", "commercial"):
        assert m.loc[c, "v_cramer_manque_vs_source"] > 0.8 and m.loc[c, "indicateur_autorise"].startswith("NON")
    assert m.loc["quartier", "sources_renseignees"] == "plateforme (100 %)"
    assert m.loc["commercial", "sources_renseignees"] == "agence (100 %)"
    assert m.loc["ville", "indicateur_autorise"] == "à examiner"


def test_colonnes_mono_source_absentes_des_fichiers_de_sortie(r):
    assert (r["mono"].colonnes_mono_source_presentes == "aucune").all() and len(r["mono"]) == 4


def test_score_du_modele_final_plausible(r):
    assert (r["score"].r2_cv_train.between(0.5, 0.95)).all()


def test_le_fit_ne_voit_que_le_train_et_l_espion_detecte_une_fuite(r):
    assert r["fit"]["dont_val_ou_test"] == 0 and r["fit"]["lignes_vues_au_fit"] == r["fit"]["dont_train"] == 1773
    train = charger_train(RACINE)
    sp = pd.read_csv(RACINE / "sortie" / "split.csv")
    val_ids = set(sp[sp.ensemble == "val"].ligne_id)
    c = pd.read_csv(RACINE / "sortie" / "corpus_conserve.csv")
    val = c[c.ligne_id.isin(val_ids)]
    fuite = pd.concat([train, val.assign(distance_dakar_km=0.0)])
    pipe = Pipeline([("espion", EspionFit()), ("ct", construire_transformeur(["categorie"]))]).fit(fuite)
    assert len(set(pipe.named_steps["espion"].lignes_vues_) & val_ids) == len(val_ids) > 0     # contre-épreuve : fit global détecté


def test_tableau_audit_decisions(r):
    a = r["audit"].set_index("feature")
    for f in r["finales"]:
        assert a.loc[f, "statut"] == "OK"
    for f in ("prix_m2", "ratio_prix_fourchette", "statut", "source (one-hot)", "annee + mois", "quartier", "description", "date_expiration"):
        assert a.loc[f, "statut"].startswith("exclue")
    assert a.loc["indicateurs de manque (chambres_vide, sdb_vide)", "statut"] == "jamais créés"
    assert not any("prix" in f for f in r["finales"])
