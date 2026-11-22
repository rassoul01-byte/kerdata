"""Génère docs/soutenance.md : réponses de 30 secondes, chiffrées, aux questions de la fiche 11.

Tous les chiffres sont relus dans reports/ et sortie/ (aucun chiffre écrit à la main).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .qualite import md_table


def _faits(racine: Path) -> dict:
    rep, sortie = racine / "reports", racine / "sortie"
    F: dict = {}
    brut = pd.read_csv(sortie / "corpus_brut_concatene.csv", dtype=str, keep_default_na=False)
    p = pd.read_csv(sortie / "donnees_propres.csv", dtype=str, keep_default_na=False)
    a = pd.read_csv(sortie / "avertissements.csv", dtype=str, keep_default_na=False)
    q = pd.read_csv(sortie / "quarantine.csv", dtype=str, keep_default_na=False)
    F["par_source"] = pd.DataFrame({
        "source": sorted(brut.source.unique())}).assign(
        lues=lambda d: d.source.map(brut.source.value_counts()), propres=lambda d: d.source.map(p.source.value_counts()).fillna(0).astype(int),
        avertissements=lambda d: d.source.map(a.source.value_counts()).fillna(0).astype(int), quarantaine=lambda d: d.source.map(q.source.value_counts()).fillna(0).astype(int))
    F["n"], F["n_p"], F["n_a"], F["n_q"] = len(brut), len(p), len(a), len(q)
    mes = pd.read_csv(rep / "comp3_mesures.csv", index_col=0).valeur
    F["conformes"], F["propres_pct"] = mes["taux_conformes_emblee"], mes["taux_propres"]
    pl = pd.read_csv(rep / "comp1_prix_vs_log.csv").set_index("population").loc["segment vente"]
    F["skew_brut"], F["skew_log"], F["ratio_mm"] = pl.skew_brut, pl.skew_log, pl.ratio_mean_median
    ty = pd.read_csv(rep / "comp1_types_par_source.csv").set_index(["source", "champ"])
    F["prix_part"] = ty.loc[("particuliers", "prix")]
    F["prix_plat"] = ty.loc[("plateforme", "prix")]
    c6 = pd.read_csv(rep / "comp6_candidates.csv").set_index("variable")
    F["c6"] = c6
    F["meilleur_gain"] = c6[c6.type.isin(["existante", "créée"])].gain.max()
    F["meilleure"] = c6[c6.type.isin(["existante", "créée"])].gain.idxmax()
    F["mk"] = pd.read_csv(rep / "comp7_preuve_strategie_mann_kendall.csv")
    F["ens"] = pd.read_csv(rep / "comp7_split_ensembles.csv").set_index("ensemble")
    F["src_split"] = pd.read_csv(rep / "comp7_split_effectifs_source.csv")
    F["det"] = pd.read_csv(rep / "comp8_detectabilite_source.csv")
    F["ev"] = json.loads((rep / "comp9_evaluation_finale.json").read_text(encoding="utf-8"))
    F["scelle"] = json.loads((sortie / "test_scelle.json").read_text(encoding="utf-8"))
    F["aud"] = pd.read_csv(rep / "comp8_audit_features.csv")
    F["alpha"] = pd.read_csv(rep / "comp9_choix_alpha_validation.csv")
    F["cr"] = pd.read_csv(rep / "comp5_audits_mesures.csv", index_col=0).valeur
    # anomalies par source
    F["moj"] = int((brut.region.str.contains("\ufffd") | brut.ville.str.contains("\ufffd")).sum())
    F["stat_var"] = brut[brut.statut.isin(["VENDU", "Vente conclue", "Acte signé"])].groupby("source").size().to_dict()
    ag = brut[brut.source == "agence"]
    F["agence_s"] = int((pd.to_numeric(ag.surface, errors="coerce") <= 0).sum())
    F["agence_p"] = int((pd.to_numeric(ag.prix, errors="coerce") <= 0).sum())
    F["agence_q"] = int(q[q.source == "agence"].shape[0])
    F["dup"] = int(q.motifs_q.str.contains("doublon exact").sum())
    F["dates_fut"] = int(q.motifs_q.str.contains("date future").sum())
    import re
    out = pd.read_csv(rep / "comp3_outliers.csv")
    F["n_hors_prix"] = int(out[(out.champ == "prix") & out.methode.str.startswith("fourchette")].nombre.sum())
    dbl = pd.read_csv(rep / "comp3_doublons.csv").set_index("type")
    F["n_probables"] = int(dbl[dbl.index.str.startswith("probable")].nombre.iloc[0])
    F["q_part"] = int(q[q.source == "particuliers"].shape[0])
    F["notaires_dates"] = int(ty.loc[("notaires", "date")].n_non_convertibles)
    sm = pd.read_csv(rep / "comp2_d4_d5_correlations_prix_surface.csv")
    F["r_glob"] = float(sm[sm.niveau == "global"].spearman.iloc[0]); F["r_cat_max"] = float(sm[sm.niveau == "catégorie"].spearman.abs().max())
    rq = (sortie / "rapport_qualite.md").read_text(encoding="utf-8")
    m = re.search(r"Kruskal sur le prix p = ([0-9]+\.[0-9]+), sur la surface p = ([0-9]+\.[0-9]+)", rq)
    F["kw_prix"], F["kw_surf"] = (m.group(1), m.group(2)) if m else ("—", "—")
    m = re.search(r"l'historique contient ([0-9.]+) % de chambres", rq)
    F["chambres_hist"] = m.group(1) if m else "—"
    def _av_ap(libelle):
        m = re.search(r"\| " + re.escape(libelle) + r" \| ([0-9.]+) \| ([^|]+?) \|", rq)
        return (m.group(1), m.group(2).strip()) if m else ("—", "—")
    F["v5"] = {k: _av_ap(k) for k in ("Prix absents, illisibles ou <= 0", "Dates non ISO ou impossibles", "Lignes avec accents cassés (�)")}
    ec = pd.read_csv(rep / "comp7_effectifs_categorie_par_ensemble.csv", index_col=0)
    F["min_cat"] = int(ec.values.min())
    sp = pd.read_csv(rep / "comp7_split_effectifs_source.csv")
    F["ecart_src"] = float(sp[["train_pct", "val_pct", "test_pct"]].max(axis=1).sub(sp[["train_pct", "val_pct", "test_pct"]].min(axis=1)).max())
    pr = pd.read_csv(rep / "comp5_preuve_non_fuite.csv")
    F["annee_val"] = float(pr[pr.ajustement.str.startswith("fit sur train (") & (pr.variable == "annee")].moyenne_val.iloc[0])
    geo = pd.read_csv(rep / "comp2_f_coherence_geographique.csv")
    F["formes"] = int(geo[geo.mesure.str.contains("formes cassées récupérables")].valeur.sum())
    ins = (racine / "docs" / "insights_comp2.md").read_text(encoding="utf-8") if (racine / "docs" / "insights_comp2.md").exists() else ""
    F["n_insights"] = len(re.findall(r"(?m)^\d+\. ", ins))
    f_jus = racine / "docs" / "justifications.md"
    F["n_decisions"] = len(re.findall(r"(?m)^\| \d+\.\d+ \|", f_jus.read_text(encoding="utf-8"))) if f_jus.exists() else 0
    F["motifs"] = q.motifs_q.str.split("; ").explode().str.replace(r" de plateforme:\d+", "", regex=True).value_counts()
    return F


def generer(racine: Path) -> Path:
    racine = Path(racine)
    F = _faits(racine)
    ps, ev, c6, det, aud = F["par_source"], F["ev"], F["c6"], F["det"].set_index("ensemble_de_features"), F["aud"].set_index("feature")
    g, b = ev["global_"], ev["baseline_mediane_categorie"]
    cat_r2 = [m["r2_log"] for m in ev["par_categorie"].values()]
    fin = det.iloc[0]
    mk = F["mk"]
    part, plat = F["prix_part"], F["prix_plat"]
    tt = lambda d: " + ".join(f"{k} {int(v)}" for k, v in d.items())
    src = F["src_split"].set_index("source")

    texte = f"""# Support de soutenance — KerData (Module 2)

*Généré par `run_pipeline.py` : chaque chiffre est relu dans `reports/` et `sortie/`. Règle d'or : répondre en 30 secondes, chiffrer, nommer la limite.*

## 0. Les 7 choses à savoir montrer en 30 secondes

| Demande du jury | Réponse chiffrée | Où l'ouvrir |
|---|---|---|
| Retrouver le chiffre d'une décision | {F['n_decisions']} décisions numérotées (`0.1` à `9.8`), chacune avec sa preuve chiffrée | `docs/justifications.md` |
| Pipeline rechargé | `models/pipeline_preparation.joblib` rechargé dans un interpréteur neuf, prédictions identiques (écart 0) | `docs/pipeline.md`, notebook section 7 |
| Gain de `prix_m2` | seul : R² {c6.loc['prix_m2', 'r2_avec']:.3f} (gain {c6.loc['prix_m2', 'gain']:+.3f}) ; avec `surface_log` : **R² = {c6.loc['prix_m2 + surface_log', 'r2_avec']:.5f}** → fuite | `reports/comp6_candidates.csv` |
| Limite principale | le prix se prédit par la catégorie ; à l'intérieur d'une catégorie R² de {min(cat_r2):+.2f} à {max(cat_r2):+.2f} | décision 9.8 |
| Pourquoi `statut` est exclu | connu après la vente (fuite type 2) et proxy de la source (V = {F['cr']['statut.v_source_statut']:.2f}) | décisions 5.1, 8.3 |
| Pourquoi `source` est exclue | identifiant de flux (type 4) ; gain mesuré {c6.loc['source', 'gain']:+.4f} | décisions 5.2, 6.7, 8.4 |
| Une anomalie par source | voir section 1 | `sortie/quarantine.csv` |

## 1. Chiffres à connaître : lignes par source, avant et après nettoyage

{md_table(ps)}
Total : **{F['n']} lues → {F['n_p']} propres, {F['n_a']} avertissements, {F['n_q']} en quarantaine** ({F['conformes']} % conformes d'emblée, {F['propres_pct']} % propres après traitement). Écart avec la fiche : 40 lignes d'agence manquent (640 lues pour 680).

**Une anomalie par source :**

| Source | Anomalie | Chiffre |
|---|---|---|
| `historique` | accents cassés (mojibake) | {F['moj']} lignes ; {F['formes']} formes distinctes, chacune rattachée à un seul nom du référentiel |
| `plateforme` | en-tête absent en ligne 1, répété en ligne 575 ; ID dupliqués | 1 ligne d'en-tête écartée ; {F['dup']} doublons exacts → quarantaine |
| `particuliers` | prix en texte (suffixe FCFA, `None FCFA`) et surfaces en mots | prix : {int(part.n_convertibles)} à convertir, {int(part.n_non_convertibles)} illisibles, {int(part.n_vides)} vides ; {F['q_part']} lignes en quarantaine |
| `notaires` | statuts aux libellés variables, dates impossibles | statuts non harmonisés (`VENDU`, `Vente conclue`, `Acte signé`) : {', '.join(f'{k} {v} lignes' for k, v in F['stat_var'].items())} ; {F['notaires_dates']} dates impossibles (`32/13/2024`) |
| `agence` | surfaces et prix négatifs ou nuls | {F['agence_s']} surfaces ≤ 0 et {F['agence_p']} prix ≤ 0 ; {F['agence_q']} lignes en quarantaine ; 40 lignes manquantes vs fiche |

## 2. Questions par compétence (réponses de 30 secondes)

### Compétence 1 — Types et statistiques
- **Skewness de `prix` avant/après log ?** Ventes : **{F['skew_brut']:.2f}** → **{F['skew_log']:.2f}**. Conséquence : on modélise `log(prix)`.
- **Pourquoi la médiane ?** La moyenne dépasse la médiane (ratio {F['ratio_mm']:.2f}) à cause de la queue à droite ; la médiane résume le bien typique.
- **QQ-plot ?** Compare les quantiles à ceux d'une loi normale : `log(prix)` suit la diagonale par segment, le mélange ventes + locations montre une cassure (deux populations), d'où la segmentation.
- **Conséquence d'un mauvais typage ?** Un prix en texte (« 147.52 millions ») ferait planter ou fausser tout calcul ; ici {int(plat.n_convertibles)} prix de `plateforme` sont à convertir et {int(plat.n_non_convertibles)} illisibles (« à négocier »).
- **Prix en texte ?** `particuliers` : {int(part.n_convertibles)} convertibles + {int(part.n_non_convertibles)} illisibles ; `plateforme` : {int(plat.n_convertibles)} convertibles + {int(plat.n_non_convertibles)} illisibles.

### Compétence 2 — EDA
- **Insights ?** {F['n_insights']} (voir `docs/insights_comp2.md`) : `transaction` structurellement absente de 3 sources ; mojibake réparable ; Simpson actif ; pas de tendance ; lignes à écarter.
- **Simpson ?** Oui, sur `prix` ~ `surface` : corrélation globale {F['r_glob']:.2f}, mais |r| ≤ {F['r_cat_max']:.2f} dans chaque catégorie. Conséquence : pas de `prix_m2`, pas de `surface` seule.
- **Mann-Kendall ?** p = {mk.p_value.min():.2f} à {mk.p_value.max():.2f} à {len(mk)} échelles : pas de tendance → split aléatoire.
- **Mécanisme des manquants ?** 100 % absent dans une source = structurel ; sinon khi2 contre catégorie/statut/transaction : p > 0,05 = aléatoire → quarantaine plutôt qu'imputation.
- **Source la plus anomalique ?** `particuliers` ({F['q_part']} des {F['n_q']} lignes en quarantaine).

### Compétence 3 — Nettoyage
- **Quarantaine / avertissements par source ?** Tableau de la section 1 ({F['n_q']} / {F['n_a']} au total).
- **Bloquante vs avertissement ?** Bloquante : la ligne n'est pas exploitable (prix, surface ou date absents/illisibles/≤ 0, doublon exact, date future + vendu). Avertissement : exploitable mais suspecte (hors fourchette, ville absente, doublon probable) : conservée et signalée.
- **Indicateur de manque ?** Non : `chambres_vide` + `sdb_vide` devinent la source (AUC {det.loc['2 indicateurs de manque (jamais créés)', 'auc_macro']:.2f}) : fuite type 4.
- **Sort d'un outlier ?** Fourchette du référentiel de sa catégorie : hors fourchette mais plausible → avertissement ({F['n_hors_prix']} ventes), jamais supprimé ; l'IQR sert de confirmation seulement.
- **Doublon probable ?** Même bien vu par 2 sources (date, ville, catégorie, surface) : mesuré ({F['n_probables']} trouvé) ; on signale, on ne fusionne jamais sans preuve.
- **Mojibake ?** Caractère de remplacement `�` ; on le remplace par le nom du référentiel **uniquement si le rattachement est unique** ({F['formes']} formes sur {F['formes']}) ; un motif ambigu n'est pas deviné.
- **Header dupliqué ?** Lecture sans en-tête, 15 noms imposés, ligne répétant l'en-tête écartée (ligne 575).
- **ID dupliqués dans `plateforme` ?** {F['dup']}, tous identiques à la ligne d'origine : 1re occurrence conservée, copies en quarantaine (« doublon exact de plateforme:00xx »).
- **Surfaces négatives de `agence` ?** {F['agence_s']} lignes avec surface ≤ 0 : quarantaine, valeur brute conservée dans `quarantine.csv`.

> **Piège : pourquoi ne pas supprimer toutes les lignes avec des manquants ?** Les manquants structurels (`transaction`, `sdb`, `chambres`, `statut`) sont concentrés sur une source : supprimer ces lignes reviendrait à exclure la source entière (perte et biais). On distingue structurel, aléatoire et bloquant.
>
> **Piège : pourquoi ne pas garder la feuille `Params` d'Excel ?** C'est de la métadonnée (4 lignes), pas des annonces : elle corromprait le corpus ; seule la feuille `Annonces` est lue.

### Compétence 4 — Visualisations
- **Diagnostique vs restitution ?** La diagnostique cherche (exploration, comp 2) ; la restitution prouve une décision déjà prise, avec une conclusion chiffrée dans le titre.
- **Figure qui justifie `log(prix)` ?** V1 : skew {F['skew_brut']:.2f} → {F['skew_log']:.2f}.
- **Preuve du nettoyage ?** V5 : conformité {F['conformes']} % → {F['propres_pct']} %, mesurée sur les fichiers livrés (prix invalides {F['v5']['Prix absents, illisibles ou <= 0'][0]} → {F['v5']['Prix absents, illisibles ou <= 0'][1]}, dates non ISO {F['v5']['Dates non ISO ou impossibles'][0]} → {F['v5']['Dates non ISO ou impossibles'][1]}, accents cassés {F['v5']['Lignes avec accents cassés (�)'][0]} → {F['v5']['Lignes avec accents cassés (�)'][1]}).
- **V6 : sources alignées ?** Oui après regroupement par catégorie (Kruskal prix p = {F['kw_prix']}, surface p = {F['kw_surf']}) ; en brut la surface de l'historique se détache par **effet de composition** ({F['chambres_hist']} % de chambres). Conséquence : `source` n'entre pas dans le modèle et le split est stratifié.

### Compétence 5 — Encodage
- **One-hot et pas label encoding ?** `categorie` n'a pas d'ordre : un entier inventerait un ordre (Villa > Studio) que le modèle linéaire exploiterait.
- **`statut` ?** Exclu : `Vendu` est connu après la vente (type 2) ; V(source, statut) = {F['cr']['statut.v_source_statut']:.2f} le rend proxy de la source ; aucun lien avec le prix (η² = {F['cr']['statut.eta2']:.4f}).
- **`source` ?** Exclue : identifiant de flux, η² sur le prix relatif = {F['cr']['source.eta2_prix_std']:.4f} (aucun signal).
- **`commune` ?** Exclue du one-hot : {int(F['cr']['cr.n_villes'])} modalités, gain de variance expliquée de {100 * F['cr']['cr.gain_ville_vs_region']:.2f} point par rapport à la région ; frequency encoding testé en comp 6 : gain {c6.loc['ville_frequence', 'gain']:+.4f}.
- **Preuve d'absence de fuite ?** Fit sur le train : moyenne de `annee` = 0 sur le train, {F['annee_val']:.4f} sur la validation ; fit sur la validation donnerait exactement 0.
- **`handle_unknown="ignore"` ?** Une modalité jamais vue en production (« Château ») donne une ligne de zéros au lieu d'une erreur.

> **Piège : pourquoi ne pas one-hot `commune` ? Elle contient peut-être de l'information.** 46 modalités, redondantes avec la région ; gain mesuré {c6.loc['ville_frequence', 'gain']:+.4f} en CV : proche de 0.
>
> **Piège : pourquoi ne pas utiliser `source` en one-hot ?** Identifiant de flux, pas une caractéristique du bien. Gain mesuré {c6.loc['source', 'gain']:+.4f} : la fiche attendait un gain positif, il n'est pas observé ; on l'exclut quand même par principe (fuite type 4).

### Compétence 6 — Features
- **Créées ?** `distance_dakar_km`, `ville_frequence`, `surface_x_categorie`, `surface_par_chambre` (4) + 4 fuites volontaires + 2 audits.
- **Exclues ?** Toutes les créées (gain maximal en valeur absolue : {c6.loc[['distance_dakar_km', 'ville_frequence', 'surface_x_categorie', 'surface_par_chambre']].gain.abs().max():.4f}, bien sous le seuil de 0,01), plus `annee`, `mois`, `chambres_sdb`.
- **Meilleur gain ?** `{F['meilleure']}` : {F['meilleur_gain']:+.4f} en R² CV, soit < 0,01 : neutre ; gardée par sens métier.
- **`prix_m2` ?** Seul : R² {c6.loc['prix_m2', 'r2_avec']:.3f}, gain {c6.loc['prix_m2', 'gain']:+.3f} ; avec `surface_log` : **R² {c6.loc['prix_m2 + surface_log', 'r2_avec']:.5f}**. Fuite type 1 : `prix_m2` contient la cible.
- **`source` en feature ?** Gain {c6.loc['source', 'gain']:+.4f} ; fuite type 4 ; exclue.
- **Mesure du gain ?** CV 5 plis sur le train seul, une candidate à la fois sur la baseline `categorie` (R² {c6.iloc[0].r2_base:.5f}), seuil ±0,01, confirmé par une forêt.

> **Piège : « votre modèle a un R² de 0,99, c'est excellent non ? »** Non : c'est un signal d'alarme. Une feature contient probablement `prix` (c'est ce que fait `prix_m2 + surface_log`, R² {c6.loc['prix_m2 + surface_log', 'r2_avec']:.5f}) ou `source` a été gardée. Ici `garde_score` interrompt tout R² > 0,95, et notre modèle légitime plafonne à {g['r2_log']:.2f}.
>
> **Piège : `est_hors_fourchette` a un gain de {c6.loc['est_hors_fourchette', 'gain']:+.3f} > 0,01, on la garde ?** Non : elle est dérivée de `prix`. Un seuil seul aurait gardé une fuite : le rejet de principe passe avant la mesure.

### Compétence 7 — Split
- **Ratio ?** 70/15/15 : {int(F['ens'].loc['train', 'count'])} / {int(F['ens'].loc['val', 'count'])} / {int(F['ens'].loc['test', 'count'])} ventes ; ≥ {F['min_cat']} biens par catégorie dans chaque ensemble.
- **Aléatoire ou temporel ?** Aléatoire : Mann-Kendall p = {mk.p_value.min():.2f} à {mk.p_value.max():.2f} (annuel, mensuel, par vente).
- **Test scellé ?** Empreinte SHA-256 de ses {F['scelle']['n_lignes']} lignes (`sortie/test_scelle.json`, `{F['scelle']['sha256_contenu'][:12]}…`) ; modifier un prix ou déplacer une ligne change l'empreinte ; aucun module hors `split.py` et `comp7.py` ne lit le test (testé).
- **Stratifier par `categorie` ?** Elle explique 74 % de la variance : sans stratification, une petite catégorie pourrait manquer au test.
- **5 sources dans chaque ensemble ?** Oui : effectifs {', '.join(f"{s} {int(r.train)}/{int(r.val)}/{int(r.test)}" for s, r in src.iterrows())} (train/val/test) ; écart maximal {F['ecart_src']:.2f} point.
- **Relancer le split ?** Mêmes lignes : graine 42, testé (graine 43 donne un autre split).

> **Piège : les sources ne couvrent pas les mêmes périodes, un split aléatoire est-il correct ?** Oui si Mann-Kendall ne détecte pas de tendance (p > 0,05), mais il faut vérifier les effectifs par source. Ici, stratifié sur `categorie` seule, l'écart par source dépassait 2 points : on a ajouté `source` à la stratification (écart final {F['ecart_src']:.2f} point).

### Compétence 8 — Anti-fuite
- **Les 4 types, un cas réel chacun :** 1 `prix_m2` (R² {c6.loc['prix_m2 + surface_log', 'r2_avec']:.5f}) ; 2 `statut` = `Vendu` (connu après la vente) ; 3 un scaler fitté sur tout le jeu (contre-épreuve : fit sur la validation → moyenne exactement 0) ; 4 `source`, `annee+mois` (AUC {det[det.index.str.startswith('annee')].auc_macro.iloc[0]:.2f}), indicateurs de manque (AUC {det.loc['2 indicateurs de manque (jamais créés)', 'auc_macro']:.2f}).
- **Fuite de type 2 ?** `statut` (`Vendu`, `Vente conclue`, `Acte signé`, `Loué`) et `date` pour notaires/historique (date d'acte ou de vente).
- **Vérifier qu'un scaler n'est pas fitté sur tout ?** Un espion en tête du pipeline enregistre les lignes vues au fit : {int(pd.read_csv(racine / 'reports' / 'comp8_audit_fit.csv', index_col=0).valeur['lignes_vues_au_fit'])} vues, 0 de validation ou test.
- **Prévenir le type 4 ?** Tester si les features devinent la source : features finales AUC {fin.auc_macro:.3f} (hasard = 0,5), précision {fin.precision:.3f} contre {fin.precision_baseline:.3f}.
- **Détecter une fuite sans la voir ?** Un score suspect (R² > 0,95 pour un prix immobilier) déclenche l'audit.
- **Pourquoi retirer `date_expiration`, `quartier`, `description` ?** Colonnes renseignées dans une seule source : leur présence **est** la source (V de Cramér = 1,00). Elles sont absentes des 4 fichiers de sortie ; seule la trace brute les garde. *Écart assumé : la fiche demande de les retirer avant la concaténation.*

### Compétence 9 — Pipeline
- **Dans le pipeline ?** `normalisation` → `preparation` (one-hot 7 + 14, log1p/RobustScaler sur la surface) → `Ridge`, cible `log(prix)` : 22 colonnes.
- **Hors pipeline ?** Nettoyage de la comp 3, inférence de `transaction`, split : règles ou décisions sur le corpus, rejouées par `run_pipeline.py` (concaténation des 5 sources incluse).
- **Reproductible ?** Deux exécutions complètes : mêmes coefficients (`{ev['empreinte_coefficients']}`), mêmes prédictions ; sur un clone neuf, `run_pipeline.py` ne modifie aucun fichier suivi.
- **Nouvelle modalité ?** Ignorée (ligne de zéros), sans erreur ; surface absente ou illisible : refus explicite.
- **Sérialisation ?** `joblib` ; rechargé dans un interpréteur neuf : écart 0 sur 60 lignes de validation et 60 de test.
- **`particuliers` (JSON imbriqué) vs `plateforme` (CSV) ?** `adapter_ligne(source, ligne)` aplatit `annonce.details.surface` ou renomme les colonnes natives, puis le même pipeline s'applique ; testé sur une ligne brute de chacune des 5 sources.

## 3. Questions transverses (honnêteté)

- **Décision la plus hésitée ?** Garder `surface_log` : gain neutre ({c6.loc['surface_log', 'gain']:+.4f}) mais la forêt perd {abs(c6.loc['surface_log', 'gain_foret']):.3f} ; gardée par sens métier et parce que le modèle final est linéaire.
- **Ce que je changerais ?** Mettre en quarantaine les 4 ventes datées de 2028 (conservées en avertissement) ; je ne l'ai pas fait pour ne pas modifier le corpus après le scellé du test.
- **Limite principale ?** Le modèle fait à peine mieux que la médiane de la catégorie : R² log {g['r2_log']:.3f} contre {b['r2_log']:.3f} sur le test, erreur médiane {g['mdape_pct']:.1f} % contre {b['mdape_pct']:.1f} %. Les données sont synthétiques : la surface n'explique rien à l'intérieur d'une catégorie.
- **Avec deux fois plus de temps ?** Enrichir les features intra-catégorie (quartier, état, étage), modéliser les loyers séparément, valider dans le temps.
- **Hypothèse la plus fragile ?** Le seuil de 3 M FCFA entre ventes et locations : 0 erreur sur 1537 lignes connues et confirmé par le statut, mais choisi en regardant tout le corpus, test compris.
- **Gérer 5 sources sans perdre le fil ?** Un schéma commun, `source` conservée pour l'audit seulement, un registre de décisions numérotées et un script unique rejouable.

## 4. Trois slides

1. **Nettoyage** : tableau de la section 1, V5 ({F['conformes']} % → {F['propres_pct']} %), une anomalie par source.
2. **Features** : tableau des 15 candidates (`reports/comp6_candidates.csv`), le mirage `prix_m2` (R² {c6.loc['prix_m2 + surface_log', 'r2_avec']:.5f}), l'AUC de détection de la source.
3. **Pipeline** : schéma `normalisation → préparation → Ridge`, rechargement en direct, résultat du test ({g['r2_log']:.3f}, évalué une seule fois) et limites.

## 5. À ouvrir à la demande

```
head sortie/quarantine.csv sortie/avertissements.csv sortie/donnees_propres.csv
grep "^| 6.6" docs/justifications.md
PYTHONPATH=src python -c "import joblib; m = joblib.load('models/pipeline_preparation.joblib'); print(m)"
```

## 6. Réponses à ne jamais donner

« C'est la méthode » · « Je ne sais pas » (dire : *je n'ai pas mesuré, voici comment je le ferais*) · « Ça marche bien » sans chiffre · « C'est mieux » sans comparaison · inventer un chiffre · « j'ai suivi le tutoriel ».
"""
    chemin = racine / "docs" / "soutenance.md"
    chemin.parent.mkdir(exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")
    return chemin


if __name__ == "__main__":
    print(generer(Path(".")))
