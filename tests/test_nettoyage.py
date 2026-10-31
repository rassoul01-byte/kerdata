from pathlib import Path

import pandas as pd
import pytest

from kerdata.comp1 import charger_corpus
from kerdata.nettoyage import cle, nettoyer, normaliser_lieu, Referentiels

RACINE = Path(__file__).resolve().parent.parent
REF = RACINE / "referentiels"


@pytest.fixture(scope="module")
def res():
    return nettoyer(charger_corpus(RACINE), REF)


@pytest.fixture(scope="module")
def ref():
    return Referentiels(REF)


def test_cle_ignore_casse_accents_espaces():
    assert cle("  KÉDOUGOU ") == cle("kedougou") == "kedougou"
    assert cle("Keur  Massar") == cle("KEUR MASSAR")


@pytest.mark.parametrize("brut,attendu,regle", [
    ("Thi\ufffds", "Thiès", "mojibake"), ("ZIGUINCHOR", "Ziguinchor", "casse/accents/espaces"),
    ("touba", "Touba", "casse/accents/espaces"), ("Dakar", "Dakar", "inchangé"), ("", "", "vide"),
    ("Atlantis", "Atlantis", "inconnu")])
def test_normaliser_lieu(ref, brut, attendu, regle):
    assert normaliser_lieu(brut, ref.villes) == (attendu, regle)


def test_mojibake_ambigu_n_est_pas_corrige(ref):
    # '�' remplace une lettre : "M\ufffd" correspond à plusieurs noms potentiels -> on ne devine pas
    v, r = normaliser_lieu("\ufffd\ufffd\ufffd", ref.villes)
    assert r == "inconnu"


def test_synonyme_de_categorie(ref):
    assert ref.synonymes[cle("appart")] == "Appartement"
    assert ref.synonymes[cle("LOCAL COMMERCIAL")] == "Local commercial"


def test_chaque_ligne_dans_exactement_une_classe(res):
    d = res["d"]
    assert len(d) == 3184 and d.ligne_id.is_unique
    assert set(d.classe) <= {"propre", "avertissement", "quarantaine"}
    assert d.classe.value_counts().sum() == 3184


def test_quarantaine_regles_bloquantes(res):
    q = res["d"][res["d"].classe == "quarantaine"]
    assert q.motifs_q.ne("").all()
    assert (res["d"][res["d"].classe != "quarantaine"].prix_num > 0).all()
    assert (res["d"][res["d"].classe != "quarantaine"].surface_num > 0).all()


def test_doublons_exacts_plateforme_en_quarantaine(res):
    d = res["d"]
    dup = d[d.motifs_q.str.contains("doublon exact")]
    assert len(dup) == 15 and (dup.source == "plateforme").all()


def test_aucune_surface_negative_signalee_comme_atypique(res):
    d = res["d"]
    assert not d[(d.surface_num <= 0)].motifs_a.str.contains("surface atypique").any()


def test_mojibake_corrige_dans_regions_et_villes(res):
    d = res["d"]
    assert not d.region.str.contains("\ufffd").any() and not d.ville.str.contains("\ufffd").any()
    assert set(d.region.unique()) <= set(res["ref"].regions) | {""}


def test_transaction_inferee_tracee(res):
    d, j = res["d"], res["journal"]
    inf = d[d.transaction_origine == "inférée_par_prix"]
    assert len(j[j.champ == "transaction"]) == len(inf)
    assert inf.transaction.isin(["vente", "location"]).all()
