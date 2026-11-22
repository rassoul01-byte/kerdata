# Auto-évaluation contre la grille (compétence 10)

Chaque case est cochée **par le code** (`src/kerdata/grille.py`, rejouable) à partir des fichiers livrés.

**Bilan : 55/55 critères vérifiés.** Critères éliminatoires : **5/5**.
Aucun critère en échec.

### A. Conformité du rendu (10 %) — 10/10 critères vérifiés

|  | bloc | critère | points | preuve |
|---|---|---|---|---|
| ✅ | A | joblib présent et rechargeable | éliminatoire | 5501 octets ; rechargé dans un interpréteur neuf, prédictions identiques sur 120 lignes |
| ✅ | A | notebook exécutable de bout en bout | éliminatoire | 24 cellules, 14 de code exécutées, 0 erreur ; ré-exécuté avec succès sur un clone neuf |
| ✅ | A | justifications.md présent, ≥ 1 entrée par décision | éliminatoire | 98 décisions numérotées |
| ✅ | A | sources/ et referentiels/ non modifiés | éliminatoire | 9 fichiers identiques à l'archive d'origine (SHA-256) |
| ✅ | A | sortie/ : propres, quarantaine, avertissements | éliminatoire | 2872 propres, 111 avertissements, 201 en quarantaine |
| ✅ | A | Tous les livrables présents | 3 | 17/17 présents |
| ✅ | A | Notebook exécutable sans erreur | 3 | 14 cellules de code, 0 erreur, 9 figures |
| ✅ | A | Reproductibilité (graine fixée, mêmes scores) | 2 | graine 42 ; empreintes de coefficients et de prédictions identiques sur 2 exécutions ; clone neuf : 0 fichier suivi modifié |
| ✅ | A | Format des CSV respecté | 1 | 62 CSV lus avec en-tête, UTF-8, séparateur virgule ; illisibles : aucun |
| ✅ | A | Nomenclature des fichiers respectée | 1 | donnees_propres.csv, avertissements.csv, quarantine.csv (copie quarantaine.csv), pipeline_preparation.joblib, 02_preparation_analyse.ipynb |

### B. Compétences techniques (55 %) — 36/36 critères vérifiés

|  | bloc | critère | points | preuve |
|---|---|---|---|---|
| ✅ | B1 | Types corrects par source | 2 | 55 lignes (5 sources × 11 champs) |
| ✅ | B1 | Skew chiffré | 2 | ventes : skew 1.86 → -0.22 (log) |
| ✅ | B1 | Choix de cible justifié | 1 | décision 1.8 (log(prix) sur les ventes) |
| ✅ | B2 | 3 à 5 insights actionnables | 2 | 5 insights |
| ✅ | B2 | Tests statistiques (ANOVA, khi2, Mann-Kendall) | 2 | comp2_d7_tests_croises.csv, comp2_d6_robustesse.csv |
| ✅ | B2 | Simpson testé | 1 | corrélation globale vs par catégorie |
| ✅ | B2 | Qualité par source | 1 | comp2_d8_qualite_par_source.csv |
| ✅ | B3 | 3 fichiers produits | 3 | 2872 + 111 + 201 = 3184 lignes (aucune perdue) |
| ✅ | B3 | 6 mesures obligatoires produites | 3 | tableau des 6 mesures dans rapport_qualite.md |
| ✅ | B3 | Mécanisme des manquants par source | 2 | 14 couples (source, champ) avec mécanisme et traitement |
| ✅ | B3 | Mojibake corrigé sur historique | 2 | 0 caractère « � » dans les fichiers livrés ; 1407 lignes corrigées, journal avant → après |
| ✅ | B3 | Header dupliqué filtré sur plateforme | 1 | ligne d'en-tête (ligne 575) absente des 4 fichiers |
| ✅ | B3 | Doublons d'ID arbitrés | 1 | 15 doublons exacts → quarantaine, 1re occurrence conservée |
| ✅ | B4 | V1 à V6 produites | 3 | 6 figures dans reports/figures/ |
| ✅ | B4 | Conclusions chiffrées | 2 | 6 conclusions, chacune avec ses chiffres |
| ✅ | B4 | Lien avec la comp 3 (décisions justifiées) | 1 | tableau {figure, question, décision comp 3} |
| ✅ | B5 | Tableau de décision par variable | 2 | 13 variables |
| ✅ | B5 | statut audité et décidé | 2 | décisions 5.1 et 8.3 : exclu, fuite types 2 et 4 |
| ✅ | B5 | source auditée et décidée | 1 | décisions 5.2, 8.4 : exclue, type 4 |
| ✅ | B5 | commune exclue ou frequency justifié | 1 | décision 5.3 + frequency encoding testé en comp 6 |
| ✅ | B5 | Preuve non-fuite (moyenne val ≠ 0) | 2 | annee : moyenne train -0.0000, validation -0.0030 |
| ✅ | B6 | 3 à 5 candidates créées, gains chiffrés | 2 | 4 candidates créées, 15 mesurées en CV 5 plis |
| ✅ | B6 | Test de fuite documenté | 2 | prix_m2 + surface_log : R² = 1.0000 |
| ✅ | B6 | source testée | 2 | gain -0.0015 |
| ✅ | B7 | Mann-Kendall | 1 | 3 échelles, p > 0,05 |
| ✅ | B7 | Stratification par catégorie | 1 | stratifié categorie + source, écart 0,47 point |
| ✅ | B7 | Vérification par source | 1 | écart par source 0,60 point |
| ✅ | B7 | Graine fixée et test scellé | 1 | graine 42 ; empreinte SHA-256 du test vérifiée (intact) |
| ✅ | B8 | Les 4 types audités | 2 | 24 lignes d'audit couvrant les types 1 à 4 |
| ✅ | B8 | prix_m2 testé et exclu | 1 | exclue : fuite type 1 |
| ✅ | B8 | statut audité | 1 | exclu : fuite type 2 |
| ✅ | B8 | source auditée | 1 | exclue : type 4 |
| ✅ | B8 | Colonnes mono-source retirées | 1 | quartier, description, date_expiration, pieces, commercial, devise : absentes des 4 fichiers |
| ✅ | B9 | 6 vérifications documentées | 2 | comp9_verification_1 à 6 |
| ✅ | B9 | Sérialisation testée | 1 | rechargement en interpréteur neuf, écart 0 |
| ✅ | B9 | Cohérence multi-source | 1 | 5 sources, 100 % des modalités connues |

### C. Documentation (15 %) — 5/5 critères vérifiés

|  | bloc | critère | points | preuve |
|---|---|---|---|---|
| ✅ | C | Chaque décision a une preuve chiffrée | 6 | 98/98 décisions avec chiffre |
| ✅ | C | Décisions de nettoyage tracées (corrigé, quarantaine, averti) | 3 | 14/14 décisions de la comp 3 portent leur traitement explicite ([CORRIGÉ], [QUARANTAINE], [AVERTISSEMENT]…) ; corrections réversibles via journal_corrections.csv |
| ✅ | C | Test de fuite de comp 6 documenté | 2 | décision 6.6 (R² = 0,9999) |
| ✅ | C | Toutes les features utilisées sont documentées | 2 | ['categorie', 'region', 'surface_log'] dans dictionnaire_features.csv (16 lignes) |
| ✅ | C | Type, transformation, justification par feature | 2 | colonnes renseignées pour les 16 lignes |

### D. Rapport final (10 %) — 3/3 critères vérifiés

|  | bloc | critère | points | preuve |
|---|---|---|---|---|
| ✅ | D | Structure en 7 sections | 10 | introduction → conclusion |
| ✅ | D | Figures avec conclusions | 2 | 10 figures, 10 conclusions |
| ✅ | D | Limites reconnues | 1 | 7 limites listées |

### E. Soutenance (10 %) — 1/1 critères vérifiés

|  | bloc | critère | points | preuve |
|---|---|---|---|---|
| ✅ | E | Support de soutenance prêt | 10 | docs/soutenance.md (questions, réponses chiffrées, question piège sur `source`) |

## Ce que le code ne peut pas juger

- **Lisibilité des figures** (axes, unités, titres) : vérifiée à l'œil à chaque génération, non automatisable.
- **Soutenance orale (10 %)** : seul le support est vérifié (`docs/soutenance.md`) ; la défense dépend de la personne.
- **Pondération réelle** : la grille donne des points par critère mais la note finale dépend du correcteur ; ce document ne la prédit pas.
