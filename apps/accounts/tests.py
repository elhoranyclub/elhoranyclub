"""Critical-path tests: registration, OTP, membership numbering, dependents."""
from __future__ import annotations

import datetime

import pytest
from django.urls import reverse

from apps.accounts.models import Dependent, OTP, Profile, User, generate_membership_number
from apps.accounts.validators import validate_egyptian_phone
from django.core.exceptions import ValidationError


@pytest.mark.django_db
class TestPhones:
    @pytest.mark.parametrize("phone", ["01012345678", "01112345678", "01212345678", "01512345678"])
    def test_valid(self, phone):
        validate_egyptian_phone(phone)

    @pytest.mark.parametrize("phone", ["0101234567", "010123456789", "02012345678", "010abcdefgh", ""])
    def test_invalid(self, phone):
        with pytest.raises(ValidationError):
            validate_egyptian_phone(phone)


@pytest.mark.django_db
class TestMembershipNumber:
    def test_format_and_unique(self):
        u1 = User.objects.create_user(username="t1", phone="01000000011", password="x", is_active=True)
        u2 = User.objects.create_user(username="t2", phone="01000000012", password="x", is_active=True)
        p1 = Profile.objects.create(user=u1, full_name_ar="اختبار واحد")
        p2 = Profile.objects.create(user=u2, full_name_ar="اختبار اتنين")
        assert p1.membership_number.isdigit()
        assert int(p2.membership_number) == int(p1.membership_number) + 1


@pytest.mark.django_db
class TestRegistrationFlow:
    def _register(self, client):
        return client.post(reverse("accounts:register"), {
            "full_name_ar": "اختبار المستخدم",
            "full_name_en": "Test User",
            "phone": "01098765432",
            "email": "test@example.com",
            "password1": "StrongPass#2026",
            "password2": "StrongPass#2026",
        }, follow=True)

    def test_full_flow_creates_profile_and_logs_in(self, client):
        response = self._register(client)
        assert response.status_code == 200
        user = User.objects.get(phone="01098765432")
        assert user.is_active is False
        otp2, code = OTP.issue("01098765432", "register")
        response = client.post(reverse("accounts:verify"), {"code": code}, follow=True)
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.is_active is True
        assert Profile.objects.get(user=user).membership_number.isdigit()

    def test_wrong_code_exhausts_attempts(self, client):
        self._register(client)
        for _ in range(OTP.MAX_ATTEMPTS):
            client.post(reverse("accounts:verify"), {"code": "000000"})
        otp = OTP.objects.filter(phone="01098765432", purpose="register").latest("created_at")
        assert otp.attempts >= OTP.MAX_ATTEMPTS


@pytest.mark.django_db
class TestDependents:
    def _guardian(self):
        u = User.objects.create_user(username="g1", phone="01099998877", password="pw12345#", is_active=True)
        Profile.objects.create(user=u, full_name_ar="ولي الأمر")
        return u

    def test_add_and_age_guard(self, client):
        guardian = self._guardian()
        client.force_login(guardian)
        response = client.post(reverse("accounts:dependent_add"), {
            "full_name_ar": "ابن اختبار",
            "full_name_en": "",
            "birth_date": datetime.date.today().replace(year=datetime.date.today().year - 10).isoformat(),
            "gender": "M",
            "relation": "son",
            "national_id": "",
            "health_notes": "",
        }, follow=True)
        assert response.status_code == 200
        assert Dependent.objects.filter(guardian=guardian).count() == 1
        assert Dependent.objects.get(guardian=guardian).membership_number.isdigit()

    def test_adult_dependent_rejected(self, client):
        guardian = self._guardian()
        client.force_login(guardian)
        response = client.post(reverse("accounts:dependent_add"), {
            "full_name_ar": "تابع كبير",
            "full_name_en": "",
            "birth_date": "2000-01-01",
            "gender": "M",
            "relation": "son",
            "national_id": "",
            "health_notes": "",
        })
        assert response.status_code == 200
        assert Dependent.objects.filter(guardian=guardian).count() == 0


@pytest.mark.django_db
class TestPasswordReset:
    def test_unknown_phone_says_no_account_instead_of_fake_email(self, client):
        """رقم مش مسجّل: الموقع يقول «مفيش حساب» بدل ما يدّعي إنه بعت إيميل."""
        r = client.post(reverse("accounts:forgot"), {"phone": "01000000999"})
        assert r.status_code == 302
        assert reverse("accounts:forgot_confirm") in r.url
        r = client.get(reverse("accounts:forgot_confirm"))
        body = r.content.decode()
        assert r.status_code == 200
        assert "مفيش حساب مسجّل بهذا الرقم" in body
        assert "ابعت الرمز الآن" not in body  # ما بنبعتش كود لرقم مش موجود
        r = client.post(reverse("accounts:forgot_confirm"))
        assert r.status_code == 302
        assert reverse("accounts:forgot_sent") in r.url
        r = client.get(reverse("accounts:forgot_sent"))
        body = r.content.decode()
        assert "مفيش حساب بهذا الرقم" in body
        assert reverse("accounts:register") in body

    def test_account_without_email_says_no_email(self, client):
        User.objects.create_user(username="reset0", phone="01000000100", email="", password="x", is_active=True)
        client.post(reverse("accounts:forgot"), {"phone": "01000000100"})
        r = client.get(reverse("accounts:forgot_confirm"))
        assert "من غير إيميل مسجّل" in r.content.decode()

    def test_masked_email_shown_for_user_with_email(self, client):
        User.objects.create_user(username="reset1", phone="01000000101", email="saleh@example.com", password="x", is_active=True)
        r = client.post(reverse("accounts:forgot"), {"phone": "01000000101"})
        assert r.status_code == 302
        r = client.get(reverse("accounts:forgot_confirm"))
        body = r.content.decode()
        assert "sa***h@example.com" in body
        assert "saleh@example.com" not in body  # never reveal the full address

    def test_full_reset_flow_changes_password_and_logs_in(self, client):
        u = User.objects.create_user(username="reset2", phone="01000000102", email="full@example.com", password="OldPass#2026", is_active=True)
        client.post(reverse("accounts:forgot"), {"phone": "01000000102"})
        client.get(reverse("accounts:forgot_confirm"))
        client.post(reverse("accounts:forgot_confirm"))
        _otp, code = OTP.issue("01000000102", "reset")
        response = client.post(reverse("accounts:verify"), {"code": code}, follow=True)
        assert response.status_code == 200
        response = client.post(reverse("accounts:forgot_new"), {
            "password1": "NewPass#2026",
            "password2": "NewPass#2026",
        }, follow=True)
        assert response.status_code == 200
        client.logout()
        from django.contrib.auth import authenticate
        assert authenticate(username="01000000102", password="NewPass#2026") is not None
