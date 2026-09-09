"""
Script de test de l'API analytics — Module 4.
Utilise la TokenAuthentication de DRF.

Usage : python test_api_analytics.py
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"
USERNAME = "admin"
PASSWORD = "admin1234"

SEP = "─" * 65


def req(path, method="GET", data=None, token=None):
    url = f"{BASE}{path}"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Token {token}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get_token():
    """Obtient un token DRF via /api-token-auth/ ou crée un token admin."""
    # On utilise django.contrib.auth directement via management shell
    import django, os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    user = User.objects.get(username=USERNAME)
    token, _ = Token.objects.get_or_create(user=user)
    return token.key


def ok(label, status, body):
    mark = "✓" if status < 400 else "✗"
    print(f"{mark} [{status}] {label}")
    if status >= 400:
        print(f"   ERREUR : {body}")
        return False
    return True


def main():
    print(SEP)
    print("  Test de l'API analytics — Module 4 (PAD)")
    print(SEP)

    # Auth
    try:
        token = get_token()
        print(f"✓ Token admin obtenu : {token[:12]}...\n")
    except Exception as e:
        print(f"✗ Impossible d'obtenir le token : {e}")
        sys.exit(1)

    erreurs = 0

    # ── 1. Référentiel ────────────────────────────────────────────────────────
    print("[ Référentiel OLAP ]")
    s, b = req("/api/analytics/axes/", token=token)
    if ok("GET /api/analytics/axes/", s, b):
        print(f"   {len(b)} axes : {', '.join(a['code'] for a in b[:4])}...")
    else:
        erreurs += 1

    s, b = req("/api/analytics/mesures/", token=token)
    if ok("GET /api/analytics/mesures/", s, b):
        print(f"   {len(b)} mesures : {', '.join(m['code'] for m in b[:3])}...")
    else:
        erreurs += 1

    # ── 2. Catalogue des cubes ────────────────────────────────────────────────
    print("\n[ Catalogue des cubes ]")
    s, b = req("/api/analytics/cubes/", token=token)
    if ok("GET /api/analytics/cubes/", s, b):
        cubes = b.get("results", b) if isinstance(b, dict) else b
        print(f"   {len(cubes)} cube(s) défini(s) :")
        for c in cubes:
            print(f"   - {c['nom']} ({c['mesure']})")
    else:
        erreurs += 1

    # ── 3. Exécution d'un cube 1D ─────────────────────────────────────────────
    print("\n[ Cube ad hoc — 1D ]")
    payload = {
        "mesure": "nb_escales",
        "axe_ligne": "terminal",
        "date_debut": "2025-01-01",
        "date_fin": "2026-06-30",
        "format": "plat",
    }
    s, b = req("/api/analytics/cube/executer/", method="POST", data=payload, token=token)
    if ok("POST /api/analytics/cube/executer/ (nb_escales × terminal)", s, b):
        rows = b.get("resultats", [])
        resume = b.get("resume", {})
        print(f"   {len(rows)} terminal(aux) — total escales : {resume.get('total')}")
        for r in rows:
            print(f"   · {r['label']} : {r['valeur']} escales")
    else:
        erreurs += 1

    # ── 4. Cube 2D pivot ──────────────────────────────────────────────────────
    print("\n[ Cube ad hoc — Pivot 2D ]")
    payload2d = {
        "mesure": "nb_escales",
        "axe_ligne": "terminal",
        "axe_colonne": "temps_trimestre",
        "date_debut": "2025-01-01",
        "date_fin": "2026-06-30",
        "format": "pivot",
    }
    s, b = req("/api/analytics/cube/executer/", method="POST", data=payload2d, token=token)
    if ok("POST /api/analytics/cube/executer/ (pivot terminal × trimestre)", s, b):
        pivot = b.get("resultats", {})
        print(f"   {len(pivot.get('lignes',[]))} lignes × {len(pivot.get('colonnes',[]))} colonnes")
        print(f"   Colonnes : {pivot.get('labels_colonnes', [])}")
        for i, ligne in enumerate(pivot.get("lignes", [])):
            print(f"   · {pivot['labels_lignes'][i]} → {pivot['matrice'][i]}")
    else:
        erreurs += 1

    # ── 5. Tendance temporelle ────────────────────────────────────────────────
    print("\n[ Tendance temporelle ]")
    s, b = req(
        "/api/analytics/tendance/?mesure=nb_escales&date_debut=2025-01-01&date_fin=2026-06-30&granularite=mois",
        token=token,
    )
    if ok("GET /api/analytics/tendance/ (nb_escales, mois)", s, b):
        serie = b.get("serie", [])
        reg = b.get("regression") or {}
        print(f"   {len(serie)} points, variation totale : {b.get('variation_totale')}")
        if reg:
            print(f"   Tendance : {reg.get('tendance')} (pente={reg.get('pente')}, R²={reg.get('r_carre')})")
        for pt in serie[:4]:
            print(f"   · {pt['label']} : {pt['valeur']}")
        if len(serie) > 4:
            print(f"   ... ({len(serie) - 4} de plus)")
    else:
        erreurs += 1

    # ── 6. Comparaison de périodes ────────────────────────────────────────────
    print("\n[ Comparaison de périodes ]")
    s, b = req(
        "/api/analytics/comparaison/?mesure=nb_escales&axe=terminal"
        "&ref_debut=2025-01-01&ref_fin=2025-12-31"
        "&comp_debut=2026-01-01&comp_fin=2026-06-30",
        token=token,
    )
    if ok("GET /api/analytics/comparaison/ (2025 vs 2026)", s, b):
        for row in b.get("comparaison", []):
            signe = "+" if (row.get("delta") or 0) > 0 else ""
            print(f"   · {row['label']}: {row['valeur_ref']} → {row['valeur_comp']} ({signe}{row.get('delta')}, {signe}{row.get('variation_pct')}%)")
    else:
        erreurs += 1

    # ── 7. Classement ─────────────────────────────────────────────────────────
    print("\n[ Classement top-5 compagnies ]")
    s, b = req(
        "/api/analytics/classement/?mesure=nb_escales&axe=compagnie"
        "&date_debut=2025-01-01&date_fin=2026-06-30&top=5&ordre=desc",
        token=token,
    )
    if ok("GET /api/analytics/classement/ (nb_escales × compagnie, top 5)", s, b):
        for row in b.get("classement", []):
            print(f"   #{row['rang']} {row['label']} : {row['valeur']} escales ({row.get('part_pct')}%)")
    else:
        erreurs += 1

    # ── 8. Corrélation ────────────────────────────────────────────────────────
    print("\n[ Corrélation ]")
    s, b = req(
        "/api/analytics/correlation/?mesure_x=nb_escales&mesure_y=temps_attente_moy"
        "&date_debut=2025-01-01&date_fin=2026-06-30&granularite=mois",
        token=token,
    )
    if ok("GET /api/analytics/correlation/ (nb_escales ↔ temps_attente_moy)", s, b):
        print(f"   r = {b.get('correlation_pearson')} — {b.get('interpretation')}")
        print(f"   ({b.get('nb_periodes')} périodes communes)")
    else:
        erreurs += 1

    # ── 9. Synthèse globale ───────────────────────────────────────────────────
    print("\n[ Synthèse globale ]")
    s, b = req(
        "/api/analytics/synthese/?date_debut=2026-01-01&date_fin=2026-06-30",
        token=token,
    )
    if ok("GET /api/analytics/synthese/ (2026-01 → 2026-06)", s, b):
        kpi = b.get("kpi_globaux", {})
        print(f"   Escales : {kpi.get('nb_escales')}")
        print(f"   Temps d'attente moyen : {kpi.get('temps_attente_moyen_h')} h")
        print(f"   Tonnage total : {kpi.get('tonnage_total_t')} t")
        print(f"   Top terminaux :")
        for t in b.get("top_terminaux", [])[:3]:
            print(f"   #{t['rang']} {t['label']} — {t['valeur']} escales ({t.get('part_pct')}%)")
    else:
        erreurs += 1

    # ── 10. Répartition statuts ───────────────────────────────────────────────
    print("\n[ Répartition statuts ]")
    s, b = req(
        "/api/analytics/repartition-statuts/?date_debut=2026-01-01&date_fin=2026-06-30",
        token=token,
    )
    if ok("GET /api/analytics/repartition-statuts/", s, b):
        for r in b.get("repartition", []):
            print(f"   {r['label']} : {r['nb_escales']} ({r['part_pct']}%)")
    else:
        erreurs += 1

    # ── Bilan ─────────────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    total = 10
    reussis = total - erreurs
    if erreurs == 0:
        print(f"  ✓ Tous les tests passent ({reussis}/{total})")
    else:
        print(f"  ✗ {erreurs} test(s) en échec ({reussis}/{total} OK)")
    print(SEP)
    return erreurs


if __name__ == "__main__":
    sys.exit(main())
