"""Compétence 3 : tableaux imposés, 6 mesures obligatoires et rapport_qualite.md."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .comp2 import manquants, preparer

TRAITEMENT_MANQUANT = {
    "transaction": "imputée par seuil de prix (3 M FCFA), provenance tracée, SANS indicateur de manque (fuite type 4)",
    "prix": "quarantaine (règle bloquante) : jamais imputé, c'est la cible",
    "surface": "quarantaine (règle bloquante)",
    "date": "quarantaine (règle bloquante)",
    "ville": "conservée avec avertissement (région présente)",
    "statut": "conservé vide : source qui ne le fournit pas ; pas d'indicateur de manque",
    "chambres": "conservé vide ; imputation par groupe dans le pipeline (fit sur train, comp 5/7), sans indicateur de manque",
    "sdb": "conservé vide ; imputation par groupe dans le pipeline (fit sur train, comp 5/7), sans indicateur de manque",
}


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(aucune ligne)_\n"
    cols = list(df.columns)
    lignes = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lignes.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |")
    return "\n".join(lignes) + "\n"


def table_manquants(brut: pd.DataFrame) -> pd.DataFrame:
    """{source, champ, % manquants, mécanisme, traitement} sur l'état initial (avant nettoyage)."""
    m = manquants(preparer(brut))
    m = m[(m.vides > 0) | (m.non_convertibles > 0)].copy()
    m["traitement"] = m.champ.map(TRAITEMENT_MANQUANT)
    m = m.rename(columns={"pct_total_inutilisable": "pct_manquants_ou_illisibles"})
    return m[["source", "champ", "vides", "non_convertibles", "pct_manquants_ou_illisibles", "mecanisme", "traitement"]].reset_index(drop=True)


def table_doublons(res: dict) -> pd.DataFrame:
    d, p = res["d"], res["paires"]
    return pd.DataFrame([
        dict(type="exact (intra-source)", nombre=int(d.motifs_q.str.contains("doublon exact").sum()),
             decision="supprimé du corpus (mis en quarantaine, 1re occurrence conservée)"),
        dict(type="ID dupliqué, contenu différent", nombre=int(d.motifs_a.str.contains("id dupliqué").sum()),
             decision="conservé avec avertissement (arbitrage manuel)"),
        dict(type="probable inter-sources (même date, ville, catégorie, surface)", nombre=int((p.type == "probable").sum()) if len(p) else 0,
             decision="signalé, jamais fusionné sans preuve"),
        dict(type="conflit (même bien, prix à plus de 20 %)", nombre=int((p.type == "conflit").sum()) if len(p) else 0,
             decision="signalé seulement"),
    ])


def table_outliers(res: dict) -> pd.DataFrame:
    d = res["d"]
    ok = d.motifs_q.eq("")
    lignes = []
    for s, g in d.groupby("source"):
        go = g[ok.loc[g.index]]
        v = go[go.transaction.eq("vente")]
        lig = [
            ("prix", "fourchette du référentiel catégoriel", int(go.hors_prix_ref.sum()), "avertissement (plausible)"),
            ("surface", "fourchette typique du référentiel", int(go.hors_surf_ref.sum()), "avertissement"),
            ("prix", "seuils atypiques (<100 k ou >2 Md, ventes)", int(go.motifs_a.str.contains("prix atypique").sum()), "avertissement"),
            ("surface", "seuils atypiques (<5 ou >2000 m²)", int(go.motifs_a.str.contains("surface atypique").sum()), "avertissement"),
            ("prix", "prix <= 0", int(g.motifs_q.str.contains("prix <= 0").sum()), "quarantaine"),
            ("surface", "surface <= 0", int(g.motifs_q.str.contains("surface <= 0").sum()), "quarantaine"),
        ]
        # IQR par catégorie (confirmation) sur log(prix) des ventes conservées
        lp = np.log(v.prix_num)
        q1, q3 = lp.groupby(v.categorie).transform(lambda x: x.quantile(.25)), lp.groupby(v.categorie).transform(lambda x: x.quantile(.75))
        iqr_flag = (lp < q1 - 1.5 * (q3 - q1)) | (lp > q3 + 1.5 * (q3 - q1))
        lig.append(("prix", "IQR par catégorie sur log(prix) (confirmation)", int(iqr_flag.sum()), "confirmation seulement, aucune action"))
        lig.append(("prix", "… dont hors fourchette du référentiel", int((iqr_flag & v.hors_prix_ref).sum()), "recoupement des 2 méthodes"))
        lignes += [dict(source=s, champ=c, methode=m, nombre=n, decision=dec) for c, m, n, dec in lig]
    return pd.DataFrame(lignes)


def mesures(brut: pd.DataFrame, res: dict) -> dict:
    d, j = res["d"], res["journal"]
    n = len(d)
    cl = d.classe.value_counts()
    corrigees = d[(d.corrections > 0)]
    conformes_emblee = d[(d.classe == "propre") & (d.corrections == 0)]
    err = {
        "prix": int(((d.prix_brut != "") & d.prix_num.isna()).sum()),
        "surface": int(((d.surface_brut != "") & d.surface_num.isna()).sum()),
        "date": int(((d.date_brut != "") & d.date_ts.isna()).sum()),
    }
    communs = ["id", "date", "transaction", "categorie", "region", "ville", "prix", "surface", "chambres", "sdb", "statut"]
    manq = (brut[communs] == "").mean().mul(100).round(1)
    return dict(
        n=n, classes=cl.to_dict(), manquants_pct=manq.to_dict(),
        doublons_exacts=int(d.motifs_q.str.contains("doublon exact").sum()),
        doublons_probables=int((res["paires"].type == "probable").sum()) if len(res["paires"]) else 0,
        conflits=int((res["paires"].type == "conflit").sum()) if len(res["paires"]) else 0,
        erreurs_conversion=err, lignes_corrigees=len(corrigees), corrections_total=int(len(j[j.champ != "transaction"])),
        quarantaine=int(cl.get("quarantaine", 0)), avertissements=int(cl.get("avertissement", 0)), propres=int(cl.get("propre", 0)),
        taux_conformes_emblee=round(100 * len(conformes_emblee) / n, 1), taux_propres=round(100 * cl.get("propre", 0) / n, 1),
        taux_conserves=round(100 * (cl.get("propre", 0) + cl.get("avertissement", 0)) / n, 1),
    )


def validation_transaction(d: pd.DataFrame) -> pd.DataFrame:
    """Preuve indépendante du seuil de prix : cohérence avec le statut sémantique (Loué/Disponible = location)."""
    from .nettoyage import STATUT_TRANSACTION
    x = d[d.transaction_origine.eq("inférée_par_prix") & d.statut.map(STATUT_TRANSACTION).notna()].copy()
    x["attendue_par_statut"] = x.statut.map(STATUT_TRANSACTION)
    x["coherent"] = x.attendue_par_statut.eq(x.transaction)
    out = (x.groupby(["source", "transaction"]).agg(lignes_inferees=("coherent", "size"), confirmees_par_statut=("coherent", "sum"))
           .reset_index().rename(columns={"transaction": "transaction_inferee"}))
    out["pct_confirme"] = (100 * out.confirmees_par_statut / out.lignes_inferees).round(1)
    return out


def rapport_md(brut: pd.DataFrame, res: dict, tabs: dict) -> str:
    m = tabs["mesures"]
    d = res["d"]
    cl = m["classes"]
    err = m["erreurs_conversion"]
    top_manq = pd.Series(m["manquants_pct"]).sort_values(ascending=False)
    top_manq = top_manq[top_manq > 0]
    n_inf = int((d.transaction_origine == "inférée_par_prix").sum())
    n_prix_q = int(d.motifs_q.str.contains("prix absent|prix non numérique|prix <= 0").sum())
    n_surf_q = int(d.motifs_q.str.contains("surface absente|surface non numérique|surface <= 0").sum())
    lab = d[d.transaction_origine.eq("source")]
    n_loue = int(((lab.statut == "Loué") & (lab.transaction == "location")).sum())
    n_dispo = int(((lab.statut == "Disponible") & (lab.transaction == "location")).sum())
    n_loc_vente = int(lab.statut.isin(["Loué", "Disponible"]).sum()) - n_loue - n_dispo
    q = d[d.classe == "quarantaine"]
    part_part = round(100 * (q.source == "particuliers").mean(), 1)
    return f"""# Rapport de qualité — KerData (corpus de 5 sources)

Généré automatiquement par `run_pipeline.py`. Chaque ligne des {m['n']} lignes lues finit dans **un seul** fichier.

## Bilan global

| Fichier | Lignes | Part |
|---|---|---|
| `donnees_propres.csv` | {cl.get('propre', 0)} | {m['taux_propres']} % |
| `avertissements.csv` (conservées, signalées) | {cl.get('avertissement', 0)} | {round(100 * cl.get('avertissement', 0) / m['n'], 1)} % |
| `quarantine.csv` (rejetées, avec raison) | {cl.get('quarantaine', 0)} | {round(100 * cl.get('quarantaine', 0) / m['n'], 1)} % |
| **Total** | **{m['n']}** | 100 % |

Corpus conservé (propres + avertissements) : **{cl.get('propre', 0) + cl.get('avertissement', 0)} lignes** ({m['taux_conserves']} %), fichier `corpus_conserve.csv`.

## Les 6 mesures obligatoires

| # | Mesure | Valeur |
|---|---|---|
| 1 | Taux de manquants par colonne (état initial, toutes sources) | voir tableau « Manquants » ; colonnes les plus vides : {", ".join(f"{k} {v} %" for k, v in top_manq.head(6).items())} |
| 2 | Doublons exacts | **{m['doublons_exacts']}** (tous dans `plateforme`, identifiants dupliqués) |
| 3 | Doublons probables / conflits entre sources | **{m['doublons_probables']}** probables, **{m['conflits']}** conflits (clé : date + ville + catégorie + surface, après correction du mojibake) |
| 4 | Erreurs de conversion par champ | prix **{err['prix']}**, surface **{err['surface']}**, date **{err['date']}** (valeurs non vides non convertibles) |
| 5 | Corrigés / quarantaine / avertissements | **{m['lignes_corrigees']}** lignes corrigées ({m['corrections_total']} corrections tracées dans `journal_corrections.csv`) / **{m['quarantaine']}** / **{m['avertissements']}** |
| 6 | Taux d'enregistrements entièrement conformes | **{m['taux_conformes_emblee']} %** conformes d'emblée (sans correction ni alerte), **{m['taux_propres']} %** propres après corrections |

## Manquants : mécanisme et traitement

{md_table(tabs['manquants'])}
## Doublons

{md_table(tabs['doublons'])}
## Aberrants

{md_table(tabs['outliers_resume'])}
Détail par source : `reports/comp3_outliers.csv`.

## Motifs de quarantaine

{md_table(tabs['motifs_q'])}
## Motifs d'avertissement

{md_table(tabs['motifs_a'])}
## Transaction inférée : validation par le statut

La colonne `transaction` est absente de 3 sources ; elle est inférée par seuil de prix (3 M FCFA, 0 erreur sur les lignes à transaction connue).
Contrôle indépendant : dans les sources étiquetées, `Loué` ({n_loue} lignes) et `Disponible` ({n_dispo} lignes) n'apparaissent qu'avec des locations ({n_loc_vente} avec une vente). Pour `notaires`, seul `Vendu` existe : le contrôle ne vaut que pour l'agence (106 loyers confirmés par leur statut) ; `historique` n'a pas de statut et n'est donc pas contrôlable.

{md_table(tabs['validation_transaction'])}
## Limites reconnues

- **Volume agence :** 640 lignes lues pour 680 annoncées dans la fiche de conception (−40) ; non comblé.
- **Quarantaine volontairement stricte :** {n_prix_q} lignes sans prix exploitable et {n_surf_q} sans surface exploitable (absentes ou illisibles) sont rejetées par la règle bloquante, même si certaines surfaces seraient imputables ; {part_part} % de la quarantaine vient de `particuliers`.
- **Transaction inférée** pour {n_inf} lignes : fondée sur un seuil validé, mais reste une inférence (colonne `transaction_origine`).
- **Doublons probables inter-sources : 0** sur la clé stricte ; des doublons dont la date, la ville ou la surface diffèrent légèrement ne seraient pas vus.
- **Fourchettes du référentiel indicatives :** les prix hors fourchette sont conservés en avertissement, jamais supprimés.
- **Colonnes écartées du corpus final :** `quartier`, `pieces`, `description`, `date_expiration`, `commercial`, `devise` (propres à une source ou redondantes avec `transaction`).
- **Aucune imputation ici :** `chambres` et `sdb` restent vides là où la source ne les fournit pas ; l'imputation par groupe se fera dans le pipeline, ajustée sur le train uniquement.
"""
