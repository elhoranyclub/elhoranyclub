from django.urls import path

from . import views

app_name = "tournaments"

urlpatterns = [
    path("", views.tournament_list, name="list"),
    path("my-registrations/", views.my_registrations, name="my_registrations"),
    path("live/", views.live, name="live"),
    path("manage/", views.manage_matches, name="manage_matches"),
    path("manage/match/<int:match_id>/result/", views.enter_result, name="enter_result"),
    path("registration/<int:registration_id>/<str:action>/", views.staff_set_status, name="staff_set_status"),
    path("<str:slug>/", views.tournament_detail, name="detail"),
    path("<str:slug>/register/", views.register, name="register"),
]
