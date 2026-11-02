import shutil
from pathlib import Path

import pytest

from kerdata.pipeline import executer

RACINE = Path(__file__).resolve().parent.parent
FIGURES = ["v1_distribution_cible", "v2_prix_par_categorie", "v3_simpson_donnees_propres",
           "v4_matrice_correlation", "v5_preuve_nettoyage", "v6_comparaison_sources"]


@pytest.fixture(scope="module")
def projet(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("kerdata_viz")
    shutil.copytree(RACINE / "sources", tmp / "sources")
    shutil.copytree(RACINE / "referentiels", tmp / "referentiels")
    return tmp, executer(tmp)["restitution"]


def test_six_figures_sauvegardees(projet):
    tmp, _ = projet
    for nom in FIGURES:
        f = tmp / "reports" / "figures" / f"{nom}.png"
        assert f.exists() and f.stat().st_size > 10_000


def test_v1_cible_log_reduit_le_skew(projet):
    _, c = projet
    assert c["v1"]["skew_brut"] > 1 and abs(c["v1"]["skew_log"]) < 0.5
    assert c["v1"]["n"] == 2534


def test_v2_ratio_categories(projet):
    _, c = projet
    assert c["v2"]["max"] == "Villa" and c["v2"]["min"] == "Chambre"
    assert c["v2"]["ratio"] == pytest.approx(22.7, abs=0.2)
    assert c["v2"]["eta2"] > 0.7


def test_v3_simpson_actif(projet):
    _, c = projet
    assert c["v3"]["r_global"] > 0.4 and abs(c["v3"]["r_moyen"]) < 0.1 and c["v3"]["r_max_abs"] < 0.2


def test_v4_aucune_paire_redondante(projet):
    _, c = projet
    assert c["v4"]["paires"] == [] and c["v4"]["max_hors_diag"] < 0.8


def test_v5_apres_relu_depuis_les_fichiers_livres(projet):
    _, c = projet
    t = c["tab5"].set_index("Indicateur")["Après"]
    for ind in ("Prix absents, illisibles ou <= 0", "Surfaces absentes, illisibles ou <= 0", "Dates non ISO ou impossibles",
                "Lignes avec accents cassés (�)", "Catégories hors vocabulaire", "Statuts non harmonisés",
                "Doublons exacts (même id, même source)"):
        assert t[ind] == "0"
    assert c["v5"]["avant"] == pytest.approx(50.7, abs=0.1) and c["v5"]["apres"] == pytest.approx(90.2, abs=0.1)


def test_v6_sources_alignees_apres_categorie(projet):
    _, c = projet
    assert c["v6"]["kruskal_prix"] > 0.05 and c["v6"]["kruskal_surface"] > 0.05
    assert c["v6"]["chi2_compo"] < 1e-10


def test_rapport_qualite_contient_la_section_visualisations(projet):
    tmp, _ = projet
    t = (tmp / "sortie" / "rapport_qualite.md").read_text(encoding="utf-8")
    assert "Visualisations de restitution" in t and t.count("**Conclusion V") == 6
    assert (tmp / "reports" / "comp4_visualisations.md").exists()
