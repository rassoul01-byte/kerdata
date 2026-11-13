import os
import shutil
from pathlib import Path

import pandas as pd
import pytest

from kerdata.pipeline import executer

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def projet(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("kerdata")
    shutil.copytree(RACINE / "sources", tmp / "sources")
    shutil.copytree(RACINE / "referentiels", tmp / "referentiels")
    res = executer(tmp, etapes_longues=False)
    return tmp, res


def lire(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def test_les_trois_fichiers_reconstituent_le_corpus(projet):
    tmp, _ = projet
    p, a, q = (lire(tmp / "sortie" / f) for f in ("donnees_propres.csv", "avertissements.csv", "quarantine.csv"))
    ids = pd.concat([p.ligne_id, a.ligne_id, q.ligne_id])
    assert len(ids) == 3184 and ids.is_unique


def test_propres_sans_valeur_bloquante(projet):
    tmp, _ = projet
    p = lire(tmp / "sortie" / "donnees_propres.csv")
    assert (p.prix.astype(float) > 0).all() and (p.surface.astype(float) > 0).all()
    assert p.date.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
    assert p.id.ne("").all()


def test_quarantaine_chaque_ligne_a_une_raison(projet):
    tmp, _ = projet
    q = lire(tmp / "sortie" / "quarantine.csv")
    assert len(q) == 201 and q.motifs_q.ne("").all()
    assert (tmp / "sortie" / "quarantaine.csv").exists()


def test_journal_reversible_avant_egal_valeur_brute(projet):
    tmp, res = projet
    j = lire(tmp / "sortie" / "journal_corrections.csv")
    brut = res["d"].set_index("ligne_id")
    reg = j[j.champ == "region"]
    assert len(reg) == 118
    assert (brut.loc[reg.ligne_id, "region_brut"].to_numpy() == reg.avant.to_numpy()).all()


def test_rapport_qualite_contient_les_6_mesures(projet):
    tmp, _ = projet
    t = (tmp / "sortie" / "rapport_qualite.md").read_text(encoding="utf-8")
    for mot in ("Les 6 mesures obligatoires", "Doublons exacts", "Erreurs de conversion", "entièrement conformes", "Limites reconnues"):
        assert mot in t


def test_agence_loyers_confirmes_par_statut(projet):
    _, res = projet
    v = res["tabs"]["validation_transaction"].set_index(["source", "transaction_inferee"])
    assert v.loc[("agence", "location"), "lignes_inferees"] == 106
    assert v.loc[("agence", "location"), "pct_confirme"] == 100.0
    assert v.loc[("agence", "vente"), "pct_confirme"] == 100.0


def test_rapport_contient_la_section_encodage_et_la_preuve(projet):
    tmp, res = projet
    t = (tmp / "sortie" / "rapport_qualite.md").read_text(encoding="utf-8")
    for mot in ("Encodage et normalisation (compétence 5)", "Preuve de non-fuite", "`statut` : exclu", "`commune` : exclue"):
        assert mot in t
    for f in ("split.csv",):
        assert (tmp / "sortie" / f).exists()
    for f in ("comp5_tableau_variables.csv", "comp5_preuve_non_fuite.csv", "comp7_split_proportions_categorie.csv"):
        assert (tmp / "reports" / f).exists()
    assert res["split"]["strategie"] == "categorie + source"


def test_pipeline_complet_avec_comp6_dans_le_rapport(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("kerdata_complet")
    shutil.copytree(RACINE / "sources", tmp / "sources")
    shutil.copytree(RACINE / "referentiels", tmp / "referentiels")
    res = executer(tmp)
    assert res["comp6"]["retenues"] == ["categorie", "region", "surface_log"]
    t = (tmp / "sortie" / "rapport_qualite.md").read_text(encoding="utf-8")
    assert "Feature engineering (compétence 6)" in t and "prix_m2 + surface_log" in t
    assert (tmp / "reports" / "dictionnaire_features.csv").exists() and (tmp / "reports" / "features_retenues.json").exists()
    assert res["comp7"]["scelle_intact"] and res["comp7"]["prerequis"].verifie.all()
    assert "Jeu de test scellé" in t and (tmp / "sortie" / "test_scelle.json").exists()
