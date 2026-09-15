from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("account/", views.account, name="account"),
    path("recherche/", views.search, name="search"),
    path("account/anonyme/creer/", views.create_anonymous, name="create_anonymous"),
    path("account/anonyme/retrouver/", views.recover_anonymous, name="recover_anonymous"),
    path("account/anonyme/oublier/", views.forget_anonymous, name="forget_anonymous"),
    path("account/anonyme/rattacher/", views.link_anonymous, name="link_anonymous"),
    path("raccourcis/", views.raccourcis, name="raccourcis"),
    path("groupes/", views.groupes, name="groupes"),
    path("agenda/", views.agenda, name="agenda"),
    path("agenda/<int:pk>/", views.event_detail, name="event_detail"),
    path("agenda/<int:pk>/ics/", views.event_ics, name="event_ics"),
    path("activites/", views.group_page, {"key": "reperes"}, name="activites"),
    path("poles/", views.group_page, {"key": "poles"}, name="poles"),
    path("a-propos/", views.group_page, {"key": "association"}, name="a_propos"),
    path("annuaire/", views.annuaire, name="annuaire"),
    path("annuaire/secteur/<slug:secteur>/", views.annuaire, name="annuaire_pour"),
    path("annuaire/mes-fiches/", views.mes_fiches, name="mes_fiches"),
    path("annuaire/mes-fiches/apercu/", views.markdown_preview, name="markdown_preview"),
    path("annuaire/mes-fiches/<slug:slug>/modifier/", views.fiche_modifier, name="fiche_modifier"),
    path("annuaire/mes-fiches/<slug:slug>/supprimer/", views.fiche_supprimer, name="fiche_supprimer"),
    path("annuaire/<slug:slug>/", views.entry_detail, name="entry_detail"),
    path("annuaire/<slug:slug>/revendiquer/", views.claim_entry_ownership, name="claim_entry_ownership"),
    path("annuaire/<slug:slug>/abonnement/", views.toggle_subscription, name="toggle_subscription"),
    path("annuaire/<slug:slug>/publication/", views.toggle_publication, name="toggle_publication"),
    path("annuaire/<slug:slug>/raccourci/", views.toggle_shortcut, name="toggle_shortcut"),
    path("raccourcis/<slug:slug>/raccourci/<str:direction>/", views.reorder_shortcut, name="reorder_shortcut"),
    path("raccourcis/glisser/", views.reorder_shortcuts, name="reorder_shortcuts"),
    path("groupes/<slug:slug>/adherer/", views.toggle_membership, name="toggle_membership"),
    path("groupes/<slug:slug>/adherer/<str:direction>/", views.reorder_membership, name="reorder_membership"),
    path("groupes/glisser/", views.reorder_memberships, name="reorder_memberships"),
]
