from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("checkout/<str:reference>/", views.checkout, name="checkout"),
    path("checkout/<str:reference>/online/", views.pay_online, name="pay_online"),
    path("checkout/<str:reference>/wallet/", views.pay_wallet, name="pay_wallet"),
    path("checkout/<str:reference>/cash/", views.pay_cash, name="pay_cash"),
    path("mock/<str:token>/", views.mock_pay, name="mock_pay"),
    path("cash/<str:reference>/", views.cash, name="cash"),
    path("my/", views.my_payments, name="my"),
    path("receipt/<str:reference>/", views.receipt, name="receipt"),
    path("receipt/<str:reference>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("staff/", views.staff_review, name="staff_review"),
    path("staff/cash/<str:reference>/confirm/", views.staff_confirm_cash, name="staff_confirm_cash"),
    path("staff/proof/<int:proof_id>/<str:action>/", views.staff_review_proof, name="staff_review_proof"),
    path("proof/<int:proof_id>/file/", views.proof_file, name="proof_file"),
    path("webhook/", views.webhook, name="webhook"),
]
