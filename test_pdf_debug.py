import django, os, traceback
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from datetime import date

print("=== Test generation PDF ===")
try:
    from apps.reporting.generators.pdf_generator import generer_pdf
    b = generer_pdf(date(2026, 1, 1), date(2026, 6, 30), 'mensuel')
    print(f"PDF OK — {len(b)} bytes")
except Exception:
    traceback.print_exc()

print()
print("=== Test generation Excel ===")
try:
    from apps.reporting.generators.excel_generator import generer_excel
    b = generer_excel(date(2026, 1, 1), date(2026, 6, 30), 'mensuel')
    print(f"Excel OK — {len(b)} bytes")
except Exception:
    traceback.print_exc()
