from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.course_list, name="list"),
    path("my/", views.my_courses, name="my_courses"),
    path("manage/", views.manage_courses, name="manage"),
    path("<str:slug>/", views.course_detail, name="detail"),
    path("<str:slug>/enroll/", views.enroll_view, name="enroll"),
    path("<str:slug>/attendance/", views.attendance_view, name="attendance"),
    path("enrollment/<int:enrollment_id>/complete/", views.mark_complete, name="mark_complete"),
    path("enrollment/<int:enrollment_id>/evaluate/", views.evaluate, name="evaluate"),
    path("certificate/<int:certificate_id>/", views.certificate_pdf, name="certificate_pdf"),
]
