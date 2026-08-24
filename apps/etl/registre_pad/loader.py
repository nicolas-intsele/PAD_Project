"""
Chargement des escales du registre mensuel réel du PAD dans l'entrepôt de données.

Contrairement au chargeur générique (apps.etl.loader.EscaleLoader), celui-ci
résout le navire en priorité via le référentiel DONNEES DES NAVIRES (100% de
correspondance constatée sur le fichier fourni), et le quai/terminal via la
table de correspondance POSTE -> SPECIALITE de l'onglet AUTRES DONNEES.
"""
from __future__ import annotations

import pandas as pd
from django.db import transaction
from django.utils import timezone

from apps.escales.models import Escale
from apps.referentiel.models import AgentMaritime, Calendrier, CompagnieMaritime, Navire, Quai, Terminal, TypeNavire

from .dateutils import parser_date_intelligent


def _parser_date(valeur):
    parsed = parser_date_intelligent(valeur)
    if parsed is None:
        return None
    dt = parsed.to_pydatetime()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_default_timezone())
    return dt


def _parser_decimal(valeur):
    if valeur is None or pd.isna(valeur) or str(valeur).strip() == "":
        return None
    try:
        return float(str(valeur).replace(",", "."))
    except ValueError:
        return None


def _duree_heures(debut, fin):
    if debut is None or fin is None:
        return None
    heures = (fin - debut).total_seconds() / 3600
    return round(heures, 2) if heures >= 0 else None


class ReferentielCache:
    """Précharge les référentiels Navire/Quai/Terminal pour éviter le N+1 sur un import volumineux."""

    def __init__(self, df_navires_ref: pd.DataFrame, df_quais_ref: pd.DataFrame):
        self._navires_ref = {
            str(row["navire"]).strip().upper(): row for _, row in df_navires_ref.iterrows()
        }
        self._quais_ref = {
            str(row["poste"]).strip().upper(): str(row["specialite"]).strip() for _, row in df_quais_ref.iterrows()
        }
        self._terminaux_cache = {}
        self._quais_cache = {}
        self._navires_cache = {}
        self._compagnies_cache = {}
        self._types_navire_cache = {}
        self._agents_cache = {}

    def resoudre_quai(self, code_poste: str) -> Quai:
        code = str(code_poste).strip().upper()
        if code in self._quais_cache:
            return self._quais_cache[code]

        nom_terminal = self._quais_ref.get(code, "Non spécifié")
        if nom_terminal not in self._terminaux_cache:
            self._terminaux_cache[nom_terminal], _ = Terminal.objects.get_or_create(
                nom=nom_terminal, defaults={"specialite": nom_terminal}
            )
        terminal = self._terminaux_cache[nom_terminal]

        quai, _ = Quai.objects.get_or_create(nom=code, terminal=terminal)
        self._quais_cache[code] = quai
        return quai

    def resoudre_navire(self, nom_navire: str, ligne_escale: dict) -> Navire:
        cle = str(nom_navire).strip().upper()
        if cle in self._navires_cache:
            return self._navires_cache[cle]

        ref = self._navires_ref.get(cle)
        ref_dict = ref.to_dict() if ref is not None else {}

        armateur = (ref["armateur"] if ref is not None and pd.notna(ref.get("armateur")) else None) \
            or ligne_escale.get("armateur") or "Armateur non renseigné"
        armateur = str(armateur).strip() or "Armateur non renseigné"
        if armateur not in self._compagnies_cache:
            self._compagnies_cache[armateur], _ = CompagnieMaritime.objects.get_or_create(raison_sociale=armateur)
        compagnie = self._compagnies_cache[armateur]

        type_navire = (ref["type_navire"] if ref is not None and pd.notna(ref.get("type_navire")) else None) \
            or ligne_escale.get("type_navire") or "Non renseigné"
        type_navire = str(type_navire).strip() or "Non renseigné"
        if type_navire not in self._types_navire_cache:
            self._types_navire_cache[type_navire], _ = TypeNavire.objects.get_or_create(libelle=type_navire)
        type_navire_obj = self._types_navire_cache[type_navire]

        imo = None
        if ref is not None and pd.notna(ref.get("imo")):
            try:
                imo = str(int(float(ref["imo"])))
            except (ValueError, TypeError):
                imo = str(ref["imo"]).strip()

        navire, _ = Navire.objects.update_or_create(
            nom=str(nom_navire).strip(),
            defaults={
                "imo": imo,
                "pavillon": str(ref_dict.get("pavillon") or ligne_escale.get("pavillon") or "") or "",
                "longueur": _parser_decimal(ref_dict.get("longueur")) or _parser_decimal(ligne_escale.get("longueur")),
                "jauge_brute": _parser_decimal(ref_dict.get("jauge_brute")) or _parser_decimal(ligne_escale.get("jauge_brute")),
                "type_navire": type_navire_obj,
                "compagnie": compagnie,
            },
        )
        self._navires_cache[cle] = navire
        return navire

    def resoudre_agent(self, nom_agent) -> AgentMaritime:
        nom = str(nom_agent).strip() if nom_agent and pd.notna(nom_agent) else "Consignataire non renseigné"
        if nom not in self._agents_cache:
            self._agents_cache[nom], _ = AgentMaritime.objects.get_or_create(nom=nom)
        return self._agents_cache[nom]


class RegistrePADLoader:
    def __init__(self, cache: ReferentielCache, journal_import=None):
        self.cache = cache
        self.journal_import = journal_import

    def charger(self, df: pd.DataFrame, lignes_ignorees: set[int] | None = None):
        lignes_ignorees = lignes_ignorees or set()
        nb_chargees = 0
        erreurs = []

        for idx, row in df.iterrows():
            numero_ligne = int(row["ligne_source"])
            if numero_ligne in lignes_ignorees:
                continue
            try:
                with transaction.atomic():
                    self._charger_ligne(row)
                nb_chargees += 1
            except Exception as exc:  # noqa: BLE001
                erreurs.append({"ligne": numero_ligne, "message": f"{type(exc).__name__}: {exc}"})

        return nb_chargees, erreurs

    def _charger_ligne(self, row) -> Escale:
        quai = self.cache.resoudre_quai(row["poste"])
        navire = self.cache.resoudre_navire(row["navire"], row)
        agent = self.cache.resoudre_agent(row.get("consignataire"))

        arrivee_rade = _parser_date(row.get("arrivee_rade"))
        arrivee_poste = _parser_date(row.get("arrivee_poste"))
        pilote_a_bord_arrivee = _parser_date(row.get("pilote_a_bord_arrivee"))
        pilote_a_bord_depart = _parser_date(row.get("pilote_a_bord_depart"))
        navire_appareille = _parser_date(row.get("navire_appareille"))
        pilote_debarque_depart = _parser_date(row.get("pilote_debarque_depart"))

        date_ref = Calendrier.get_or_create_from_date(arrivee_rade.date())

        # Départ effectif du port : dernier événement disponible dans la séquence
        # (débarquement du pilote au départ), à défaut l'appareillage du navire.
        date_depart = pilote_debarque_depart or navire_appareille

        # Temps de pilotage = somme des fenêtres pilote-à-bord à l'arrivée et au départ.
        temps_pilotage = None
        parts = []
        if pilote_a_bord_arrivee and arrivee_poste:
            parts.append(_duree_heures(pilote_a_bord_arrivee, arrivee_poste))
        if pilote_a_bord_depart and pilote_debarque_depart:
            parts.append(_duree_heures(pilote_a_bord_depart, pilote_debarque_depart))
        parts = [p for p in parts if p is not None]
        if parts:
            temps_pilotage = round(sum(parts), 2)

        # Temps d'accostage = durée de la seule manœuvre d'entrée (pilote à bord -> à quai).
        temps_accostage = _duree_heures(pilote_a_bord_arrivee, arrivee_poste)

        statut = Escale.Statut.TERMINEE if date_depart else (
            Escale.Statut.EN_COURS if arrivee_poste else Escale.Statut.PLANIFIEE
        )

        escale, _ = Escale.objects.update_or_create(
            navire=navire, quai=quai, date_arrivee=arrivee_rade,
            defaults={
                "agent": agent,
                "date_ref": date_ref,
                "date_accostage": arrivee_poste,
                "date_appareillage": navire_appareille,
                "date_depart": date_depart,
                "temps_pilotage": temps_pilotage,
                "temps_accostage": temps_accostage,
                "statut": statut,
                "import_source": self.journal_import,
            },
        )
        escale.temps_attente = escale.calculer_temps_attente()
        escale.temps_sejour = escale.calculer_duree_sejour()
        escale.save(update_fields=["temps_attente", "temps_sejour"])
        return escale
