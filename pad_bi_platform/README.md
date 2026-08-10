# Plateforme décisionnelle — Opérations navires du Port Autonome de Douala (PAD)

Conception et développement d'une plateforme décisionnelle pour l'analyse des
performances des opérations navires — mémoire de fin d'études.

## État d'avancement

| Module (cahier des charges)                  | Statut               |
|-----------------------------------------------|----------------------|
| 1. Collecte et intégration des données (ETL)  | ✅ Développé et testé |
| 2. Entrepôt de données (Data Warehouse)        | ✅ Modèles Django créés |
| 3. Calcul automatique des KPI                  | ⏳ À venir |
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

### Import en ligne de commande

```bash
python manage.py import_fichier data/samples/escales_exemple.csv
python manage.py import_fichier data/samples/escales_exemple.xlsx --format excel
```

Le pipeline exécute successivement :

1. **Extraction** (`apps/etl/importers/`) — lecture du fichier CSV ou Excel en DataFrame pandas
2. **Contrôle qualité** (`apps/etl/validators.py`) — colonnes obligatoires, valeurs manquantes,
   formats de date, doublons, cohérence des dates (bloquant ou avertissement)
3. **Transformation** (`apps/etl/transformers.py`) — normalisation des textes, dates, décimales
4. **Chargement** (`apps/etl/loader.py`) — résolution/création des dimensions et de la table
   de faits `Escale`, avec calcul immédiat des temps caractéristiques
5. **Historisation** (`apps/etl/models.py::JournalImport`) — traçabilité complète de chaque import

### Import via l'API REST

```
POST /api/etl/import/          (multipart/form-data : fichier, format)
GET  /api/etl/imports/         (historique des imports — lecture seule)
```

Réservé aux comptes administrateur (`IsAdminUser`).

### Format de fichier attendu

Colonnes obligatoires : `navire_imo, navire_nom, type_navire, compagnie,
agent_maritime, quai, terminal, date_arrivee`.
Colonnes optionnelles : `pavillon, longueur_navire, jauge_brute, date_accostage,
date_appareillage, date_depart, statut`.

Un exemple complet (avec anomalies volontaires pour tester le contrôle qualité)
est fourni dans `data/samples/escales_exemple.csv`.

## Tests

```bash
python manage.py test apps.etl -v 2
```

14 tests couvrent les importeurs, le contrôleur qualité, les transformateurs
et le pipeline d'intégration complet (`run_import`).

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
