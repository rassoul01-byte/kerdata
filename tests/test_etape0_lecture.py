"""Tests de l'étape 0 : lecture fidèle et concaténation des 5 sources."""
from pathlib import Path

import pytest

from kerdata.concat import VOLUMES_FICHE, concatener, controle_volumes
from kerdata.readers import (COLONNES_COMMUNES, SOURCES, read_plateforme,
                                 read_source)

SRC = Path(__file__).resolve().parent.parent / "sources"


@pytest.fixture(scope="module")
def corpus():
    return concatener(SRC)


@pytest.mark.parametrize("nom,attendu", [
    ("plateforme", 875), ("agence", 640), ("particuliers", 731),
    ("notaires", 410), ("historique", 528)])
def test_volume_par_source(nom, attendu):
    assert len(read_source(nom, SRC)) == attendu


def test_plateforme_ecarte_le_header_duplique():
    df = read_plateforme(SRC / "plateforme_immo_sn.csv")
    assert not df["id"].eq("ref_plateforme").any()
    assert df["id"].str.startswith("PLT-").all()


def test_corpus_colonnes_et_sources(corpus):
    assert set(corpus["source"]) == set(SOURCES)
    assert all(c in corpus.columns for c in COLONNES_COMMUNES)
    assert len(corpus) == 3184


def test_aucune_valeur_nan_toutes_en_texte(corpus):
    assert not corpus.isna().any().any()
    assert all(corpus[c].map(type).eq(str).all() for c in corpus.columns)


def test_ecart_agence_est_le_seul_ecart_avec_la_fiche(corpus):
    t = controle_volumes(corpus).set_index("source")["ecart"]
    assert t["agence"] == -40
    assert t.drop(["agence", "TOTAL"]).eq(0).all()
    assert VOLUMES_FICHE["agence"] == 680
