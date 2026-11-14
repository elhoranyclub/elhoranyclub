from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("preferences/", views.preferences, name="preferences"),
    path("<int:notification_id>/read/", views.mark_read, name="mark_read"),
    path("mark-all/", views.mark_all, name="mark_all"),
]
