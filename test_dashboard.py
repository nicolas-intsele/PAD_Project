"""Test rapide des pages dashboard."""
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from django.test import Client
from django.test.utils import override_settings

erreurs = 0

with override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1']):
    c = Client()

    r = c.get('/')
    ok = r.status_code in (200, 302)
    loc = r.get('Location', '')
    mark = 'OK' if ok else 'ERR'
    print(f"{mark} [{r.status_code}] GET /  -> {loc}")
    if not ok:
        erreurs += 1

    r2 = c.get('/direction/')
    ok2 = r2.status_code == 302
    mark2 = 'OK' if ok2 else 'ERR'
    print(f"{mark2} [{r2.status_code}] GET /direction/ sans auth -> {r2.get('Location', '')}")
    if not ok2:
        erreurs += 1

    logged = c.login(username='admin', password='admin1234')
    print(f"{'OK' if logged else 'ERR'} Login admin")
    if not logged:
        erreurs += 1

    tests = [
        '/direction/',
        '/exploitation/',
        '/capitainerie/',
        '/kpi/?categorie=trafic&date_debut=2025-01-01&date_fin=2026-06-30',
        '/analyse/?mesure=nb_escales&axe_ligne=terminal',
    ]
    for url in tests:
        r = c.get(url)
        ok = r.status_code == 200
        if not ok:
            erreurs += 1
        label = url.split('?')[0]
        print(f"{'OK' if ok else 'ERR'} [{r.status_code}] {label}")

print()
if erreurs == 0:
    print("RESULTAT : SUCCES — toutes les pages repondent correctement.")
else:
    print(f"RESULTAT : {erreurs} erreur(s) detectee(s).")
