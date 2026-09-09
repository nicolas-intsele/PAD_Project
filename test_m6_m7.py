import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from django.test import Client
from django.test.utils import override_settings

with override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1']):
    c = Client()
    c.login(username='admin', password='admin1234')
    erreurs = 0

    tests = [
        ('/alertes/',                                          200),
        ('/alertes/?gravite=critique',                        200),
        ('/alertes/?statut=active&type_alerte=retard',        200),
        ('/reporting/',                                        200),
    ]

    for url, expected in tests:
        r = c.get(url)
        ok = r.status_code == expected
        if not ok:
            erreurs += 1
        label = url.split('?')[0]
        print(f"{'OK' if ok else 'ERR'} [{r.status_code}] {label}")

    # Test scan alertes (GET → redirect)
    r = c.get('/alertes/scanner/')
    ok = r.status_code in (200, 302)
    if not ok:
        erreurs += 1
    print(f"{'OK' if ok else 'ERR'} [{r.status_code}] /alertes/scanner/")

    print()
    if erreurs == 0:
        print("M6/M7 : SUCCES — toutes les pages repondent correctement.")
    else:
        print(f"M6/M7 : {erreurs} erreur(s)")
