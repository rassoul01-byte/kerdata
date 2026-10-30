"""Étape 0 : concaténation des 5 sources + contrôle des volumes."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .readers import COLONNES_COMMUNES, COLONNES_EXTRA, SOURCES, read_source

# Volumes annoncés par docs/dataset_fiche_conception_dataset.md
VOLUMES_FICHE = {"plateforme": 875, "agence": 680, "particuliers": 731,
                 "notaires": 410, "historique": 528}


def concatener(dossier_sources: Path) -> pd.DataFrame:
    """Concatène les 5 sources dans le schéma commun (valeurs brutes, en texte)."""
    morceaux = [read_source(nom, dossier_sources) for nom in SOURCES]
    df = pd.concat(morceaux, ignore_index=True, sort=False)
    ordre = COLONNES_COMMUNES + COLONNES_EXTRA
    return df.reindex(columns=ordre).fillna("")


def controle_volumes(df: pd.DataFrame) -> pd.DataFrame:
    """Compare lignes lues / lignes annoncées, par source."""
    lus = df["source"].value_counts()
    t = pd.DataFrame({"attendu_fiche": pd.Series(VOLUMES_FICHE)})
    t["lu"] = lus.reindex(t.index).fillna(0).astype(int)
    t["ecart"] = t["lu"] - t["attendu_fiche"]
    t.loc["TOTAL"] = t.sum()
    return t.rename_axis("source").reset_index()


def main(racine: Path = Path(".")) -> pd.DataFrame:
    df = concatener(racine / "sources")
    (racine / "sortie").mkdir(exist_ok=True)
    (racine / "reports").mkdir(exist_ok=True)
    df.to_csv(racine / "sortie" / "corpus_brut_concatene.csv", index=False,
              encoding="utf-8")
    controle_volumes(df).to_csv(racine / "reports" / "volumes_etape0.csv",
                                index=False)
    return df


if __name__ == "__main__":
    out = main()
    print(controle_volumes(out).to_string(index=False))
