# Plateforme décisionnelle — Opérations navires du Port Autonome de Douala (PAD)

Conception et développement d'une plateforme décisionnelle pour l'analyse des
performances des opérations navires — mémoire de fin d'études.

## État d'avancement

| Module (cahier des charges)                  | Statut               |
|-----------------------------------------------|----------------------|
| 1. Collecte et intégration des données (ETL)  | ✅ Développé et testé (gabarit générique + registre PAD réel) |
| 2. Entrepôt de données (Data Warehouse)        | ✅ Modèles Django créés |
| 3. Calcul automatique des KPI                  | ✅ KPI de base implémentés |
| 4. Analyse multidimensionnelle                 | ⏳ À venir |
| 5. Tableaux de bord décisionnels               | ⏳ À venir |
| 6. Alertes et aide à la décision               | ⏳ À venir |
| 7. Reporting                                   | ⏳ À venir |
| 8. Administration                              | ⏳ À venir (modèles utilisateur/rôle en place) |

## Stack technique

Python 3.12 · Django 5/6 · Django REST Framework · PostgreSQL · pandas ·
openpyxl · SQLAlchemy · Celery/Redis · Docker.

## Installation locale (sans Docker — développement rapide)

```bash
python -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate
pip install -r requirements/dev.txt

python manage.py migrate          # utilise SQLite par défaut si POSTGRES_DB n'est pas défini
python manage.py createsuperuser
python manage.py runserver
```

## Installation avec Docker (environnement complet)

```bash
cp .env.example .env              # ajuster les valeurs si besoin
docker compose up --build
```

Services démarrés : `db` (PostgreSQL), `redis`, `web` (Django/Gunicorn),
`celery_worker`, `celery_beat`, `nginx` (reverse proxy sur le port 80).

## Module ETL — utilisation

Le projet propose **deux pipelines ETL** :
- un pipeline **générique** (`apps/etl/services.py`) pour tout fichier CSV/Excel
  respectant le gabarit ci-dessous ;
- un pipeline **dédié** (`apps/etl/registre_pad/`) au classeur officiel de
  collecte de données navires du PAD, dont le format réel (feuilles mensuelles,
  référentiels intégrés) diffère significativement du gabarit générique.

### Import générique (CSV / Excel à une seule table)

```bash
python manage.py import_fichier data/samples/escales_exemple.csv
python manage.py import_fichier data/samples/escales_exemple.xlsx --format excel
```

Colonnes obligatoires : `navire_imo, navire_nom, type_navire, compagnie,
agent_maritime, quai, terminal, date_arrivee`.
Colonnes optionnelles : `pavillon, longueur_navire, jauge_brute, date_accostage,
date_appareillage, date_depart, statut`.

Un exemple complet (avec anomalies volontaires pour tester le contrôle qualité)
est fourni dans `data/samples/escales_exemple.csv`.

### Import du registre mensuel officiel du PAD

```bash
python manage.py import_registre_pad data/samples/COLLECTE_DE_DONNEES_NAVIRES_2026_26062026.xlsx
```

Ce classeur a une structure propre au PAD : un onglet par mois (double en-tête,
données à partir de la ligne 3), un onglet `DONNEES DES NAVIRES` (référentiel
navire avec IMO) et un onglet `AUTRES DONNEES` (correspondance poste ↔ terminal).
Le pipeline dédié (`apps/etl/registre_pad/`) gère :
- la concaténation des onglets mensuels non vides (les mois futurs sans
  données, ex. juillet à décembre dans le fichier fourni, sont ignorés) ;
- la résolution du navire (par nom, avec repli sur les colonnes de la feuille
  mensuelle si le référentiel est incomplet) et du terminal (via la
  correspondance poste → spécialité) ;
- le calcul du temps de pilotage (arrivée + départ) et du temps de manœuvre
  d'accostage, en plus des temps d'attente et de séjour standards ;
- la détection des anomalies de dates (formats invalides, doublons inter-
  mensuels, incohérences chronologiques). **Aucune durée négative n'est
  jamais persistée** : lorsque les dates sources sont incohérentes (ex. départ
  antérieur à l'arrivée, erreur de saisie), le temps correspondant est mis à
  `NULL` plutôt que de fausser les futurs calculs de KPI, et l'anomalie reste
  visible dans `JournalImport.erreurs`.

Ce pipeline est également disponible via l'API : `POST /api/etl/import/` avec
`format=registre_pad`.

### Import via l'API REST (les deux pipelines)

```
POST /api/etl/import/          (multipart/form-data : fichier, format=csv|excel|registre_pad)
GET  /api/etl/imports/         (historique des imports — lecture seule)
```

Réservé aux comptes administrateur (`IsAdminUser`).

## Tests

```bash
python manage.py test apps.etl apps.etl.registre_pad -v 2
```

28 tests couvrent les deux pipelines ETL, le contrôleur qualité, les
transformateurs, et une garde-fou de non-régression sur le calcul des durées
(temps d'attente/séjour jamais négatifs). Les tests spécifiques au registre
PAD réel sont automatiquement ignorés (skip) si le fichier
`data/samples/COLLECTE_DE_DONNEES_NAVIRES_2026_26062026.xlsx` n'est pas présent.

## Arborescence

Voir la structure complète du projet dans `docs/` (cahier des charges,
diagrammes UML, MCD/MLD/MPD) — cohérente avec l'arborescence proposée en
amont du développement.

## Prochaines étapes

- Module 3 : moteur de calcul des KPI (`apps/kpi/`)
- Module 4 : analyse multidimensionnelle (`apps/analytics/`)
- Module 5 : tableaux de bord (`apps/dashboard/`)
- Module 6 : alertes (`apps/alerts/`)
- Module 7 : reporting PDF/Excel (`apps/reporting/`)
