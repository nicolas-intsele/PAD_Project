import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from apps.kpi.engine.service import garantir_catalogue
from apps.kpi.models import KPI, SeuilAlerte

garantir_catalogue()

seuils = [
    ('TEMPS_ATTENTE_MOYEN',   None, 24,  'avertissement'),
    ('TEMPS_ATTENTE_MOYEN',   None, 48,  'critique'),
    ('INFRA_TAUX_OCCUPATION', None, 80,  'avertissement'),
    ('INFRA_TAUX_OCCUPATION', None, 95,  'critique'),
    ('PERF_CONGESTION',       None, 20,  'avertissement'),
    ('PERF_CONGESTION',       None, 40,  'critique'),
    ('PERF_PONCTUALITE',      70,   None,'avertissement'),
    ('PERF_PONCTUALITE',      50,   None,'critique'),
]

created = 0
for code, vmin, vmax, gravite in seuils:
    kpi = KPI.objects.filter(code=code).first()
    if not kpi:
        print(f'KPI non trouve : {code}')
        continue
    obj, c = SeuilAlerte.objects.get_or_create(
        kpi=kpi, niveau_gravite=gravite,
        defaults={'valeur_min': vmin, 'valeur_max': vmax}
    )
    if c:
        created += 1
        print(f'  Seuil cree : {code} ({gravite}) min={vmin} max={vmax}')

print(f'Total : {created} seuil(s) cree(s)')
