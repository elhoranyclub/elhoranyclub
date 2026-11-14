from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.event_list, name="list"),
    path("my/", views.my_registrations, name="my_registrations"),
    path("<int:event_id>/register/", views.event_register, name="register"),
    path("registration/<int:registration_id>/cancel/", views.event_cancel, name="cancel"),
    path("<str:slug>/", views.event_detail, name="detail"),
]
