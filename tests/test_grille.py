from pathlib import Path

import pytest

from kerdata import grille

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def t():
    return grille.verifier(RACINE)


def test_tous_les_criteres_eliminatoires_sont_verifies(t):
    elim = t[t.eliminatoire]
    assert len(elim) == 5 and elim.verifie.all(), list(elim[~elim.verifie].critere)


def test_aucun_critere_en_echec(t):
    assert t.verifie.all(), list(t[~t.verifie].critere)


def test_sources_et_referentiels_identiques_a_l_archive_d_origine(t):
    ligne = t[t.critere.str.startswith("sources/ et referentiels/")].iloc[0]
    assert ligne.verifie and "9 fichiers identiques" in ligne.preuve


def test_les_5_blocs_sont_couverts(t):
    assert {b[0] for b in t.bloc} == set("ABCDE") and len(t) >= 50


def test_document_d_auto_evaluation_genere(t):
    grille.main(RACINE)
    doc = (RACINE / "docs" / "auto_evaluation.md").read_text(encoding="utf-8")
    assert "Critères éliminatoires : **5/5**" in doc and "Ce que le code ne peut pas juger" in doc
