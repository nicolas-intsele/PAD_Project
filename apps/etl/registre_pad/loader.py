"""
Chargement des escales du registre mensuel réel du PAD dans l'entrepôt de données.

Contrairement au chargeur générique (apps.etl.loader.EscaleLoader), celui-ci
résout le navire en priorité via le référentiel DONNEES DES NAVIRES (100% de
correspondance constatée sur le fichier fourni), et le poste/terminal via la
table de correspondance POSTE -> SPECIALITE de l'onglet AUTRES DONNEES.
"""
from __future__ import annotations

import pandas as pd
from django.db import transaction
from django.utils import timezone

from apps.escales.models import Escale
from apps.referentiel.models import AgentMaritime, Calendrier, CompagnieMaritime, Navire, Poste, Terminal, TypeNavire

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
    """Précharge les référentiels Navire/Poste/Terminal pour éviter le N+1 sur un import volumineux."""

    def __init__(self, df_navires_ref: pd.DataFrame, df_quais_ref: pd.DataFrame):
        self._navires_ref = {
            str(row["navire"]).strip().upper(): row for _, row in df_navires_ref.iterrows()
        }
        self._postes_ref = {
            str(row["poste"]).strip().upper(): str(row["specialite"]).strip() for _, row in df_quais_ref.iterrows()
        }
        self._terminaux_cache = {}
        self._postes_cache = {}
        self._navires_cache = {}
        self._compagnies_cache = {}
        self._types_navire_cache = {}
        self._agents_cache = {}

    def resoudre_poste(self, code_poste: str) -> Poste:
        code = str(code_poste).strip().upper()
        if code in self._postes_cache:
            return self._postes_cache[code]

        nom_terminal = self._postes_ref.get(code, "Non spécifié")
        if nom_terminal not in self._terminaux_cache:
            self._terminaux_cache[nom_terminal], _ = Terminal.objects.get_or_create(
                nom=nom_terminal, defaults={"specialite": nom_terminal}
            )
        terminal = self._terminaux_cache[nom_terminal]

        poste, _ = Poste.objects.get_or_create(nom=code, terminal=terminal)
        self._postes_cache[code] = poste
        return poste

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
        poste = self.cache.resoudre_poste(row["poste"])
        navire = self.cache.resoudre_navire(row["navire"], row)
        agent = self.cache.resoudre_agent(row.get("consignataire"))

        # ── Lecture des dates brutes depuis les colonnes du registre PAD ──────
        arrivee_rade          = _parser_date(row.get("arrivee_rade"))           # ARRIVEE RADE
        pilote_a_bord_arrivee = _parser_date(row.get("pilote_a_bord_arrivee"))  # PILOTE A BORD ARRIVEE
        arrivee_poste         = _parser_date(row.get("arrivee_poste"))          # NAVIRE ARRIVEE POSTE
        pilote_debarque_arr   = _parser_date(row.get("pilote_debarque_arrivee"))# PILOTE DEBARQUE ARRIVEE
        navire_appareille     = _parser_date(row.get("navire_appareille"))      # NAVIRE APPAREILLE

        if arrivee_rade is None:
            raise ValueError("arrivee_rade manquant — ligne invalide")

        date_ref = Calendrier.get_or_create_from_date(arrivee_rade.date())

        # ── Mapping vers les champs Escale ────────────────────────────────────
        # date_arrivee    = arrivee_rade          (arrivée en rade)
        # date_accostage  = pilote_a_bord_arrivee (pilote monte à bord → début attente)
        # date_depart     = arrivee_poste         (navire à poste → début séjour)
        # date_appareillage = navire_appareille   (navire appareille → fin séjour)

        # ── Calculs des temps caractéristiques ───────────────────────────────
        # TEMPS_ATTENTE   = pilote_a_bord_arrivee - arrivee_rade
        temps_attente = _duree_heures(arrivee_rade, pilote_a_bord_arrivee)

        # TEMPS_SEJOUR    = navire_appareille - arrivee_poste
        temps_sejour = _duree_heures(arrivee_poste, navire_appareille)

        # TEMPS_PILOTAGE  = arrivee_poste - pilote_a_bord_arrivee
        temps_pilotage = _duree_heures(pilote_a_bord_arrivee, arrivee_poste)

        # TEMPS_ACCOSTAGE = pilote_debarque_arrivee - arrivee_poste
        temps_accostage = _duree_heures(arrivee_poste, pilote_debarque_arr)

        statut = Escale.Statut.TERMINEE if navire_appareille else (
            Escale.Statut.EN_COURS if arrivee_poste else Escale.Statut.PLANIFIEE
        )

        # mois_source : "AAAA-MM" converti depuis le nom de l'onglet ("JANVIER 2026" → "2026-01")
        MOIS_FR = {
            "JANVIER":1, "FEVRIER":2, "MARS":3, "AVRIL":4, "MAI":5, "JUIN":6,
            "JUILLET":7, "AOUT":7, "SEPTEMBRE":9, "OCTOBRE":10, "NOVEMBRE":11, "DECEMBRE":12
        }
        mois_str = str(row.get("mois_source", "") or "").strip().upper()
        mois_source_key = None
        if mois_str:
            parties = mois_str.split()
            if len(parties) == 2:
                nom_mois, annee_str = parties[0], parties[1]
                mois_num = MOIS_FR.get(nom_mois)
                if mois_num and annee_str.isdigit():
                    mois_source_key = f"{annee_str}-{mois_num:02d}"

        escale, _ = Escale.objects.update_or_create(
            navire=navire, poste=poste, date_arrivee=arrivee_rade,
            mois_source=mois_source_key,
            defaults={
                "agent": agent,
                "date_ref": date_ref,
                "date_accostage":    pilote_a_bord_arrivee,
                "date_depart":       arrivee_poste,
                "date_appareillage": navire_appareille,
                "temps_attente":     temps_attente,
                "temps_sejour":      temps_sejour,
                "temps_pilotage":    temps_pilotage,
                "temps_accostage":   temps_accostage,
                "tonnage_debarque":  _parser_decimal(row.get("tonnage_debarque")),
                "tonnage_embarque":  _parser_decimal(row.get("tonnage_embarque")),
                "mois_source":       mois_source_key,
                "statut": statut,
                "import_source": self.journal_import,
            },
        )
        return escale
