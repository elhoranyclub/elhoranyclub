from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("export/members.csv", views.export_members_csv, name="export_members"),
    path("export/payments.csv", views.export_payments_csv, name="export_payments"),
]
