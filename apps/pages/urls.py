from django.urls import path

from . import views

app_name = "pages"

urlpatterns = [
    path("about/", views.about, name="about"),
    path("facilities/", views.facilities, name="facilities"),
    path("pricing/", views.pricing, name="pricing"),
    path("regulation/", views.regulation, name="regulation"),
    path("faq/", views.faq, name="faq"),
    path("contact/", views.contact, name="contact"),
    path("learn-more/", views.learn_more, name="learn_more"),
    path("learn-more/done/", views.learn_more_done, name="learn_more_done"),
    path("guide/", views.guide_view, name="guide"),
]
