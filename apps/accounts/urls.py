"""Accounts URLs — auth screens + ledger (دفتر الأعضاء) management for staff."""
from django.urls import path

from . import registry_views, views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    path("verify/", views.verify_view, name="verify"),
    path("resend/<str:purpose>/", views.resend_view, name="resend"),
    path("forgot/", views.forgot_view, name="forgot"),
    path("forgot/confirm/", views.forgot_confirm_view, name="forgot_confirm"),
    path("forgot/sent/", views.forgot_sent_view, name="forgot_sent"),
    path("forgot/new/", views.forgot_new_view, name="forgot_new"),
    path("password-change/", views.CustomPasswordChangeView.as_view(), name="password_change"),
    path("password-change/done/", views.password_change_done, name="password_change_done"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.profile_edit_view, name="profile_edit"),
    path("card/", views.card_view, name="card"),
    path("dependents/", views.dependents_view, name="dependents"),
    path("dependents/add/", views.dependent_add_view, name="dependent_add"),
    path("dependents/<int:dependent_id>/delete/", views.dependent_delete_view, name="dependent_delete"),
    # خدماتي — درگاه للطلبات (تفعيل كامل مع المرحلة 4)
    path("my-services/", views.profile_view, name="my_services"),
]
