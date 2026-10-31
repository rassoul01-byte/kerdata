"""Compétence 3 : nettoyage. Chaque ligne finit dans UN seul fichier :
quarantine (bloquant) / avertissements (conservée + signalée) / donnees_propres.

Toute correction de valeur est tracée dans le journal (avant -> après, règle).
Aucune imputation ici : les manques structurels (chambres, sdb) restent vides et
seront imputés dans le pipeline sklearn, ajusté sur le train uniquement (comp 5/7).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from .typage import parse_date, parse_prix, parse_surface

FFFD = "\ufffd"
AUJOURD_HUI = pd.Timestamp("2026-10-31")
SEUIL_LOYER_VENTE = 3_000_000          # validé en comp 1 (0 erreur sur 1537 lignes connues)
PRIX_ATYPIQUE = (100_000, 2_000_000_000)
SURFACE_ATYPIQUE = (5, 2_000)

STATUTS = {
    "vendu": "Vendu", "vente conclue": "Vendu", "acte signe": "Vendu",
    "en vente": "En vente", "disponible": "Disponible", "loue": "Loué",
    "retire": "Retiré", "sous offre": "Sous offre", "a confirmer": "À confirmer",
}
# Transaction attendue d'après le statut (évidence : sources à transaction connue)
STATUT_TRANSACTION = {"Disponible": "location", "Loué": "location", "En vente": "vente",
                      "Vendu": "vente", "Sous offre": "vente", "Retiré": "vente", "À confirmer": "vente"}

COLONNES_FINALES = ["ligne_id", "source", "id", "date", "transaction", "transaction_origine",
                    "categorie", "region", "ville", "prix", "surface", "chambres", "sdb", "statut"]


def cle(s: str) -> str:
    """Clé de comparaison : sans accents, sans casse, espaces et tirets normalisés."""
    s = unicodedata.normalize("NFKD", (s or "").strip().lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[\s\-]+", " ", s)


class Referentiels:
    def __init__(self, dossier: Path):
        g = pd.read_csv(dossier / "referentiel_geographique.csv")
        c = pd.read_csv(dossier / "referentiel_categories.csv")
        self.geo = g
        self.regions = sorted(g.region.unique())
        self.villes = sorted(g.ville.unique())
        self.paires = set(zip(g.region.map(cle), g.ville.map(cle)))
        self.cat = c
        self.synonymes = {}
        for _, r in c.iterrows():
            for syn in str(r.synonymes).split("|") + [r.categorie]:
                self.synonymes[cle(syn)] = r.categorie


def normaliser_lieu(valeur: str, noms: list[str]) -> tuple[str, str]:
    """-> (valeur normalisée, règle). Règles : inchangé | casse/accents | mojibake | inconnu | vide."""
    v = (valeur or "").strip()
    if not v:
        return "", "vide"
    if v in noms:
        return v, "inchangé"
    if FFFD in v:
        motif = re.compile("^" + re.escape(v).replace(FFFD, ".") + "$", re.I)
        trouves = [n for n in noms if motif.match(n)]
        if len(trouves) == 1:                      # rattachement UNIQUE exigé
            return trouves[0], "mojibake"
        return v, "inconnu"
    index = {cle(n): n for n in noms}
    if cle(v) in index:
        return index[cle(v)], "casse/accents/espaces"
    return v, "inconnu"


def ajouter_identifiants(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ligne_id"] = out["source"] + ":" + (out.groupby("source").cumcount() + 1).astype(str).str.zfill(4)
    return out


def normaliser(df: pd.DataFrame, ref: Referentiels) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalise les champs ; renvoie (df enrichi, journal des corrections)."""
    d = ajouter_identifiants(df)
    journal: list[pd.DataFrame] = []

    def tracer(champ, avant, apres, regle):
        m = (avant != apres) & regle.ne("inchangé") & regle.ne("vide")
        if m.any():
            journal.append(pd.DataFrame({"ligne_id": d.loc[m, "ligne_id"], "champ": champ,
                                         "avant": avant[m], "apres": apres[m], "regle": regle[m]}))

    for champ, noms in (("region", ref.regions), ("ville", ref.villes)):
        res = d[champ].map(lambda v: normaliser_lieu(v, noms))
        d[f"{champ}_brut"] = d[champ]
        d[champ] = res.map(lambda t: t[0]); d[f"{champ}_regle"] = res.map(lambda t: t[1])
        tracer(champ, d[f"{champ}_brut"], d[champ], d[f"{champ}_regle"])

    d["categorie_brut"] = d["categorie"]
    d["categorie"] = d["categorie"].map(lambda v: ref.synonymes.get(cle(v), (v or "").strip()))
    d["categorie_connue"] = d["categorie_brut"].map(lambda v: cle(v) in ref.synonymes)
    tracer("categorie", d["categorie_brut"], d["categorie"], pd.Series("casse/synonyme", index=d.index))

    d["statut_brut"] = d["statut"]
    d["statut"] = d["statut"].map(lambda v: STATUTS.get(cle(v), (v or "").strip()))
    tracer("statut", d["statut_brut"], d["statut"], pd.Series("vocabulaire unique", index=d.index))

    d["prix_brut"], d["surface_brut"], d["date_brut"] = d["prix"], d["surface"], d["date"]
    d["prix_num"] = d["prix_brut"].map(parse_prix)
    d["surface_num"] = d["surface_brut"].map(parse_surface)
    d["date_ts"] = d["date_brut"].map(parse_date)
    propre_prix = d["prix_brut"].str.fullmatch(r"-?\d+(\.0+)?")
    propre_surf = d["surface_brut"].str.fullmatch(r"-?\d+(\.\d+)?")
    tracer("prix", d["prix_brut"], d["prix_num"].map(lambda x: "" if pd.isna(x) else f"{x:.0f}"),
           pd.Series(np.where(propre_prix | d["prix_num"].isna(), "inchangé", "séparateur/unité explicite"), index=d.index))
    tracer("surface", d["surface_brut"], d["surface_num"].map(lambda x: "" if pd.isna(x) else f"{x:g}"),
           pd.Series(np.where(propre_surf | d["surface_num"].isna(), "inchangé", "virgule décimale"), index=d.index))
    tracer("date", d["date_brut"], d["date_ts"].dt.strftime("%Y-%m-%d").fillna(""),
           pd.Series(np.where(d["date_brut"].str.fullmatch(r"\d{4}-\d{2}-\d{2}") | d["date_ts"].isna(), "inchangé", "JJ/MM/AAAA -> ISO"), index=d.index))

    # transaction : connue (plateforme, particuliers) ou inférée par le seuil de prix
    connue = d["transaction"].isin(["vente", "location"])
    inferee = pd.Series(np.where(d["prix_num"] < SEUIL_LOYER_VENTE, "location", "vente"), index=d.index)
    inferee[~(d["prix_num"] > 0)] = ""
    d["transaction_origine"] = np.where(connue, "source", np.where(inferee != "", "inférée_par_prix", "inconnue"))
    d["transaction"] = d["transaction"].where(connue, inferee)
    j = pd.concat(journal, ignore_index=True) if journal else pd.DataFrame(columns=["ligne_id", "champ", "avant", "apres", "regle"])
    d["corrections"] = d["ligne_id"].map(j.groupby("ligne_id").size()).fillna(0).astype(int)
    # l'inférence de `transaction` est tracée mais n'est pas une correction de valeur
    inf = d["transaction_origine"].eq("inférée_par_prix")
    j = pd.concat([j, pd.DataFrame({"ligne_id": d.loc[inf, "ligne_id"], "champ": "transaction", "avant": "",
                                     "apres": d.loc[inf, "transaction"], "regle": "inférée : seuil de prix 3 M FCFA"})], ignore_index=True)
    return d, j


def detecter_doublons(d: pd.DataFrame) -> pd.DataFrame:
    """Doublons exacts (intra-source) et ID dupliqués de contenu différent. -> colonnes motif_q / motif_a."""
    out = pd.DataFrame({"motif_q": "", "motif_a": ""}, index=d.index)
    brut = ["id", "date_brut", "transaction", "categorie_brut", "region_brut", "ville_brut", "prix_brut",
            "surface_brut", "chambres", "sdb", "statut_brut"]
    for s, g in d.groupby("source"):
        exact = g.duplicated(subset=brut, keep="first")
        premier = g[~exact].drop_duplicates(subset=brut).set_index(brut).ligne_id
        for i in g.index[exact]:
            ref_ligne = premier.loc[tuple(g.loc[i, brut])]
            out.loc[i, "motif_q"] = f"doublon exact de {ref_ligne}"
        distincts = g.drop_duplicates(subset=brut).groupby("id").size()
        conflit = g.id.isin(distincts[distincts > 1].index) & ~exact
        out.loc[g.index[conflit], "motif_a"] = "id dupliqué avec contenu différent"
    return out


def doublons_inter_sources(d: pd.DataFrame, valides: pd.Series) -> pd.DataFrame:
    """Doublons PROBABLES (même date, ville, catégorie, surface ; sources différentes) et CONFLITS (prix > 20 % d'écart).
    Aucune fusion : signalement seulement. Retourne le détail des paires."""
    x = d[valides & d.ville.ne("") & d.date_ts.notna()].copy()
    x["k"] = x.date_ts.dt.strftime("%Y-%m-%d") + "|" + x.ville + "|" + x.categorie + "|" + x.surface_num.round(1).astype(str)
    lignes = []
    for k, g in x.groupby("k"):
        if g.source.nunique() > 1:
            ratio = g.prix_num.max() / g.prix_num.min()
            lignes.append(dict(cle=k, type="conflit" if ratio > 1.2 else "probable", ratio_prix=round(ratio, 3),
                               lignes=",".join(g.ligne_id), sources=",".join(sorted(g.source.unique()))))
    return pd.DataFrame(lignes, columns=["cle", "type", "ratio_prix", "lignes", "sources"])


def regles(d: pd.DataFrame, ref: Referentiels, dup: pd.DataFrame) -> pd.DataFrame:
    """Applique les règles métier. Renvoie pour chaque ligne : motifs_q (bloquants) et motifs_a (avertissements)."""
    q: dict[int, list[str]] = {i: [] for i in d.index}
    a: dict[int, list[str]] = {i: [] for i in d.index}

    def ajouter(cible, masque, texte):
        for i in d.index[masque]:
            cible[i].append(texte)

    # --- bloquantes
    ajouter(q, d.id.eq(""), "identifiant absent")
    ajouter(q, d.prix_brut.eq(""), "prix absent")
    ajouter(q, d.prix_brut.ne("") & d.prix_num.isna(), "prix non numérique")
    ajouter(q, d.prix_num.notna() & (d.prix_num <= 0), "prix <= 0")
    ajouter(q, d.surface_brut.eq(""), "surface absente")
    ajouter(q, d.surface_brut.ne("") & d.surface_num.isna(), "surface non numérique")
    ajouter(q, d.surface_num.notna() & (d.surface_num <= 0), "surface <= 0")
    ajouter(q, d.date_ts.isna(), "date non interprétable ou absente")
    futur = d.date_ts > AUJOURD_HUI
    ajouter(q, futur & d.statut.eq("Vendu"), "date future pour une vente conclue")
    ajouter(a, futur & ~d.statut.eq("Vendu"), "date future (non vendue)")
    for i in d.index[dup.motif_q.ne("")]:
        q[i].append(dup.motif_q[i])

    # --- avertissements
    ajouter(a, dup.motif_a.ne(""), "id dupliqué avec contenu différent")
    ajouter(a, d.ville.eq(""), "ville absente")
    ajouter(a, d.region_regle.eq("inconnu") | d.ville_regle.eq("inconnu"), "région ou ville absente du référentiel")
    paire_ok = pd.Series([(cle(r), cle(v)) in ref.paires for r, v in zip(d.region, d.ville)], index=d.index)
    ajouter(a, d.ville.ne("") & d.region_regle.ne("inconnu") & d.ville_regle.ne("inconnu") & ~paire_ok,
            "région et ville incompatibles (non corrigé)")
    ajouter(a, ~d.categorie_connue, "catégorie absente du référentiel")
    ajouter(a, (d.surface_num > 0) & ((d.surface_num < SURFACE_ATYPIQUE[0]) | (d.surface_num > SURFACE_ATYPIQUE[1])),
            "surface atypique (<5 ou >2000 m²)")
    vente = d.transaction.eq("vente") & (d.prix_num > 0)
    ajouter(a, vente & ((d.prix_num < PRIX_ATYPIQUE[0]) | (d.prix_num > PRIX_ATYPIQUE[1])), "prix atypique (vente <100 k ou >2 Md)")
    m = d.merge(ref.cat, left_on="categorie", right_on="categorie", how="left", suffixes=("", "_ref"))
    m.index = d.index
    hors_prix = vente & ((d.prix_num < m.prix_min_indicatif) | (d.prix_num > m.prix_max_indicatif))
    ajouter(a, hors_prix, "prix hors fourchette du référentiel (plausible)")
    hors_surf = (d.surface_num > 0) & ((d.surface_num < m.surface_min_typique) | (d.surface_num > m.surface_max_typique))
    ajouter(a, hors_surf, "surface hors fourchette typique de la catégorie")
    attendu = d.statut.map(STATUT_TRANSACTION)
    ajouter(a, d.transaction_origine.eq("source") & attendu.notna() & attendu.ne(d.transaction),
            "statut incohérent avec la transaction")

    res = pd.DataFrame({"motifs_q": ["; ".join(q[i]) for i in d.index], "motifs_a": ["; ".join(a[i]) for i in d.index]}, index=d.index)
    res["hors_prix_ref"], res["hors_surf_ref"] = hors_prix, hors_surf
    return res


def ajouter_probables(d: pd.DataFrame, res: pd.DataFrame, paires: pd.DataFrame) -> pd.DataFrame:
    res = res.copy()
    pos = {l: i for i, l in zip(d.index, d.ligne_id)}
    for _, p in paires.iterrows():
        for l in p.lignes.split(","):
            txt = f"doublon probable inter-sources ({p.type}, ratio prix {p.ratio_prix})"
            res.loc[pos[l], "motifs_a"] = "; ".join(filter(None, [res.loc[pos[l], "motifs_a"], txt]))
    return res


def classer(d: pd.DataFrame, res: pd.DataFrame) -> pd.Series:
    return pd.Series(np.where(res.motifs_q.ne(""), "quarantaine", np.where(res.motifs_a.ne(""), "avertissement", "propre")), index=d.index)


def nettoyer(brut: pd.DataFrame, dossier_ref: Path) -> dict:
    ref = Referentiels(dossier_ref)
    d, journal = normaliser(brut, ref)
    dup = detecter_doublons(d)
    res = regles(d, ref, dup)
    valides = res.motifs_q.eq("")
    paires = doublons_inter_sources(d, valides)
    res = ajouter_probables(d, res, paires)
    d["classe"] = classer(d, res)
    d = d.join(res)
    return dict(d=d, journal=journal, paires=paires, ref=ref)
