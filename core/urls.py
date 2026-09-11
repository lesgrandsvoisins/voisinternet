from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("je-vois/", views.je_vois, name="je_vois"),
    path("je-vois/anonyme/creer/", views.create_anonymous, name="create_anonymous"),
    path("je-vois/anonyme/retrouver/", views.recover_anonymous, name="recover_anonymous"),
    path("je-vois/anonyme/oublier/", views.forget_anonymous, name="forget_anonymous"),
    path("je-vois/anonyme/rattacher/", views.link_anonymous, name="link_anonymous"),
    path("tu-vois/", TemplateView.as_view(template_name="core/tu_vois.html"), name="tu_vois"),
    path("il-ou-elle-voit/", TemplateView.as_view(template_name="core/il_ou_elle_voit.html"),
         name="il_ou_elle_voit"),
    path("nous-voyons/", TemplateView.as_view(template_name="core/nous_voyons.html"), name="nous_voyons"),
    path("vous-voyez/", views.vous_voyez, name="vous_voyez"),
    path("vous-voyez/<slug:slug>/raccourci/", views.toggle_shortcut, name="toggle_shortcut"),
    path("ils-et-elles-voient/", views.ils_et_elles_voient, name="ils_et_elles_voient"),
]
