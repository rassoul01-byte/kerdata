#!/usr/bin/env python3
"""Exécute tout le pipeline KerData de bout en bout : python run_pipeline.py"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE / "src"))

from kerdata.pipeline import executer  # noqa: E402

if __name__ == "__main__":
    res = executer(RACINE)
    m = res["tabs"]["mesures"]
    print(f"{m['n']} lignes lues -> {m['propres']} propres | {m['avertissements']} avertissements | {m['quarantaine']} quarantaine")
    print("Sorties dans sortie/ et reports/ ; rapport : sortie/rapport_qualite.md")
