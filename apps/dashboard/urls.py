from django.urls import path
from . import views, views_alerts, views_reporting, views_users

app_name = "dashboard"

urlpatterns = [
    # Auth
    path("",        views.login_view,  name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Module 5 — Tableaux de bord
    path("direction/",    views.vue_direction,    name="direction"),
    path("exploitation/", views.vue_exploitation, name="exploitation"),
    path("capitainerie/", views.vue_capitainerie, name="capitainerie"),
    path("kpi/",          views.vue_kpi,          name="kpi"),
    path("analyse/",      views.vue_analyse,      name="analyse"),

    # Module 6 — Alertes (views_alerts.py)
    path("alertes/",                                  views_alerts.vue_alertes,            name="alertes"),
    path("alertes/scanner/",                          views_alerts.alertes_scanner,        name="alertes_scanner"),
    path("alertes/acquitter-tout/",                   views_alerts.alertes_acquitter_tout, name="alertes_acquitter_tout"),
    path("alertes/<int:pk>/acquitter/",               views_alerts.alerte_acquitter,       name="alerte_acquitter"),
    path("alertes/<int:pk>/resoudre/",                views_alerts.alerte_resoudre,        name="alerte_resoudre"),

    # Module 7 — Reporting (views_reporting.py)
    path("reporting/",                                views_reporting.vue_reporting,          name="reporting"),
    path("reporting/generer/",                        views_reporting.reporting_generer,      name="reporting_generer"),
    path("reporting/<int:pk>/telecharger/",           views_reporting.reporting_telecharger,  name="reporting_telecharger"),
    path("reporting/rapide/<str:type>/<str:format>/", views_reporting.reporting_rapide,       name="reporting_rapide"),

    # Module 8 — Administration (views_users.py)
    path("admin-pad/",                                views_users.vue_administration,         name="admin_pad"),
    path("admin-pad/utilisateurs/",                   views_users.vue_admin_utilisateurs,     name="admin_utilisateurs"),
    path("admin-pad/utilisateurs/nouveau/",           views_users.vue_admin_user_form,        name="admin_user_creer"),
    path("admin-pad/utilisateurs/<int:pk>/modifier/", views_users.vue_admin_user_form,        name="admin_user_modifier"),
    path("admin-pad/utilisateurs/<int:pk>/toggle/",   views_users.vue_admin_user_toggle,      name="admin_user_toggle"),
    path("admin-pad/journal/",                        views_users.vue_admin_journal,          name="admin_journal"),
    path("admin-pad/seuils/",                         views_users.vue_admin_seuils,           name="admin_seuils"),
    path("admin-pad/seuils/sauver/",                  views_users.vue_admin_seuils_sauver,    name="admin_seuils_sauver"),
    path("admin-pad/seuils/ajouter/",                 views_users.vue_admin_seuil_ajouter,    name="admin_seuil_ajouter"),
    path("admin-pad/seuils/<int:pk>/supprimer/",      views_users.vue_admin_seuil_supprimer,  name="admin_seuil_supprimer"),
]
