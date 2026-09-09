"""
Générateur de rapports PDF — Module 7.
Utilise ReportLab (100% Python, sans dépendances système).

Structure du rapport :
  1. Page de garde (logo PAD + titre + période)
  2. Synthèse exécutive (KPI globaux)
  3. KPI par catégorie (tableau)
  4. Évolution du trafic mensuel
  5. Top terminaux & compagnies
  6. Alertes actives
"""
from __future__ import annotations

import io
import logging
import os
from datetime import date
from decimal import Decimal

logger = logging.getLogger(__name__)

# ── Couleurs PAD ──────────────────────────────────────────────────────────────
try:
    from reportlab.lib.colors import Color, HexColor, white, black
    BLUE    = HexColor('#1B2B6B')
    BLUE2   = HexColor('#243985')
    ORANGE  = HexColor('#E67E22')
    TEAL    = HexColor('#148F77')
    RED     = HexColor('#C0392B')
    GREY_BG = HexColor('#F0F4F8')
    GREY_LN = HexColor('#E2E8F0')
    MUTED   = HexColor('#7F8C8D')
except ImportError:
    pass   # sera capturé plus bas


def _collecter_donnees(date_debut: date, date_fin: date) -> dict:
    """Collecte toutes les données nécessaires au rapport."""
    from apps.analytics.analyses import (
        calculer_tendance, classement, repartition_statut, synthese_periode
    )
    from apps.kpi.engine.calculateurs import CALCULATEURS
    from apps.kpi.engine.service import garantir_catalogue
    from apps.kpi.models import KPI
    from apps.alerts.service import stats_alertes
    from apps.alerts.models import Alerte

    from django.utils import timezone

    garantir_catalogue()

    synthese = synthese_periode(date_debut, date_fin)

    kpi_valeurs = []
    for kpi in KPI.objects.all().order_by("categorie", "code"):
        fn = CALCULATEURS.get(kpi.code)
        valeur = None
        if fn:
            try:
                valeur = fn(date_debut, date_fin)
            except Exception:
                pass
        kpi_valeurs.append({
            "code": kpi.code,
            "libelle": kpi.libelle,
            "categorie": kpi.categorie,
            "unite": kpi.unite or "",
            "valeur": float(valeur) if valeur is not None else None,
        })

    try:
        tendance = calculer_tendance("nb_escales", date_debut, date_fin)
    except Exception:
        tendance = {"serie": [], "regression": None}

    top_terminaux  = classement("nb_escales", "terminal",  date_debut, date_fin, top=5)
    top_compagnies = classement("nb_escales", "compagnie", date_debut, date_fin, top=5)
    statuts        = repartition_statut(date_debut, date_fin)

    alertes_actives = list(
        Alerte.objects.filter(statut="active")
        .order_by("-niveau_gravite", "-date_declenchement")[:10]
    )

    return {
        "date_debut":      date_debut,
        "date_fin":        date_fin,
        "date_generation": timezone.now(),
        "synthese":        synthese,
        "kpi_valeurs":     kpi_valeurs,
        "tendance":        tendance,
        "top_terminaux":   top_terminaux,
        "top_compagnies":  top_compagnies,
        "statuts":         statuts,
        "alertes_actives": alertes_actives,
        "stats_alertes":   stats_alertes(),
    }


# ── Helpers ReportLab ─────────────────────────────────────────────────────────

def _table_style_base():
    from reportlab.platypus import TableStyle
    return TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0),  BLUE),
        ('TEXTCOLOR',    (0, 0), (-1, 0),  white),
        ('FONTNAME',     (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, 0),  9),
        ('BOTTOMPADDING',(0, 0), (-1, 0),  7),
        ('TOPPADDING',   (0, 0), (-1, 0),  7),
        ('ROWBACKGROUNDS',(0, 1),(-1, -1), [white, GREY_BG]),
        ('FONTNAME',     (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',     (0, 1), (-1, -1), 8),
        ('TOPPADDING',   (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING',(0, 1), (-1, -1), 5),
        ('GRID',         (0, 0), (-1, -1), 0.4, GREY_LN),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
    ])


def _h1(text):
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    st = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=14,
                        textColor=BLUE, spaceAfter=6)
    return Paragraph(text, st)


def _h2(text):
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    st = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11,
                        textColor=BLUE2, spaceBefore=14, spaceAfter=5,
                        borderPad=4, borderColor=ORANGE,
                        leftIndent=8, borderWidth=0)
    return Paragraph(f'<font color="#E67E22">▌</font> {text}', st)


def _para(text, size=8, color=None):
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    c = color or HexColor('#2C3E50')
    st = ParagraphStyle('p', fontName='Helvetica', fontSize=size,
                        textColor=c, spaceAfter=3)
    return Paragraph(text, st)


def _spacer(h=8):
    from reportlab.platypus import Spacer
    from reportlab.lib.units import mm
    return Spacer(1, h)


# ── Construction du PDF ───────────────────────────────────────────────────────

def generer_pdf(
    date_debut: date,
    date_fin: date,
    type_rapport: str = "mensuel",
    titre: str | None = None,
) -> bytes:
    """Génère le PDF via ReportLab et retourne les bytes."""
    try:
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, PageBreak, Image as RLImage,
        )
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm, cm
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
    except ImportError as exc:
        raise RuntimeError("reportlab non installé. Lancez : pip install reportlab") from exc

    donnees = _collecter_donnees(date_debut, date_fin)
    titre   = titre or f"Rapport {type_rapport.capitalize()} — Port Autonome de Douala"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.5*cm,  bottomMargin=2*cm,
        title=titre,
        author="Plateforme Décisionnelle PAD",
    )

    # ── Logo path ─────────────────────────────────────────────────────────────
    from django.conf import settings as dj_settings
    logo_path = os.path.join(dj_settings.BASE_DIR, "static", "dashboard", "img", "pad_logo.jpg")

    story = []
    styles = getSampleStyleSheet()
    PAGE_W = A4[0] - 3.6*cm   # largeur utile

    # ── PAGE DE GARDE ─────────────────────────────────────────────────────────
    story.append(_spacer(30))

    # Logo centré
    if os.path.exists(logo_path):
        logo = RLImage(logo_path, width=5*cm, height=5*cm)
        logo.hAlign = 'CENTER'
        story.append(logo)
    else:
        story.append(_para("⚓", size=40))

    story.append(_spacer(16))

    # Titre principal
    title_style = styles['Title']
    title_style.textColor = BLUE
    title_style.fontSize = 20
    title_style.fontName = 'Helvetica-Bold'
    story.append(Paragraph(titre, title_style))
    story.append(_spacer(8))

    # Sous-titre période
    story.append(_para(
        f"Période : <b>{date_debut.strftime('%d/%m/%Y')}</b> → <b>{date_fin.strftime('%d/%m/%Y')}</b>",
        size=11, color=BLUE2
    ))
    story.append(_para(
        f"Type : {type_rapport.capitalize()}  |  "
        f"Généré le : {date.today().strftime('%d/%m/%Y')}",
        size=9, color=MUTED
    ))
    story.append(_spacer(10))
    story.append(HRFlowable(width=PAGE_W, thickness=2, color=ORANGE))
    story.append(_spacer(20))

    # ── Bloc KPI globaux (page de garde) ──────────────────────────────────────
    kpi_g = donnees["synthese"]["kpi_globaux"]
    kpi_cards = [
        ["Escales totales",        str(kpi_g.get("nb_escales") or "—"),                    "escales"],
        ["Attente moyenne",        f"{kpi_g.get('temps_attente_moyen_h') or '—':.1f}" if kpi_g.get('temps_attente_moyen_h') else "—", "heures"],
        ["Séjour moyen",           f"{kpi_g.get('temps_sejour_moyen_h') or '—':.1f}"  if kpi_g.get('temps_sejour_moyen_h')  else "—", "heures"],
        ["Tonnage total",          f"{kpi_g.get('tonnage_total_t') or '—':,.0f}"       if kpi_g.get('tonnage_total_t')       else "—", "tonnes"],
    ]
    kpi_table_data = [["Indicateur", "Valeur", "Unité"]] + kpi_cards
    kpi_tbl = Table(kpi_table_data, colWidths=[PAGE_W*0.5, PAGE_W*0.25, PAGE_W*0.25])
    kpi_tbl.setStyle(_table_style_base())
    kpi_tbl.setStyle(TableStyle([
        ('FONTNAME',  (1, 1), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',  (1, 1), (1, -1), 11),
        ('TEXTCOLOR', (1, 1), (1, -1), BLUE),
        ('ALIGN',     (1, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(kpi_tbl)

    # ── Alertes résumé (page de garde) ───────────────────────────────────────
    stats = donnees["stats_alertes"]
    if stats.get("total_actives", 0) > 0:
        story.append(_spacer(14))
        story.append(HRFlowable(width=PAGE_W, thickness=0.5, color=GREY_LN))
        story.append(_spacer(6))
        story.append(_para(
            f"⚠ <b>{stats['critiques']}</b> alerte(s) critique(s)  |  "
            f"<b>{stats['avertissements']}</b> avertissement(s)  |  "
            f"<b>{stats['infos']}</b> information(s)",
            size=9, color=RED
        ))

    story.append(PageBreak())

    # ── 1. KPI PAR CATÉGORIE ──────────────────────────────────────────────────
    story.append(_h1("1. Indicateurs de performance"))
    story.append(_spacer(6))

    cats = [
        ("trafic",          "Trafic"),
        ("temps",           "Temps"),
        ("infrastructures", "Infrastructures"),
        ("performance",     "Performance"),
    ]
    for cat_code, cat_label in cats:
        items = [k for k in donnees["kpi_valeurs"] if k["categorie"] == cat_code]
        if not items:
            continue
        story.append(_h2(cat_label))
        rows = [["Indicateur", "Code", "Valeur", "Unité"]]
        for k in items:
            val = f"{k['valeur']:.3f}" if k["valeur"] is not None else "—"
            rows.append([k["libelle"], k["code"], val, k["unite"]])
        tbl = Table(rows, colWidths=[PAGE_W*0.38, PAGE_W*0.30, PAGE_W*0.17, PAGE_W*0.15])
        tbl.setStyle(_table_style_base())
        tbl.setStyle(TableStyle([
            ('FONTNAME',  (2, 1), (2, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (2, 1), (2, -1), BLUE),
            ('ALIGN',     (2, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(tbl)
        story.append(_spacer(6))

    story.append(PageBreak())

    # ── 2. ÉVOLUTION DU TRAFIC ────────────────────────────────────────────────
    story.append(_h1("2. Évolution mensuelle du trafic"))
    story.append(_spacer(6))

    reg = (donnees["tendance"].get("regression") or {})
    if reg:
        tendance_txt = reg.get("tendance", "stable").upper()
        story.append(_para(
            f"Tendance : <b>{tendance_txt}</b>  |  "
            f"R² = <b>{reg.get('r_carre', 0):.3f}</b>  |  "
            f"Pente = <b>{reg.get('pente', 0):.2f}</b> escales/période",
            size=9
        ))
        story.append(_spacer(6))

    serie = donnees["tendance"].get("serie", [])
    if serie:
        rows = [["Période", "Nombre d'escales"]]
        for pt in serie:
            rows.append([pt["label"], str(pt["valeur"]) if pt["valeur"] is not None else "—"])
        tbl = Table(rows, colWidths=[PAGE_W*0.6, PAGE_W*0.4])
        tbl.setStyle(_table_style_base())
        tbl.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (1, 1), (1, -1), BLUE),
        ]))
        story.append(tbl)
    else:
        story.append(_para("Aucune donnée de trafic sur la période.", color=MUTED))

    story.append(PageBreak())

    # ── 3. TERMINAUX & COMPAGNIES ─────────────────────────────────────────────
    story.append(_h1("3. Performance par terminal et compagnie"))
    story.append(_spacer(6))

    # Top terminaux
    story.append(_h2("Top terminaux"))
    if donnees["top_terminaux"]:
        rows = [["#", "Terminal", "Escales", "Part (%)"]]
        for t in donnees["top_terminaux"]:
            rows.append([str(t.get("rang", "")), t.get("label", ""),
                         str(t.get("valeur", "")), f"{t.get('part_pct', 0):.1f}%"])
        tbl = Table(rows, colWidths=[PAGE_W*0.07, PAGE_W*0.53, PAGE_W*0.20, PAGE_W*0.20])
        tbl.setStyle(_table_style_base())
        tbl.setStyle(TableStyle([('ALIGN', (0, 0), (0, -1), 'CENTER'),
                                  ('ALIGN', (2, 0), (-1, -1), 'CENTER')]))
        story.append(tbl)
    else:
        story.append(_para("Aucune donnée.", color=MUTED))

    story.append(_spacer(12))

    # Top compagnies
    story.append(_h2("Top compagnies maritimes"))
    if donnees["top_compagnies"]:
        rows = [["#", "Compagnie", "Escales", "Part (%)"]]
        for c in donnees["top_compagnies"]:
            rows.append([str(c.get("rang", "")), c.get("label", ""),
                         str(c.get("valeur", "")), f"{c.get('part_pct', 0):.1f}%"])
        tbl = Table(rows, colWidths=[PAGE_W*0.07, PAGE_W*0.53, PAGE_W*0.20, PAGE_W*0.20])
        tbl.setStyle(_table_style_base())
        tbl.setStyle(TableStyle([('ALIGN', (0, 0), (0, -1), 'CENTER'),
                                  ('ALIGN', (2, 0), (-1, -1), 'CENTER')]))
        story.append(tbl)

    story.append(_spacer(12))

    # Statuts
    story.append(_h2("Répartition par statut des escales"))
    if donnees["statuts"]:
        rows = [["Statut", "Nb escales", "Part (%)"]]
        for s in donnees["statuts"]:
            rows.append([s.get("label", ""), str(s.get("nb_escales", 0)),
                         f"{s.get('part_pct', 0):.1f}%"])
        tbl = Table(rows, colWidths=[PAGE_W*0.5, PAGE_W*0.25, PAGE_W*0.25])
        tbl.setStyle(_table_style_base())
        tbl.setStyle(TableStyle([('ALIGN', (1, 0), (-1, -1), 'CENTER')]))
        story.append(tbl)

    # ── 4. ALERTES ACTIVES ────────────────────────────────────────────────────
    if donnees["alertes_actives"]:
        story.append(PageBreak())
        story.append(_h1("4. Alertes actives"))
        story.append(_spacer(6))

        rows = [["Gravité", "Type", "Message", "Date"]]
        for a in donnees["alertes_actives"]:
            niveau = a.niveau_gravite.upper()
            msg    = a.message[:100] + ("…" if len(a.message) > 100 else "")
            rows.append([
                niveau,
                a.get_type_alerte_display(),
                msg,
                a.date_declenchement.strftime("%d/%m/%Y"),
            ])
        tbl = Table(rows, colWidths=[PAGE_W*0.12, PAGE_W*0.18, PAGE_W*0.55, PAGE_W*0.15])
        ts  = _table_style_base()

        # Couleur par gravité dans la colonne 0
        for i, a in enumerate(donnees["alertes_actives"], 1):
            c = RED if a.niveau_gravite == "critique" else (ORANGE if a.niveau_gravite == "avertissement" else BLUE2)
            ts.add('TEXTCOLOR', (0, i), (0, i), c)
            ts.add('FONTNAME',  (0, i), (0, i), 'Helvetica-Bold')

        tbl.setStyle(ts)
        story.append(tbl)

    # ── Pied de rapport ───────────────────────────────────────────────────────
    story.append(_spacer(20))
    story.append(HRFlowable(width=PAGE_W, thickness=0.5, color=GREY_LN))
    story.append(_spacer(5))
    story.append(_para(
        "Ce rapport a été généré automatiquement par la Plateforme Décisionnelle "
        "du Port Autonome de Douala. Données issues du registre des opérations navires.",
        size=7, color=MUTED
    ))

    # ── Callback en-tête / pied de page ──────────────────────────────────────
    def _header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 7)
        canvas.setFillColor(BLUE)
        canvas.drawString(1.8*cm, A4[1] - 1.1*cm, "Port Autonome de Douala — Plateforme Décisionnelle")
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(A4[0] - 1.8*cm, A4[1] - 1.1*cm,
                               f"Rapport {type_rapport.capitalize()} | {date_debut} → {date_fin}")
        canvas.setStrokeColor(GREY_LN)
        canvas.setLineWidth(0.5)
        canvas.line(1.8*cm, A4[1] - 1.3*cm, A4[0] - 1.8*cm, A4[1] - 1.3*cm)
        # Pied
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(1.8*cm, 1.2*cm, "© PAD — Confidentiel")
        canvas.drawRightString(A4[0] - 1.8*cm, 1.2*cm,
                               f"Page {doc.page}")
        canvas.line(1.8*cm, 1.5*cm, A4[0] - 1.8*cm, 1.5*cm)
        canvas.restoreState()

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
