"""Accounts views — registration, OTP, auth, profile, dependents, QR card."""
from __future__ import annotations

import base64
import io
import json
import logging
from urllib.parse import quote

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView
from django.core.cache import cache
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import (
    DependentForm,
    ForgotPasswordForm,
    LoginForm,
    OTPVerifyForm,
    ProfileForm,
    RegisterForm,
    ResetPasswordForm,
)
from .models import Dependent, OTP, Profile, User
from .otp import mask_email, send_otp
from apps.memberships.services import current_membership, late_fine

logger = logging.getLogger(__name__)

LOGIN_ATTEMPT_LIMIT = 5
LOGIN_LOCK_MINUTES = 15


def _login_lock_key(phone: str) -> str:
    return f"login-attempts:{phone}"


def _is_locked(phone: str) -> bool:
    return cache.get(_login_lock_key(phone), 0) >= LOGIN_ATTEMPT_LIMIT


def _register_failed_attempt(phone: str) -> None:
    key = _login_lock_key(phone)
    cache.set(key, cache.get(key, 0) + 1, timeout=LOGIN_LOCK_MINUTES * 60)


def _clear_attempts(phone: str) -> None:
    cache.delete(_login_lock_key(phone))


def _guide_redirect_url(user, next_url: str = "") -> str:
    """أول مرة يسجّل دخوله — نفتحله صفحة «اعرف الموقع أكتر» (فيديو التدريب).

    وكمان لو صلاحيته اتغيّرت (من عضو لـ مدخل بيانات مثلًا) — الفيديو الجديد
    يعرض تاني عشان يشوف الجديد.

    بترجع رابط التوجيه، أو نص فاضي لو المفروض متعرضشلهوش حاجة.
    """
    from apps.pages.views import guide_role

    profile = Profile.objects.filter(user=user).first()
    if profile is None:
        return ""
    role = guide_role(user)
    if profile.guide_seen and profile.guide_seen_role == role:
        return ""
    target = next_url or reverse("core:home")
    return f"{reverse('pages:learn_more')}?welcome=1&next={quote(target)}"


# ------------------------------------------------------------ registration

def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    if not request.POST and _registration_closed():
        messages.warning(request, _("التسجيل العام متوقف مؤقتًا — تواصل مع الاستقبال."))
        return redirect("core:home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    phone=data["phone"],
                    defaults={"username": data["phone"], "is_active": False},
                )
                if not created and user.is_active:
                    messages.error(request, _("يوجد حساب مفعّل بهذا الرقم بالفعل."))
                    return redirect("accounts:login")
                user.set_password(data["password1"])
                user.first_name = data["full_name_ar"].split(" ", 1)[0]
                user.last_name = data["full_name_ar"].split(" ", 1)[1] if " " in data["full_name_ar"] else ""
                user.email = data["email"]
                user.save(update_fields=["password", "first_name", "last_name", "email"])
            if not send_otp(data["phone"], OTP.Purpose.REGISTER):
                messages.error(request, _("وصلت للحد الأقصى من الرسائل لهذا الرقم — حاول بعد ساعة."))
                return redirect("accounts:register")
            request.session["pending_phone"] = data["phone"]
            request.session["pending_purpose"] = OTP.Purpose.REGISTER
            request.session["pending_name_ar"] = data["full_name_ar"]
            request.session["pending_name_en"] = data["full_name_en"]
            messages.info(request, _("أرسلنا رمز تحقق إلى بريدك الإلكتروني — الكود صالح لمدة ١٠ دقائق"))
            return redirect("accounts:verify")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


def verify_view(request: HttpRequest) -> HttpResponse:
    phone = request.session.get("pending_phone")
    purpose = request.session.get("pending_purpose")
    if not phone or not purpose:
        return redirect("accounts:register")

    if request.method == "POST":
        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            otp = OTP.objects.filter(phone=phone, purpose=purpose, consumed=False).order_by("-created_at").first()
            if otp is None:
                messages.error(request, _("لا يوجد رمز نشط لهذا الرقم — اطلب رمزًا جديدًا."))
                return redirect("accounts:resend", purpose=purpose)
            ok, err = otp.verify(form.cleaned_data["code"])
            if ok:
                user = get_object_or_404(User, phone=phone)
                if purpose == OTP.Purpose.REGISTER:
                    user.is_active = True
                    user.save(update_fields=["is_active"])
                    profile, _created = Profile.objects.get_or_create(
                        user=user,
                        defaults={
                            "full_name_ar": request.session.get("pending_name_ar", user.first_name or phone),
                            "full_name_en": request.session.get("pending_name_en", ""),
                        },
                    )
                    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                    try:
                        from apps.notifications.services import notify_user

                        notify_user(
                            user=user,
                            type="welcome",
                            code="welcome",
                            context={"name": profile.full_name_ar, "ref": profile.membership_number},
                        )
                    except Exception:
                        pass
                    for key in ("pending_phone", "pending_purpose", "pending_name_ar", "pending_name_en"):
                        request.session.pop(key, None)
                    messages.success(request, _("أهلًا بك في مركز شباب الحوراني! تم إنشاء عضويتك."))
                    guide_url = _guide_redirect_url(user, reverse("accounts:card"))
                    if guide_url:
                        return redirect(guide_url)
                    return redirect("accounts:card")
                # RESET_PASSWORD
                request.session["reset_ok"] = True
                request.session["reset_phone"] = phone
                request.session.pop("pending_phone", None)
                request.session.pop("pending_purpose", None)
                return redirect("accounts:forgot_new")
            messages.error(request, err)
    else:
        form = OTPVerifyForm()
    user = User.objects.filter(phone=phone).first()
    masked_email = mask_email(user.email) if user and user.email else None
    masked_phone = phone[:2] + "•••" + phone[-2:]
    return render(request, "accounts/verify.html", {"form": form, "masked_phone": masked_phone, "masked_email": masked_email, "purpose": purpose})


def resend_view(request: HttpRequest, purpose: str) -> HttpResponse:
    phone = request.session.get("pending_phone")
    if not phone or purpose not in dict(OTP.Purpose.choices):
        return redirect("accounts:register")
    if send_otp(phone, purpose):
        messages.success(request, _("تم إرسال رمز جديد."))
    else:
        messages.error(request, _("وصلت للحد الأقصى من الرسائل — حاول بعد ساعة."))
    return redirect("accounts:verify")


# ------------------------------------------------------------------ auth

def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["phone"]
            if _is_locked(phone):
                messages.error(request, _("محاولات خاطئة كثيرة — الحساب مقفول ١٥ دقيقة. حاول لاحقًا."))
                return render(request, "accounts/login.html", {"form": form, "next": next_url})
            user = authenticate(request, username=phone, password=form.cleaned_data["password"])
            if user is None:
                inactive = User.objects.filter(phone=phone, is_active=False).exists()
                if inactive:
                    request.session["pending_phone"] = phone
                    request.session["pending_purpose"] = OTP.Purpose.REGISTER
                    send_otp(phone, OTP.Purpose.REGISTER)
                    messages.info(request, _("حسابك لسه غير مفعّل — بعتنالك رمز تفعيل جديد."))
                    return redirect("accounts:verify")
                _register_failed_attempt(phone)
                messages.error(request, _("رقم الموبايل أو كلمة السر غير صحيحة."))
            else:
                _clear_attempts(phone)
                login(request, user)
                guide_url = _guide_redirect_url(user, next_url)
                if guide_url:
                    return redirect(guide_url)
                return redirect(next_url or "core:home")
    else:
        form = LoginForm()
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(request, _("تم تسجيل خروجك — نراك قريبًا!"))
    return redirect("core:home")


# ------------------------------------------------------------- password

# لو عايز نرجع نخفي وجود الحساب تمامًا (زي الأول) — خلّيها False
SHOW_MISSING_ACCOUNT_HINT = True


def _reset_account_state(phone: str) -> tuple[str, str | None]:
    """يرجّع (حالة الحساب، الإيميل المخفي) — حالة من: missing / no_email / ok."""
    user = User.objects.filter(phone=phone, is_active=True).first()
    if user is None:
        return ("missing", None)
    if not user.email:
        return ("no_email", None)
    return ("ok", mask_email(user.email))


def forgot_view(request: HttpRequest) -> HttpResponse:
    """الخطوة 1: اكتب رقم موبايلك — لو الحساب موجود هتاخدك لشاشة التأكيد."""
    if request.method == "POST":
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["phone"]
            state, masked = _reset_account_state(phone)
            # إعداد الجلسة دائمًا بنفس الشكل — لا نكشف إن كان الرقم موجودًا من عدمه
            request.session["pending_phone"] = phone
            request.session["pending_purpose"] = OTP.Purpose.RESET_PASSWORD
            request.session.pop("reset_sent", None)
            request.session["reset_state"] = state
            request.session["reset_mask_email"] = masked
            return redirect("accounts:forgot_confirm")
    else:
        form = ForgotPasswordForm()
    return render(request, "accounts/forgot.html", {"form": form})


def forgot_confirm_view(request: HttpRequest) -> HttpResponse:
    """الخطوة 2: تبعتك على شاشتينها إيميلك مخفف وتأكيد — بعدين يتبعت الرمز."""
    phone = request.session.get("pending_phone")
    purpose = request.session.get("pending_purpose")
    if not phone or purpose != OTP.Purpose.RESET_PASSWORD:
        return redirect("accounts:forgot")

    if request.method == "POST":
        state, masked = _reset_account_state(phone)
        if state == "ok":
            send_otp(phone, OTP.Purpose.RESET_PASSWORD)
        request.session["reset_sent"] = True
        request.session["reset_state"] = state
        request.session["reset_mask_email"] = masked
        return redirect("accounts:forgot_sent")

    masked = request.session.get("reset_mask_email")
    state = request.session.get("reset_state", "ok")
    return render(request, "accounts/forgot_confirm.html", {
        "masked_email": masked,
        "has_user": bool(masked),
        "account_state": state,
        "show_hint": SHOW_MISSING_ACCOUNT_HINT,
    })


def forgot_sent_view(request: HttpRequest) -> HttpResponse:
    """الخطوة 3: تم إرسال التعليمات — عودة لتسجيل الدخول + رابط ادخال الكود."""
    if not request.session.get("reset_sent"):
        return redirect("accounts:forgot")
    masked = request.session.get("reset_mask_email")
    state = request.session.get("reset_state", "ok")
    return render(request, "accounts/forgot_sent.html", {
        "masked_email": masked,
        "account_state": state,
        "show_hint": SHOW_MISSING_ACCOUNT_HINT,
    })


def forgot_new_view(request: HttpRequest) -> HttpResponse:
    if not request.session.get("reset_ok"):
        messages.warning(request, _("افتح الرابط من رسالة التحقق أولًا."))
        return redirect("accounts:forgot")
    if request.method == "POST":
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            phone = request.session.get("reset_phone")
            user = User.objects.filter(phone=phone).first() if phone else None
            if user is None:
                messages.error(request, _("حدث خطأ — ابدأ من جديد."))
                return redirect("accounts:forgot")
            user.set_password(form.cleaned_data["password1"])
            user.save(update_fields=["password"])
            request.session.pop("reset_ok", None)
            request.session.pop("reset_phone", None)
            messages.success(request, _("تم تغيير كلمة السر — سجّل الدخول بكلمة السر الجديدة."))
            return redirect("accounts:login")
    else:
        form = ResetPasswordForm()
    return render(request, "accounts/forgot_new.html", {"form": form})


class StyledPasswordChangeForm(PasswordChangeForm):
    """PasswordChangeForm + the design-system input classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "input")
            if self.is_bound and name in self.errors:
                field.widget.attrs["class"] += " input-error"


class CustomPasswordChangeView(PasswordChangeView):
    form_class = StyledPasswordChangeForm
    template_name = "accounts/password_change.html"
    success_url = "/accounts/password-change/done/"

    def form_valid(self, form):
        update_session_auth_hash(self.request, form.user)
        messages.success(self.request, _("تم تغيير كلمة السر بنجاح."))
        return super().form_valid(form)


def password_change_done(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/password_change_done.html")


# ------------------------------------------------------------- profile

def _registration_closed() -> bool:
    try:
        from apps.core.models import SiteSettings

        return not SiteSettings.load().is_registration_open
    except Exception:
        return False


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    profile, _created = Profile.objects.get_or_create(user=request.user)
    dependents = request.user.dependents.order_by("birth_date")
    membership = current_membership(request.user)
    return render(request, "accounts/profile.html", {"profile": profile, "dependents": dependents, "membership": membership})


@login_required
def profile_edit_view(request: HttpRequest) -> HttpResponse:
    profile, _created = Profile.objects.get_or_create(
        user=request.user,
        defaults={"full_name_ar": request.user.get_full_name() or request.user.phone},
    )
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, _("تم حفظ بياناتك."))
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "accounts/profile_edit.html", {"form": form, "profile": profile})


# --------------------------------------------------------------- card

@login_required
def card_view(request: HttpRequest) -> HttpResponse:
    profile, _created = Profile.objects.get_or_create(
        user=request.user,
        defaults={"full_name_ar": request.user.get_full_name() or request.user.phone},
    )
    card_fine = late_fine(request.user, for_user=request.user)
    payload = json.dumps({"n": profile.membership_number, "p": request.user.phone}, ensure_ascii=False)
    qr = qrcode.QRCode(box_size=9, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0e2a47", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return render(request, "accounts/card.html", {"profile": profile, "qr_b64": qr_b64, "card_fine": card_fine})


# --------------------------------------------------------- dependents

@login_required
def dependents_view(request: HttpRequest) -> HttpResponse:
    dependents = request.user.dependents.order_by("birth_date")
    return render(request, "accounts/dependents.html", {"dependents": dependents})


@login_required
def dependent_add_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = DependentForm(request.POST, request.FILES)
        if form.is_valid():
            dependent = form.save(commit=False)
            dependent.guardian = request.user
            dependent.save()
            messages.success(request, _("تم إضافة التابع ورقم عضويته: %(n)s") % {"n": dependent.membership_number})
            return redirect("accounts:dependents")
    else:
        form = DependentForm()
    return render(request, "accounts/dependent_form.html", {"form": form})


@login_required
@require_POST
def dependent_delete_view(request: HttpRequest, dependent_id: int) -> HttpResponse:
    dependent = get_object_or_404(Dependent, id=dependent_id, guardian=request.user)
    name = dependent.full_name_ar
    dependent.delete()
    messages.success(request, _("تم حذف (%(name)s) من تابعيك.") % {"name": name})
    return redirect("accounts:dependents")
