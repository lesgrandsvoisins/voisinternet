from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("account/", views.account, name="account"),
    path("account/anonyme/creer/", views.create_anonymous, name="create_anonymous"),
    path("account/anonyme/retrouver/", views.recover_anonymous, name="recover_anonymous"),
    path("account/anonyme/oublier/", views.forget_anonymous, name="forget_anonymous"),
    path("account/anonyme/rattacher/", views.link_anonymous, name="link_anonymous"),
    path("agenda/", TemplateView.as_view(template_name="core/agenda.html"), name="agenda"),
    path("contributions/", views.contributions, name="contributions"),
    path("grandsvoisins/", TemplateView.as_view(template_name="core/grandsvoisins.html"), name="grandsvoisins"),
    path("annuaire/", views.annuaire, name="annuaire"),
    path("annuaire/secteur/<slug:secteur>/", views.annuaire, name="annuaire_pour"),
    path("annuaire/<slug:slug>/raccourci/", views.toggle_shortcut, name="toggle_shortcut"),
    path("account/<slug:slug>/raccourci/<str:direction>/", views.reorder_shortcut, name="reorder_shortcut"),
    path("account/<slug:slug>/adherer/", views.toggle_membership, name="toggle_membership"),
    path("account/<slug:slug>/adherer/<str:direction>/", views.reorder_membership, name="reorder_membership"),
    path("civisme/", views.civisme, name="civisme"),
    path("arts-plastiques/", views.arts_plastiques, name="arts_plastiques"),
    path("numerique/", views.numerique, name="numerique"),
]
