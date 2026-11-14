from django.urls import path

from apps.accounts import registry_views
from . import views
from . import manage_views

app_name = "core"
from apps.core.search import search

urlpatterns = [
    path("", views.home, name="home"),
    path("coming-soon/<slug:section>/", views.coming_soon, name="coming_soon"),
    path("healthz", views.healthz, name="healthz"),
    path("offline/", views.offline, name="offline"),
    path("guide/video/<str:role>/", views.guide_video, name="guide_video"),
    path("search/", search, name="search"),
    # ---------- Manage console (staff-only, permission-filtered) ----------
    path("manage/registry/", registry_views.registry_list, name="registry_list"),
    path("manage/registry/<int:pk>/link/", registry_views.registry_link, name="registry_link"),
    path("manage/", manage_views.manage_index, name="manage_index"),
    path("manage/<str:app_label>/<str:model_name>/", manage_views.manage_list, name="manage_list"),
    path("manage/<str:app_label>/<str:model_name>/new/", manage_views.manage_create, name="manage_create"),
    path("manage/<str:app_label>/<str:model_name>/<int:pk>/edit/", manage_views.manage_edit, name="manage_edit"),
    path("manage/<str:app_label>/<str:model_name>/<int:pk>/delete/", manage_views.manage_delete, name="manage_delete"),
]
