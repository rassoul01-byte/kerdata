"""Conversions de types (compétence 1) : prix, surface, date, entiers.

Ces fonctions MESURENT combien de valeurs sont convertibles ; elles renvoient
NaN / NaT quand la conversion n'est pas fiable. Le traitement des NaN
(quarantaine, imputation) relève de la compétence 3.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

_NOMBRE = r"\d+(?:\.\d+)?"


def parse_prix(v: str) -> float:
    """Texte -> FCFA (float). NaN si absent, non numérique ou ambigu.

    Gère : '123456', '26 620 000' (espaces), '65575000 FCFA' (unité explicite),
    '147.52 millions' (unité explicite). Rejette : '', 'N/A', 'None FCFA',
    'à négocier'.
    """
    s = (v or "").strip()
    if not s:
        return np.nan
    m = re.fullmatch(rf"({_NOMBRE})\s*millions?", s, flags=re.I)
    if m:
        return float(m.group(1)) * 1_000_000
    s = re.sub(r"\s*FCFA$", "", s, flags=re.I)
    if re.fullmatch(r"-?\d{1,3}(?: \d{3})+", s):          # milliers par espaces
        return float(s.replace(" ", ""))
    if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+", s):          # milliers par virgules
        return float(s.replace(",", ""))
    if re.fullmatch(rf"-?{_NOMBRE}", s):
        return float(s)
    return np.nan


def parse_surface(v: str) -> float:
    """Texte -> m² (float). Virgule décimale acceptée ; mots ('quatre-vingt') rejetés."""
    s = (v or "").strip()
    if not s:
        return np.nan
    if re.fullmatch(r"-?\d+,\d+", s):
        s = s.replace(",", ".")
    return float(s) if re.fullmatch(rf"-?{_NOMBRE}", s) else np.nan


def parse_date(v: str) -> pd.Timestamp:
    """ISO AAAA-MM-JJ ou JJ/MM/AAAA -> Timestamp ; NaT si impossible (ex. 32/13/2024)."""
    s = (v or "").strip()
    for rx, fmt in ((r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d"), (r"\d{2}/\d{2}/\d{4}", "%d/%m/%Y")):
        if re.fullmatch(rx, s):
            return pd.to_datetime(s, format=fmt, errors="coerce")
    return pd.NaT


def parse_entier(v: str) -> float:
    s = (v or "").strip()
    return float(s) if re.fullmatch(r"\d+", s) else np.nan


CONVERTISSEURS = {"prix": parse_prix, "surface": parse_surface,
                  "date": parse_date, "chambres": parse_entier, "sdb": parse_entier}
