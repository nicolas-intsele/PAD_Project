"""
Commande de gestion : peuple la base avec des données de test réalistes
pour permettre de tester immédiatement le module d'analyse multidimensionnelle.

Usage ::

    python manage.py peupler_donnees_test
    python manage.py peupler_donnees_test --annees 2025 2026
    python manage.py peupler_donnees_test --vider          # repart de zéro

Crée :
  - 4 terminaux avec 2-3 postes chacun
  - 5 types de navires, 8 compagnies, 6 agents maritimes
  - 15 navires
  - ~300 escales réparties sur la période demandée
  - Les axes d'analyse AxeAnalyse (idempotent)
  - 4 cubes d'analyse pré-configurés
  - Les KPI calculés pour chaque mois avec données
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone

from apps.escales.models import Escale
from apps.referentiel.models import (
    AgentMaritime,
    Calendrier,
    CompagnieMaritime,
    Navire,
    Poste,
    Terminal,
    TypeNavire,
)
from apps.analytics.models import AxeAnalyse, CubeAnalyse

TZ = timezone.utc

# ── Référentiels de base ──────────────────────────────────────────────────────

TERMINAUX = [
    {"nom": "Terminal à Conteneurs", "specialite": "conteneurs"},
    {"nom": "Terminal Pétrolier", "specialite": "hydrocarbures"},
    {"nom": "Terminal Polyvalent", "specialite": "marchandises diverses"},
    {"nom": "Terminal Minéralier", "specialite": "vrac solide"},
]

QUAIS_PAR_TERMINAL = {
    "Terminal à Conteneurs": ["Poste C1", "Poste C2", "Poste C3"],
    "Terminal Pétrolier": ["Poste P1", "Poste P2"],
    "Terminal Polyvalent": ["Poste PV1", "Poste PV2"],
    "Terminal Minéralier": ["Poste M1", "Poste M2"],
}

TYPES_NAVIRES = [
    "Porte-conteneurs",
    "Vraquier",
    "Pétrolier",
    "Cargo général",
    "Roulier",
]

COMPAGNIES = [
    "Maersk Line",
    "MSC Mediterranean",
    "CMA CGM",
    "Bolloré Transport",
    "SEALINK Africa",
    "Delmas",
    "Grimaldi Lines",
    "SITL Douala",
]

AGENTS = [
    "SAGA Cameroun",
    "GETMA",
    "Transcap",
    "SOCOPAO",
    "Maritime Services Co",
    "PAD Logistique",
]

NOMS_NAVIRES = [
    ("MV Wouri Express", "9245130", "Porte-conteneurs", "Maersk Line"),
    ("MV Dibamba Star", "9301420", "Porte-conteneurs", "MSC Mediterranean"),
    ("MT Mungo Spirit", "9187654", "Pétrolier", "SEALINK Africa"),
    ("MV Sanaga Trader", "9412301", "Vraquier", "CMA CGM"),
    ("MV Bénoué Carrier", "9523710", "Cargo général", "Bolloré Transport"),
    ("MV Kribi Pride", "9634821", "Roulier", "Grimaldi Lines"),
    ("MT Logbaba Tanker", "9745932", "Pétrolier", "SEALINK Africa"),
    ("MV Littoral Breeze", "9856043", "Vraquier", "Delmas"),
    ("MV Atlantic Voyager", "9967154", "Porte-conteneurs", "CMA CGM"),
    ("MV Gulf of Guinea", "9078265", "Cargo général", "SITL Douala"),
    ("MV Douala Bay", "9189376", "Porte-conteneurs", "Maersk Line"),
    ("MT Elf Petroleum", "9290487", "Pétrolier", "SEALINK Africa"),
    ("MV Congo Express", "9301598", "Vraquier", "Bolloré Transport"),
    ("MV Abidjan Trader", "9412609", "Roulier", "Grimaldi Lines"),
    ("MV Lagos Star", "9523710", "Cargo général", "MSC Mediterranean"),
]


def _dt(annee: int, mois: int, jour: int, heure: int = 8, minute: int = 0) -> datetime:
    return datetime(annee, mois, jour, heure, minute, tzinfo=TZ)


class Command(BaseCommand):
    help = "Peuple la base avec des données de test pour le module d'analyse multidimensionnelle"

    def add_arguments(self, parser):
        parser.add_argument(
            "--annees",
            nargs="+",
            type=int,
            default=[2025, 2026],
            help="Années à couvrir (défaut : 2025 2026)",
        )
        parser.add_argument(
            "--vider",
            action="store_true",
            help="Supprime toutes les escales existantes avant de peupler",
        )
        parser.add_argument(
            "--nb-escales",
            type=int,
            default=300,
            help="Nombre d'escales à générer (défaut : 300)",
        )

    def handle(self, *args, **options):
        random.seed(42)  # résultats reproductibles

        if options["vider"]:
            nb = Escale.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(f"  {nb} escales supprimées."))

        self.stdout.write("─" * 60)
        self.stdout.write("  Création du référentiel...")
        terminaux, postes_map = self._creer_referentiel()

        self.stdout.write("  Création des navires...")
        navires = self._creer_navires()

        self.stdout.write("  Génération des escales...")
        agents = {a: AgentMaritime.objects.get_or_create(nom=a)[0] for a in AGENTS}
        nb = self._generer_escales(
            navires, postes_map, agents, options["annees"], options["nb_escales"]
        )
        self.stdout.write(self.style.SUCCESS(f"  ✓ {nb} escales créées/mises à jour."))

        self.stdout.write("  Configuration des axes et cubes d'analyse...")
        self._creer_axes_et_cubes()
        self.stdout.write(self.style.SUCCESS("  ✓ Axes et cubes configurés."))

        self.stdout.write("  Calcul des KPI mensuels...")
        self._calculer_kpi()
        self.stdout.write(self.style.SUCCESS("  ✓ KPI calculés."))

        self.stdout.write("─" * 60)
        self.stdout.write(self.style.SUCCESS(
            "\nBase peuplée. Vous pouvez maintenant tester l'API analytics :\n"
            "  GET  http://localhost:8000/api/analytics/axes/\n"
            "  GET  http://localhost:8000/api/analytics/mesures/\n"
            "  POST http://localhost:8000/api/analytics/cube/executer/\n"
            "  GET  http://localhost:8000/api/analytics/tendance/?mesure=nb_escales"
            "&date_debut=2025-01-01&date_fin=2026-06-30&granularite=mois\n"
            "  GET  http://localhost:8000/api/analytics/synthese/?date_debut=2026-01-01&date_fin=2026-06-30\n"
        ))

    # ── Référentiel ────────────────────────────────────────────────────────────

    def _creer_referentiel(self):
        terminaux = {}
        postes_map = {}
        for t_data in TERMINAUX:
            terminal, _ = Terminal.objects.get_or_create(
                nom=t_data["nom"], defaults={"specialite": t_data["specialite"]}
            )
            terminaux[t_data["nom"]] = terminal
            for q_nom in QUAIS_PAR_TERMINAL[t_data["nom"]]:
                poste, _ = Poste.objects.get_or_create(
                    nom=q_nom,
                    terminal=terminal,
                    defaults={
                        "longueur": random.uniform(150, 400),
                        "tirant_eau_max": random.uniform(8, 16),
                    },
                )
                postes_map[q_nom] = poste
        return terminaux, postes_map

    def _creer_navires(self):
        navires = []
        for nom, imo, type_lib, compagnie_rs in NOMS_NAVIRES:
            type_nav, _ = TypeNavire.objects.get_or_create(libelle=type_lib)
            compagnie, _ = CompagnieMaritime.objects.get_or_create(raison_sociale=compagnie_rs)
            navire, _ = Navire.objects.get_or_create(
                imo=imo,
                defaults={
                    "nom": nom,
                    "type_navire": type_nav,
                    "compagnie": compagnie,
                    "pavillon": random.choice(["CM", "SN", "BJ", "GN", "CI", "NG", "ML"]),
                    "longueur": random.uniform(100, 380),
                    "jauge_brute": random.uniform(5000, 160000),
                },
            )
            navires.append(navire)
        return navires

    # ── Escales ───────────────────────────────────────────────────────────────

    def _generer_escales(self, navires, postes_map, agents, annees, nb_total):
        postes = list(postes_map.values())
        agents_list = list(agents.values())

        # Pondérations : les conteneurs plus fréquents
        poste_poids = []
        for q in postes:
            if "C" in q.nom:
                poste_poids.append(4)
            elif "P" in q.nom:
                poste_poids.append(2)
            else:
                poste_poids.append(1)

        # Générer les dates de départ sur toute la période
        debut_global = datetime(min(annees), 1, 1, tzinfo=TZ)
        fin_global = datetime(max(annees), 6, 30, 23, 59, tzinfo=TZ)
        duree_totale_jours = (fin_global - debut_global).days

        nb_crees = 0
        for i in range(nb_total):
            # Date d'arrivée aléatoire dans la période
            offset_jours = random.randint(0, duree_totale_jours)
            heure_arrivee = random.randint(0, 23)
            date_arrivee = debut_global + timedelta(days=offset_jours, hours=heure_arrivee)

            navire = random.choice(navires)
            poste = random.choices(postes, weights=poste_poids)[0]
            agent = random.choice(agents_list)

            # Temps d'attente : 0-72h (log-normal centré sur 12h)
            attente_h = max(0, random.lognormvariate(2.0, 0.8))
            attente_h = min(attente_h, 96)
            date_accostage = date_arrivee + timedelta(hours=attente_h)

            # Durée à poste : 4-120h selon le type de navire
            sejour_poste_h = max(4, random.lognormvariate(3.2, 0.6))
            sejour_poste_h = min(sejour_poste_h, 168)
            date_appareillage = date_accostage + timedelta(hours=sejour_poste_h)

            # Temps de pilotage : 1-4h
            pilotage_h = random.uniform(0.5, 4.0)
            date_depart = date_appareillage + timedelta(hours=random.uniform(0.5, 2.0))

            # Tonnages selon le type de navire
            t_lib = navire.type_navire.libelle
            if "Conteneurs" in t_lib or "conteneurs" in t_lib:
                tdb = random.uniform(1000, 15000)
                temb = random.uniform(800, 12000)
            elif "Vraquier" in t_lib:
                tdb = random.uniform(5000, 50000)
                temb = 0
            elif "Pétrolier" in t_lib:
                tdb = random.uniform(10000, 80000)
                temb = 0
            else:
                tdb = random.uniform(200, 5000)
                temb = random.uniform(100, 3000)

            # Statut
            if date_depart < dj_timezone.now():
                statut = Escale.Statut.TERMINEE
            elif date_accostage < dj_timezone.now():
                statut = Escale.Statut.EN_COURS
            else:
                statut = Escale.Statut.PLANIFIEE

            date_ref = Calendrier.get_or_create_from_date(date_arrivee.date())

            temps_attente = round(attente_h, 2)
            temps_sejour = round((date_depart - date_arrivee).total_seconds() / 3600, 2)

            escale, created = Escale.objects.update_or_create(
                navire=navire,
                poste=poste,
                date_arrivee=date_arrivee,
                defaults={
                    "agent": agent,
                    "date_ref": date_ref,
                    "date_accostage": date_accostage,
                    "date_appareillage": date_appareillage,
                    "date_depart": date_depart,
                    "statut": statut,
                    "temps_attente": temps_attente,
                    "temps_sejour": temps_sejour,
                    "temps_pilotage": round(pilotage_h, 2),
                    "temps_accostage": round(min(attente_h, 4), 2),
                    "tonnage_debarque": round(tdb, 2),
                    "tonnage_embarque": round(temb, 2),
                },
            )
            nb_crees += 1

        return nb_crees

    # ── Axes et cubes ─────────────────────────────────────────────────────────

    def _creer_axes_et_cubes(self):
        # Créer les 9 axes disponibles
        for code, libelle in AxeAnalyse.Type.choices:
            AxeAnalyse.objects.get_or_create(code=code, defaults={"libelle": libelle})

        # 4 cubes pré-configurés utiles
        axe_terminal = AxeAnalyse.objects.get(code=AxeAnalyse.Type.TERMINAL)
        axe_mois = AxeAnalyse.objects.get(code=AxeAnalyse.Type.TEMPS_MOIS)
        axe_type_navire = AxeAnalyse.objects.get(code=AxeAnalyse.Type.TYPE_NAVIRE)
        axe_compagnie = AxeAnalyse.objects.get(code=AxeAnalyse.Type.COMPAGNIE)
        axe_trimestre = AxeAnalyse.objects.get(code=AxeAnalyse.Type.TEMPS_TRIMESTRE)

        cubes = [
            {
                "nom": "Escales par terminal et par mois",
                "mesure": CubeAnalyse.Mesure.NB_ESCALES,
                "axe_ligne": axe_terminal,
                "axe_colonne": axe_mois,
                "description": "Nombre d'escales ventilées par terminal (lignes) et par mois (colonnes).",
            },
            {
                "nom": "Temps d'attente moyen par type de navire",
                "mesure": CubeAnalyse.Mesure.TEMPS_ATTENTE_MOY,
                "axe_ligne": axe_type_navire,
                "axe_colonne": axe_trimestre,
                "description": "Temps d'attente moyen (heures) par type de navire et trimestre.",
            },
            {
                "nom": "Tonnage total par compagnie",
                "mesure": CubeAnalyse.Mesure.TONNAGE_TOTAL,
                "axe_ligne": axe_compagnie,
                "axe_colonne": None,
                "description": "Tonnage total manutentionné par compagnie maritime.",
            },
            {
                "nom": "Taux d'occupation par terminal et trimestre",
                "mesure": CubeAnalyse.Mesure.TAUX_OCCUPATION,
                "axe_ligne": axe_terminal,
                "axe_colonne": axe_trimestre,
                "description": "Taux d'occupation des postes (%) par terminal et trimestre.",
            },
        ]

        for c in cubes:
            CubeAnalyse.objects.get_or_create(
                nom=c["nom"],
                defaults={
                    "mesure": c["mesure"],
                    "axe_ligne": c["axe_ligne"],
                    "axe_colonne": c["axe_colonne"],
                    "description": c["description"],
                    "actif": True,
                },
            )

    # ── KPI ───────────────────────────────────────────────────────────────────

    def _calculer_kpi(self):
        from apps.kpi.engine.service import calculer_toutes_les_periodes, garantir_catalogue
        garantir_catalogue()
        resultats = calculer_toutes_les_periodes()
        self.stdout.write(f"    {len(resultats)} période(s) calculée(s).")
