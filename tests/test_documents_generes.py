import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
# {x['cle']}, {v.attr}, {r["cle"]} : un placeholder f-string resté tel quel (dict littéral {'a': 1} exclu)
PLACEHOLDER = re.compile(r"""\{[A-Za-z_][\w\.]*\[['"]|\{[A-Za-z_]\w*\.\w+[:}]|\{[a-z_]\w*:\.\d""")


def test_aucun_placeholder_non_rempli_dans_les_documents_generes():
    fichiers = [RACINE / "sortie" / "rapport_qualite.md", RACINE / "reports" / "comp4_visualisations.md",
                RACINE / "docs" / "pipeline.md"] + list((RACINE / "docs").glob("rapport_final.md"))
    for f in fichiers:
        if f.exists():
            trouves = PLACEHOLDER.findall(f.read_text(encoding="utf-8"))
            assert not trouves, f"{f.name} : placeholder non rempli {trouves[:3]}"
