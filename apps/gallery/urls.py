from django.urls import path

from . import views

app_name = "gallery"

urlpatterns = [
    path("", views.album_list, name="list"),
    path("<str:slug>/", views.album_detail, name="detail"),
]
