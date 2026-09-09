"""
Générateur de rapports Excel multi-onglets — Module 7.
Utilise openpyxl directement (sans xlsxwriter).

Onglets générés :
  1. Résumé          — synthèse globale + alertes actives
  2. KPI             — tableau complet des 13 indicateurs
  3. Trafic          — évolution mensuelle des escales
  4. Infrastructure  — taux d'occupation par terminal
  5. Compagnies      — classement compagnies
  6. Escales         — liste des 200 dernières escales
"""
from __future__ import annotations

import io
import logging
from datetime import date
from typing import Any

import openpyxl
from openpyxl.styles import (Alignment, Border, Font, PatternFill, Side,
                              numbers)
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

# ── Palette couleurs PAD ──────────────────────────────────────────────────────
C_BLUE   = "0A3D62"
C_BLUE2  = "1A5276"
C_ORANGE = "E67E22"
C_TEAL   = "148F77"
C_RED    = "C0392B"
C_LIGHT  = "D6EAF8"
C_GREY   = "F0F4F8"
C_WHITE  = "FFFFFF"

def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)

def _font(bold=False, color="000000", size=11) -> Font:
    return Font(name="Calibri", bold=bold, color=color, size=size)

def _border_thin() -> Border:
    s = Side(style="thin", color="D1D9E0")
    return Border(left=s, right=s, top=s, bottom=s)

def _center() -> Alignment:
    return Alignment(horizontal="center", vertical="center", wrap_text=True)


def _header_row(ws, row: int, headers: list[str], col_start: int = 1):
    for i, h in enumerate(headers):
        cell = ws.cell(row=row, column=col_start + i, value=h)
        cell.fill   = _fill(C_BLUE)
        cell.font   = _font(bold=True, color=C_WHITE)
        cell.alignment = _center()
        cell.border = _border_thin()


def _data_row(ws, row: int, values: list[Any], col_start: int = 1, alternate: bool = False):
    bg = C_GREY if alternate else C_WHITE
    for i, v in enumerate(values):
        cell = ws.cell(row=row, column=col_start + i, value=v)
        cell.fill   = _fill(bg)
        cell.border = _border_thin()
        cell.alignment = Alignment(vertical="center", wrap_text=False)


def _titre_feuille(ws, titre: str, subtitle: str = "", nb_cols: int = 6):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=nb_cols)
    c = ws.cell(row=1, column=1, value=titre)
    c.font      = Font(name="Calibri", bold=True, size=14, color=C_WHITE)
    c.fill      = _fill(C_BLUE)
    c.alignment = _center()

    if subtitle:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=nb_cols)
        c2 = ws.cell(row=2, column=1, value=subtitle)
        c2.font      = Font(name="Calibri", size=10, color=C_BLUE2, italic=True)
        c2.fill      = _fill(C_LIGHT)
        c2.alignment = _center()
    return 3 if subtitle else 2


def _auto_width(ws, min_w=10, max_w=50):
    for col in ws.columns:
        w = max(
            (len(str(c.value)) if c.value else 0) for c in col
        )
        ws.column_dimensions[get_column_letter(col[0].column)].width = max(min_w, min(w + 2, max_w))


# ── Onglets ───────────────────────────────────────────────────────────────────

def _onglet_resume(wb, donnees: dict):
    ws = wb.active
    ws.title = "Résumé"
    ws.sheet_view.showGridLines = False

    row = _titre_feuille(ws, "Rapport PAD — Résumé exécutif",
                         f"Période : {donnees['date_debut']} → {donnees['date_fin']}", nb_cols=4)

    # Informations générales
    infos = [
        ("Généré le", donnees['date_generation'].strftime("%d/%m/%Y %H:%M")),
        ("Période couverte", f"{donnees['date_debut']} → {donnees['date_fin']}"),
        ("Type de rapport", donnees.get("type_rapport", "—").capitalize()),
    ]
    for label, val in infos:
        ws.cell(row=row, column=1, value=label).font = _font(bold=True)
        ws.cell(row=row, column=2, value=val)
        row += 1
    row += 1

    # KPI globaux résumé
    ws.cell(row=row, column=1, value="Indicateurs clés").font = _font(bold=True, size=12, color=C_BLUE)
    row += 1
    _header_row(ws, row, ["KPI", "Valeur", "Unité"], col_start=1)
    row += 1

    synthese_kpi = [
        ("Nombre d'escales",          donnees['synthese']['kpi_globaux']['nb_escales'],     "escales"),
        ("Temps d'attente moyen",     donnees['synthese']['kpi_globaux']['temps_attente_moyen_h'], "heures"),
        ("Temps de séjour moyen",     donnees['synthese']['kpi_globaux']['temps_sejour_moyen_h'],  "heures"),
        ("Tonnage total",             donnees['synthese']['kpi_globaux']['tonnage_total_t'],        "tonnes"),
    ]
    for i, (lib, val, unite) in enumerate(synthese_kpi):
        _data_row(ws, row, [lib, val, unite], alternate=bool(i % 2))
        row += 1
    row += 1

    # Alertes actives
    ws.cell(row=row, column=1, value="Alertes actives").font = _font(bold=True, size=12, color=C_RED)
    row += 1
    stats = donnees.get("stats_alertes", {})
    ws.cell(row=row, column=1, value="Critiques").font = _font(bold=True)
    ws.cell(row=row, column=2, value=stats.get("critiques", 0)).fill = _fill("FADBD8")
    row += 1
    ws.cell(row=row, column=1, value="Avertissements").font = _font(bold=True)
    ws.cell(row=row, column=2, value=stats.get("avertissements", 0)).fill = _fill("FDEBD0")
    row += 1
    ws.cell(row=row, column=1, value="Informations").font = _font(bold=True)
    ws.cell(row=row, column=2, value=stats.get("infos", 0))
    row += 2

    # Top terminaux
    ws.cell(row=row, column=1, value="Top terminaux").font = _font(bold=True, size=12, color=C_ORANGE)
    row += 1
    _header_row(ws, row, ["#", "Terminal", "Escales", "Part (%)"], col_start=1)
    row += 1
    for i, t in enumerate(donnees.get("top_terminaux", [])[:5]):
        _data_row(ws, row, [t.get("rang"), t.get("label"), t.get("valeur"), t.get("part_pct")], alternate=bool(i % 2))
        row += 1

    _auto_width(ws)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 22
    ws.row_dimensions[1].height = 28


def _onglet_kpi(wb, donnees: dict):
    ws = wb.create_sheet("KPI")
    ws.sheet_view.showGridLines = False
    row = _titre_feuille(ws, "Tableau des KPI", nb_cols=5)

    _header_row(ws, row, ["Code", "Libellé", "Catégorie", "Valeur", "Unité"])
    row += 1

    for i, kpi in enumerate(donnees["kpi_valeurs"]):
        val = f"{kpi['valeur']:.3f}" if kpi["valeur"] is not None else "—"
        _data_row(ws, row, [kpi["code"], kpi["libelle"], kpi["categorie"].capitalize(), val, kpi["unite"]], alternate=bool(i % 2))
        row += 1

    _auto_width(ws)


def _onglet_trafic(wb, donnees: dict):
    ws = wb.create_sheet("Trafic mensuel")
    ws.sheet_view.showGridLines = False
    row = _titre_feuille(ws, "Évolution mensuelle du trafic", nb_cols=3)

    _header_row(ws, row, ["Période", "Label", "Nb escales"])
    row += 1

    serie = donnees["tendance"].get("serie", [])
    for i, pt in enumerate(serie):
        val = pt["valeur"] if pt["valeur"] is not None else "—"
        _data_row(ws, row, [pt["periode"], pt["label"], val], alternate=bool(i % 2))
        row += 1

    if serie:
        reg = donnees["tendance"].get("regression") or {}
        row += 1
        ws.cell(row=row, column=1, value="Tendance :").font = _font(bold=True)
        ws.cell(row=row, column=2, value=reg.get("tendance", "—"))
        row += 1
        ws.cell(row=row, column=1, value="R² :").font = _font(bold=True)
        ws.cell(row=row, column=2, value=reg.get("r_carre"))

    _auto_width(ws)


def _onglet_infrastructure(wb, donnees: dict):
    ws = wb.create_sheet("Infrastructure")
    ws.sheet_view.showGridLines = False
    row = _titre_feuille(ws, "Performance des terminaux", nb_cols=4)

    _header_row(ws, row, ["#", "Terminal", "Escales", "Part (%)"])
    row += 1
    for i, t in enumerate(donnees["top_terminaux"]):
        _data_row(ws, row, [t.get("rang"), t.get("label"), t.get("valeur"), t.get("part_pct")], alternate=bool(i % 2))
        row += 1

    row += 2
    ws.cell(row=row, column=1, value="Répartition par statut").font = _font(bold=True, size=12, color=C_BLUE)
    row += 1
    _header_row(ws, row, ["Statut", "Nb escales", "Part (%)"])
    row += 1
    for i, s in enumerate(donnees.get("statuts", [])):
        _data_row(ws, row, [s.get("label"), s.get("nb_escales"), s.get("part_pct")], alternate=bool(i % 2))
        row += 1

    _auto_width(ws)


def _onglet_compagnies(wb, donnees: dict):
    ws = wb.create_sheet("Compagnies")
    ws.sheet_view.showGridLines = False
    row = _titre_feuille(ws, "Classement des compagnies maritimes", nb_cols=4)

    _header_row(ws, row, ["#", "Compagnie", "Escales", "Part (%)"])
    row += 1
    for i, c in enumerate(donnees["top_compagnies"]):
        _data_row(ws, row, [c.get("rang"), c.get("label"), c.get("valeur"), c.get("part_pct")], alternate=bool(i % 2))
        row += 1

    _auto_width(ws)


def _onglet_escales(wb, date_debut: date, date_fin: date):
    from apps.escales.models import Escale
    ws = wb.create_sheet("Escales détail")
    ws.sheet_view.showGridLines = False
    row = _titre_feuille(ws, "Détail des escales", nb_cols=9)

    _header_row(ws, row, ["ID", "Navire", "Type", "Compagnie", "Terminal", "Poste",
                           "Arrivée", "Attente (h)", "Séjour (h)"])
    row += 1

    qs = (Escale.objects
          .filter(date_arrivee__date__range=(date_debut, date_fin))
          .select_related("navire__type_navire", "navire__compagnie", "poste__terminal")
          .order_by("-date_arrivee")[:200])

    for i, e in enumerate(qs):
        att = float(e.temps_attente) if e.temps_attente else None
        sej = float(e.temps_sejour)  if e.temps_sejour  else None
        _data_row(ws, row, [
            e.pk,
            e.navire.nom,
            e.navire.type_navire.libelle,
            e.navire.compagnie.raison_sociale,
            e.poste.terminal.nom,
            e.poste.nom,
            e.date_arrivee.strftime("%d/%m/%Y %H:%M"),
            att,
            sej,
        ], alternate=bool(i % 2))
        row += 1

    _auto_width(ws)


# ── Point d'entrée ────────────────────────────────────────────────────────────

def generer_excel(
    date_debut: date,
    date_fin: date,
    type_rapport: str = "mensuel",
    titre: str | None = None,
) -> bytes:
    """Génère le classeur Excel et retourne les bytes."""
    from apps.reporting.generators.pdf_generator import _collecter_donnees

    donnees = _collecter_donnees(date_debut, date_fin)
    donnees["type_rapport"] = type_rapport
    donnees["titre"] = titre or f"Rapport {type_rapport} — Port Autonome de Douala"

    wb = openpyxl.Workbook()
    _onglet_resume(wb, donnees)
    _onglet_kpi(wb, donnees)
    _onglet_trafic(wb, donnees)
    _onglet_infrastructure(wb, donnees)
    _onglet_compagnies(wb, donnees)
    _onglet_escales(wb, date_debut, date_fin)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
