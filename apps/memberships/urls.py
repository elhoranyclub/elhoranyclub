from django.urls import path

from . import views

app_name = "memberships"

urlpatterns = [
    path("", views.my_memberships, name="my"),
    path("renew/", views.renew_step1, name="renew"),
    path("renew/2/", views.renew_step2, name="renew_step2"),
    path("renew/3/", views.renew_step3, name="renew_step3"),
    path("renew/done/<str:reference>/", views.renew_done, name="renew_done"),
]
