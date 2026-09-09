import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

# Init roles
from apps.users.models import Role, ProfilUtilisateur
Role.initialiser_roles()
roles = list(Role.objects.values_list('code', flat=True))
print(f"Roles: {roles}")

# Profil admin
from django.contrib.auth.models import User
admin = User.objects.get(username='admin')
profil, _ = ProfilUtilisateur.objects.get_or_create(utilisateur=admin)
profil.role = Role.objects.get(code='admin')
profil.poste = 'Administrateur systeme'
profil.save()
print(f"Profil admin: {profil}")

# Test pages M8
from django.test import Client
from django.test.utils import override_settings

with override_settings(ALLOWED_HOSTS=['testserver','localhost','127.0.0.1']):
    c = Client()
    c.login(username='admin', password='admin1234')
    erreurs = 0
    tests = [
        '/admin-pad/',
        '/admin-pad/utilisateurs/',
        '/admin-pad/utilisateurs/nouveau/',
        '/admin-pad/journal/',
        '/admin-pad/seuils/',
    ]
    for url in tests:
        r = c.get(url)
        ok = r.status_code == 200
        if not ok: erreurs += 1
        print(f"{'OK' if ok else 'ERR'} [{r.status_code}] {url}")

    print()
    print("M8 SUCCES" if erreurs == 0 else f"M8 {erreurs} ERREUR(S)")
