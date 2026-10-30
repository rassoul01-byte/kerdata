"""Compétence 1 : types réels, statistiques descriptives, distribution de prix/surface."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from .typage import CONVERTISSEURS

TYPE_ATTENDU = {
    "id": "text", "date": "date", "transaction": "catégorie",
    "categorie": "catégorie", "region": "catégorie", "ville": "catégorie",
    "prix": "numérique ou texte", "surface": "numérique ou texte",
    "chambres": "entier (hors dictionnaire)", "sdb": "entier (hors dictionnaire)",
    "statut": "catégorie",
}
_PROPRE = {
    "prix": r"-?\d+(\.\d+)?", "surface": r"-?\d+(\.\d+)?",
    "chambres": r"\d+", "sdb": r"\d+", "date": r"\d{4}-\d{2}-\d{2}",
}


def tableau_types(df: pd.DataFrame) -> pd.DataFrame:
    """{source, champ, type attendu, type réel, écart, action} + compteurs."""
    lignes = []
    for source, g in df.groupby("source"):
        for champ, attendu in TYPE_ATTENDU.items():
            col = g[champ]
            n, vides = len(col), int((col == "").sum())
            ligne = dict(source=source, champ=champ, type_attendu=attendu, n=n,
                         n_vides=vides, n_propres=np.nan, n_convertibles=np.nan,
                         n_non_convertibles=np.nan, n_hors_regle=np.nan)
            if vides == n:
                reel, ecart, action = "absent", "colonne non fournie par la source", "à traiter en comp 3 (champ absent)"
            elif champ in CONVERTISSEURS:
                plein = col[col != ""]
                propres = int(plein.str.fullmatch(_PROPRE[champ]).sum())
                conv = plein.map(CONVERTISSEURS[champ])
                reussis = int(conv.notna().sum())
                non_conv = len(plein) - reussis
                a_convertir = reussis - propres
                ligne.update(n_propres=propres, n_convertibles=a_convertir,
                             n_non_convertibles=non_conv)
                if champ in ("prix", "surface"):
                    ligne["n_hors_regle"] = int((conv.dropna() <= 0).sum())
                reel = "numérique" if propres == len(plein) and not non_conv else "texte mixte"
                morceaux = []
                if a_convertir: morceaux.append(f"{a_convertir} à convertir (réparable)")
                if non_conv: morceaux.append(f"{non_conv} non convertibles (structurel)")
                if vides: morceaux.append(f"{vides} vides")
                hors = 0 if pd.isna(ligne["n_hors_regle"]) else int(ligne["n_hors_regle"])
                if hors: morceaux.append(f"{hors} valeurs <= 0")
                ecart = "; ".join(morceaux) or "aucun"
                if reel == "numérique" and not vides and not hors:
                    action = "type confirmé"
                elif non_conv or vides or hors:
                    action = "convertir + traiter le reste en comp 3"
                else:
                    action = "convertir (réparable)"
            else:  # catégorielles / identifiants
                brut = col[col != ""]
                norm = brut.str.strip().str.lower()
                reel = "texte"
                ecart = f"{brut.nunique()} modalités brutes -> {norm.nunique()} après casse/espaces"
                if vides: ecart += f"; {vides} vides"
                action = "type confirmé" if brut.nunique() == norm.nunique() and not vides \
                    else "normaliser/traiter en comp 3"
            ligne.update(type_reel=reel, ecart=ecart, action=action)
            lignes.append(ligne)
    cols = ["source", "champ", "type_attendu", "type_reel", "ecart", "action",
            "n", "n_vides", "n_propres", "n_convertibles", "n_non_convertibles", "n_hors_regle"]
    return pd.DataFrame(lignes)[cols]


def charger_corpus(racine: Path = Path(".")) -> pd.DataFrame:
    return pd.read_csv(racine / "sortie" / "corpus_brut_concatene.csv",
                       dtype=str, keep_default_na=False)


def main(racine: Path = Path(".")) -> None:
    df = charger_corpus(racine)
    (racine / "reports").mkdir(exist_ok=True)
    t = tableau_types(df)
    t.to_csv(racine / "reports" / "comp1_types_par_source.csv", index=False)
    return t


if __name__ == "__main__":
    t = main()
    pd.set_option("display.width", 250, "display.max_colwidth", 80)
    print(t[t.champ.isin(["prix", "surface", "date"])][["source", "champ", "type_reel", "ecart", "action"]].to_string(index=False))
