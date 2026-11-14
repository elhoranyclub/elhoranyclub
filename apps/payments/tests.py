"""Critical payment paths: confirm (idempotent), webhook, wallet, staff cash."""
import hashlib
import hmac
import io
import json
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Profile, User
from apps.memberships.models import Membership, MembershipType
from apps.payments.models import Invoice, Payment, PaymentProof
from apps.memberships.services import request_renewal
from apps.payments.services import create_payment


def _mtype():
    return MembershipType.objects.create(name_ar="فردي", name_en="Individual", price=Decimal("1200.00"), duration_months=12)


def _user(phone="01044440001", name="عميل ديمو", is_staff=False):
    u = User.objects.create_user(username=phone, phone=phone, password="pw#12345", is_active=True, is_staff=is_staff)
    Profile.objects.create(user=u, full_name_ar=name)
    return u


def _pending_membership(user, mtype):
    membership, err = request_renewal(user=user, membership_type=mtype, for_user=user)
    assert err is None and membership is not None
    return membership


def _png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 40, 90)).save(buf, "PNG")
    return buf.getvalue()


@pytest.mark.django_db
class TestOnlineFlow:
    def test_checkout_online_activates_membership_and_invoice(self, client):
        mtype = _mtype()
        user = _user()
        membership = _pending_membership(user, mtype)
        client.force_login(user)

        r = client.post(reverse("payments:pay_online", args=[membership.reference]))
        assert r.status_code == 302

        payment = membership.payments.get()
        assert payment.method == Payment.Method.ONLINE and payment.provider == "mock"

        # mock gateway returns to a signed token page
        from django.core import signing

        token = signing.dumps({"ref": payment.reference}, salt="pay-mock-token")
        r2 = client.get(reverse("payments:mock_pay", args=[token]))
        assert r2.status_code == 200

        r3 = client.post(reverse("payments:mock_pay", args=[token]))
        assert r3.status_code == 302

        payment.refresh_from_db()
        membership.refresh_from_db()
        assert payment.status == Payment.Status.PAID
        assert membership.status == Membership.Status.ACTIVE
        assert Invoice.objects.filter(payment=payment).exists()

        # idempotency: re-POST does not duplicate or change anything
        client.post(reverse("payments:mock_pay", args=[token]))
        assert Invoice.objects.filter(payment=payment).count() == 1

    def test_webhook_hmac_and_idempotency(self, client):
        mtype = _mtype()
        user = _user()
        membership = _pending_membership(user, mtype)
        payment = create_payment(member=user, amount=membership.total_amount, kind="membership", method="online", membership=membership)
        payment.provider_ref = "MOCK-TEST-1"
        payment.save(update_fields=["provider_ref"])

        body = json.dumps({"provider_ref": "MOCK-TEST-1"}).encode()
        secret = b"mock-secret"
        sig = hmac.new(secret, body, hashlib.sha256).hexdigest()

        bad = client.post("/payments/webhook/", data=body, content_type="application/json", HTTP_X_MOCK_SIGNATURE="wrong")
        assert bad.status_code == 400

        ok = client.post("/payments/webhook/", data=body, content_type="application/json", HTTP_X_MOCK_SIGNATURE=sig)
        assert ok.status_code == 200
        payment.refresh_from_db()
        membership.refresh_from_db()
        assert payment.status == Payment.Status.PAID
        assert membership.status == Membership.Status.ACTIVE

        again = client.post("/payments/webhook/", data=body, content_type="application/json", HTTP_X_MOCK_SIGNATURE=sig)
        assert again.status_code == 200 and b"duplicate" in again.content
        assert Invoice.objects.count() == 1


@pytest.mark.django_db
class TestWalletAndCash:
    def test_wallet_upload_goes_to_review(self, client):
        mtype = _mtype()
        user = _user()
        membership = _pending_membership(user, mtype)
        client.force_login(user)
        image = SimpleUploadedFile("receipt.png", _png_bytes(), content_type="image/png")
        r = client.post(
            reverse("payments:pay_wallet", args=[membership.reference]),
            {"proof_image": image, "amount_claimed": str(membership.total_amount), "operation_number": "INS123", "channel": "wallet"},
        )
        assert r.status_code == 302
        proof = PaymentProof.objects.get()
        assert proof.status == PaymentProof.Status.PENDING
        assert proof.payment.status == Payment.Status.PENDING

    def test_staff_confirm_cash_activates_membership(self, client):
        mtype = _mtype()
        user = _user()
        staff = _user("01044440002", "موظف الاستقبال", is_staff=True)
        membership = _pending_membership(user, mtype)
        payment = create_payment(member=user, amount=membership.total_amount, kind="membership", method="cash", membership=membership)

        client.force_login(staff)
        r = client.post(reverse("payments:staff_confirm_cash", args=[payment.reference]))
        assert r.status_code == 302
        payment.refresh_from_db()
        membership.refresh_from_db()
        assert payment.status == Payment.Status.PAID
        assert membership.status == Membership.Status.ACTIVE
        assert Invoice.objects.filter(payment=payment).exists()

    def test_member_cannot_open_staff_review(self, client):
        user = _user()
        client.force_login(user)
        r = client.get(reverse("payments:staff_review"))
        assert r.status_code in (302, 403)


@pytest.mark.django_db
class TestInvoicePDF:
    def test_pdf_endpoint_returns_pdf(self, client):
        mtype = _mtype()
        user = _user()
        membership = _pending_membership(user, mtype)
        payment = create_payment(member=user, amount=membership.total_amount, kind="membership", method="cash", membership=membership)
        from apps.payments.services import confirm_payment

        confirm_payment(payment)
        client.force_login(user)
        r = client.get(reverse("payments:invoice_pdf", args=[payment.reference]))
        assert r.status_code == 200
        assert r["Content-Type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
