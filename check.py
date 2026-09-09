from apps.kpi.models import KPI
import sqlite3
from django.conf import settings

ponct = KPI.objects.filter(code='PERF_PONCTUALITE').first()
print('PERF_PONCTUALITE en base:', 'OUI' if ponct else 'NON - OK')

db_path = settings.DATABASES['default']['NAME']
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='escale'")
indexes = [r[0] for r in cur.fetchall()]
date_indexes = [i for i in indexes if 'date' in i.lower()]
print('Index dates:', date_indexes if date_indexes else 'AUCUN')
conn.close()
