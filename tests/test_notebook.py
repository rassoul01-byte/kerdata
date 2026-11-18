from pathlib import Path

import nbformat

RACINE = Path(__file__).resolve().parent.parent
NB = RACINE / "notebooks" / "02_preparation_analyse.ipynb"


def test_notebook_livre_avec_ses_sorties_et_sans_erreur():
    nb = nbformat.read(NB, as_version=4)
    code = [c for c in nb.cells if c.cell_type == "code"]
    assert len(code) >= 12
    assert all(c.execution_count is not None for c in code), "cellule non exécutée"
    assert not [o for c in code for o in c.outputs if o.output_type == "error"]


def test_notebook_contient_les_resultats_cles():
    nb = nbformat.read(NB, as_version=4)
    texte = "\n".join(o.get("text", "") for c in nb.cells if c.cell_type == "code" for o in c.outputs if o.output_type == "stream")
    assert "3184 lignes lues -> 2872 propres | 111 avertissements | 201 en quarantaine" in texte
    images = sum(1 for c in nb.cells if c.cell_type == "code" for o in c.outputs if "image/png" in o.get("data", {}))
    assert images >= 8                       # figures de restitution V1-V6 et diagnostics


def test_notebook_couvre_les_9_competences():
    nb = nbformat.read(NB, as_version=4)
    titres = " ".join(c.source for c in nb.cells if c.cell_type == "markdown")
    for mot in ("compétence 1", "compétence 2", "compétence 3", "compétence 4", "compétences 5 à 7", "compétence 8", "compétence 9", "Conclusion"):
        assert mot in titres
