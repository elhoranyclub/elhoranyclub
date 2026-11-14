from django.urls import path

from . import views

app_name = "trips"

urlpatterns = [
    path("", views.trip_list, name="list"),
    path("my-bookings/", views.my_bookings, name="my_bookings"),
    path("booking/<int:booking_id>/cancel/", views.cancel_my_booking, name="cancel"),
    path("<str:slug>/", views.trip_detail, name="detail"),
    path("<str:slug>/book/", views.book_view, name="book"),
    path("<str:slug>/roster/", views.roster_view, name="roster"),
    path("<str:slug>/roster.csv", views.roster_csv, name="roster_csv"),
    path("<str:slug>/attendance/", views.attendance_view, name="attendance"),
]
