"""Lecteurs des 5 sources brutes ImmoAnalyse.

Principe (étape 0) : LECTURE FIDÈLE. Aucune correction de valeur ici.
- toutes les valeurs sont lues comme du texte (pas d'inférence de type),
- une valeur absente est représentée par la chaîne vide '',
- seuls les NOMS de colonnes sont harmonisés vers un schéma commun,
- les fichiers de `sources/` ne sont jamais modifiés.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

SOURCES = ("agence", "historique", "notaires", "particuliers", "plateforme")

# Colonnes du schéma commun (toutes en texte). Les colonnes propres à une
# seule source sont conservées (NaN -> '' après concaténation).
COLONNES_COMMUNES = [
    "source", "id", "date", "transaction", "categorie", "region", "ville",
    "prix", "surface", "chambres", "sdb", "statut",
]
COLONNES_EXTRA = ["quartier", "devise", "pieces", "description",
                  "date_expiration", "commercial"]

# Renommages source -> schéma commun.
# NB : `pieces` (plateforme) n'est PAS mappé sur `chambres` : pièces != chambres.
MAPPING = {
    "agence": {
        "Code": "id", "Date": "date", "Region": "region", "Ville": "ville",
        "Type": "categorie", "Prix_FCFA": "prix", "Surface_m2": "surface",
        "Chambres": "chambres", "SDB": "sdb", "Statut": "statut",
        "Commercial": "commercial",
    },
    "historique": {
        "ID": "id", "DateVente": "date", "Region": "region", "Ville": "ville",
        "TypeBien": "categorie", "Prix": "prix", "Surface": "surface",
        "Chambres": "chambres", "SallesBain": "sdb",
    },
    "notaires": {
        "id_acte": "id", "date_acte": "date", "region": "region",
        "ville": "ville", "type_bien": "categorie", "montant_fcfa": "prix",
        "superficie": "surface", "nb_chambres": "chambres", "statut": "statut",
    },
    "plateforme": {
        "ref_plateforme": "id", "date_mise_en_ligne": "date",
        "type_transaction": "transaction", "commune": "ville",
    },
}

PLATEFORME_COLONNES = [
    "ref_plateforme", "date_mise_en_ligne", "type_transaction", "categorie",
    "region", "commune", "quartier", "prix", "devise", "surface", "pieces",
    "sdb", "description", "statut", "date_expiration",
]


def _en_texte(df: pd.DataFrame) -> pd.DataFrame:
    """Tout en texte, absent -> ''."""
    return df.astype(str).where(df.notna(), "").replace({"None": "", "nan": ""})


def read_agence(chemin: Path) -> pd.DataFrame:
    """Excel, feuille `Annonces` (la feuille `Params` n'est que de la métadonnée)."""
    df = pd.read_excel(chemin, sheet_name="Annonces", dtype=str,
                       keep_default_na=False)
    return df.rename(columns=MAPPING["agence"]).assign(source="agence")


def read_historique(chemin: Path) -> pd.DataFrame:
    """CSV `;`, UTF-8 contenant des U+FFFD (accents perdus, irréversible à la lecture)."""
    df = pd.read_csv(chemin, sep=";", dtype=str, keep_default_na=False,
                     encoding="utf-8")
    return df.rename(columns=MAPPING["historique"]).assign(source="historique")


def read_notaires(chemin: Path) -> pd.DataFrame:
    """CSV `,`, UTF-8 propre."""
    df = pd.read_csv(chemin, sep=",", dtype=str, keep_default_na=False,
                     encoding="utf-8")
    return df.rename(columns=MAPPING["notaires"]).assign(source="notaires")


def read_particuliers(chemin: Path) -> pd.DataFrame:
    """JSON : liste d'objets {"annonce": {..., "localisation": {...}, "details": {...}}}."""
    with open(chemin, encoding="utf-8") as f:
        brut = json.load(f)
    lignes = []
    for enreg in brut:
        a = enreg["annonce"]
        loc, det = a.get("localisation") or {}, a.get("details") or {}
        lignes.append({
            "id": a.get("id"), "date": a.get("date"),
            "region": loc.get("region"), "ville": loc.get("ville"),
            "categorie": det.get("type"), "transaction": det.get("transaction"),
            "prix": det.get("prix"), "surface": det.get("surface"),
            "chambres": det.get("chambres"), "sdb": det.get("sdb"),
            "statut": a.get("statut"),
        })
    df = pd.DataFrame(lignes, dtype=object)
    return _en_texte(df).assign(source="particuliers")


def read_plateforme(chemin: Path) -> pd.DataFrame:
    """CSV `;` SANS en-tête en ligne 1 ; l'en-tête apparaît en cours de fichier.

    On lit sans en-tête, on impose les 15 noms de colonnes et on écarte
    toute ligne qui répète l'en-tête (ex. ligne 575 du fichier brut).
    """
    df = pd.read_csv(chemin, sep=";", header=None, names=PLATEFORME_COLONNES,
                     dtype=str, keep_default_na=False, encoding="utf-8")
    est_entete = df["ref_plateforme"].eq("ref_plateforme")
    df = df.loc[~est_entete].reset_index(drop=True)
    return df.rename(columns=MAPPING["plateforme"]).assign(source="plateforme")


LECTEURS = {
    "agence": ("agence_teranga.xlsx", read_agence),
    "historique": ("import_historique.csv", read_historique),
    "notaires": ("notaires.csv", read_notaires),
    "particuliers": ("particuliers.json", read_particuliers),
    "plateforme": ("plateforme_immo_sn.csv", read_plateforme),
}


def read_source(nom: str, dossier: Path) -> pd.DataFrame:
    fichier, lecteur = LECTEURS[nom]
    return lecteur(Path(dossier) / fichier)
