from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("account/", views.account, name="account"),
    path("recherche/", views.search, name="search"),
    path("etiquettes/", views.tag_list, name="tag_list"),
    path("etiquettes/<slug:slug>/", views.tag_detail, name="tag_detail"),
    path("auteur/<int:pk>/", views.author_detail, name="author_detail"),
    path("account/anonyme/creer/", views.create_anonymous, name="create_anonymous"),
    path("account/anonyme/retrouver/", views.recover_anonymous, name="recover_anonymous"),
    path("account/anonyme/oublier/", views.forget_anonymous, name="forget_anonymous"),
    path("account/anonyme/rattacher/", views.link_anonymous, name="link_anonymous"),
    path("account/raccourcis/", views.raccourcis, name="raccourcis"),
    path("account/groupes/", views.groupes, name="groupes"),
    path("account/dons/", views.faire_don, name="faire_don"),
    path("agenda/", views.agenda, name="agenda"),
    path("agenda/mes-evenements/", views.mes_evenements, name="mes_evenements"),
    path("agenda/mes-evenements/<int:pk>/modifier/", views.evenement_modifier, name="evenement_modifier"),
    path("agenda/mes-evenements/<int:pk>/supprimer/", views.evenement_supprimer, name="evenement_supprimer"),
    path("agenda/<int:pk>/", views.event_detail, name="event_detail"),
    path("agenda/<int:pk>/ics/", views.event_ics, name="event_ics"),
    path("agenda/<int:pk>/gerer/", views.claim_event_management, name="claim_event_management"),
    path("agenda/<int:pk>/interet/", views.toggle_event_interest, name="toggle_event_interest"),
    path(
        "agenda/<int:pk>/interet/notifications/",
        views.toggle_event_interest_notify, name="toggle_event_interest_notify",
    ),
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
    path(
        "annuaire/<slug:slug>/abonnement/notifications/",
        views.toggle_subscription_notify, name="toggle_subscription_notify",
    ),
    path("annuaire/<slug:slug>/publication/", views.toggle_publication, name="toggle_publication"),
    path("annuaire/<slug:slug>/raccourci/", views.toggle_shortcut, name="toggle_shortcut"),
    path(
        "account/raccourcis/<slug:slug>/raccourci/<str:direction>/",
        views.reorder_shortcut, name="reorder_shortcut",
    ),
    path("account/raccourcis/glisser/", views.reorder_shortcuts, name="reorder_shortcuts"),
    path("account/groupes/<slug:slug>/adherer/", views.toggle_membership, name="toggle_membership"),
    path(
        "account/groupes/<slug:slug>/adherer/<str:direction>/",
        views.reorder_membership, name="reorder_membership",
    ),
    path("account/groupes/glisser/", views.reorder_memberships, name="reorder_memberships"),
    path("administration/", views.administration, name="administration"),
    path(
        "administration/fiches/<int:pk>/",
        views.administration_review_claim, name="administration_review_claim",
    ),
    path(
        "administration/evenements/<int:pk>/demande/",
        views.administration_review_event_request, name="administration_review_event_request",
    ),
    path(
        "administration/evenements/<int:pk>/bascule/",
        views.administration_toggle_event, name="administration_toggle_event",
    ),
]
