from __future__ import annotations

import datetime

from apps.core.images import clean_photo as validate_photo
from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _, ngettext

from .models import Dependent, Profile, User
from .validators import validate_egyptian_phone, validate_national_id

GOVERNORATES = [
    "القاهرة", "الجيزة", "الإسكندرية", "القليوبية", "الدقهلية", "الشرقية", "الغربية",
    "المنوفية", "البحيرة", "كفر الشيخ", "دمياط", "بورسعيد", "الإسماعيلية", "السويس",
    "الفيوم", "بني سويف", "المنيا", "أسيوط", "سوهاج", "قنا", "الأقصر", "أسوان",
    "البحر الأحمر", "الوادي الجديد", "مطروح", "شمال سيناء", "جنوب سيناء",
]


class StyledFormMixin:
    """Give every widget the .input class automatically + mark invalid fields."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            # always keep the design-system input class — even if the widget already carries custom classes
            existing = (widget.attrs.get("class") or "").split()
            if "input" not in existing:
                existing.append("input")
            widget.attrs["class"] = " ".join(existing)
            if self.is_bound and name in self.errors:
                widget.attrs["class"] = widget.attrs["class"] + " input-error"
                widget.attrs["aria-invalid"] = "true"


class EgyptianPhoneMixin:
    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip().replace(" ", "")
        validate_egyptian_phone(phone)
        return phone


class RegisterForm(StyledFormMixin, EgyptianPhoneMixin, forms.Form):
    full_name_ar = forms.CharField(label=_("الاسم بالعربي"), max_length=120)
    full_name_en = forms.CharField(label=_("الاسم بالإنجليزي (اختياري)"), max_length=120, required=False)
    phone = forms.CharField(label=_("رقم الموبايل"), max_length=15, widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "dir": "ltr"}))
    email = forms.EmailField(label=_("البريد الإلكتروني"), max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email", "inputmode": "email", "dir": "ltr"}))
    password1 = forms.CharField(label=_("كلمة السر"), widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), max_length=128)
    password2 = forms.CharField(label=_("تأكيد كلمة السر"), widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), max_length=128)

    def clean_password2(self):
        p1, p2 = self.cleaned_data.get("password1"), self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError(_("كلمتا السر غير متطابقتين."))
        validate_password(p1)
        return p2

    def clean_phone(self):
        phone = super().clean_phone()
        user = User.objects.filter(phone=phone).first()
        if user and user.is_active:
            raise forms.ValidationError(_("يوجد حساب مفعّل بهذا الرقم بالفعل — سجّل الدخول بدلًا من ذلك."))
        return phone

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        return email


class LoginForm(StyledFormMixin, EgyptianPhoneMixin, forms.Form):
    phone = forms.CharField(label=_("رقم الموبايل"), max_length=15, widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "username", "dir": "ltr", "autofocus": True}))
    password = forms.CharField(label=_("كلمة السر"), widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


class OTPVerifyForm(StyledFormMixin, forms.Form):
    code = forms.CharField(label=_("رمز التحقق (٦ أرقام)"), max_length=6, min_length=6, widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code", "dir": "ltr", "class": "tracking-[0.5em] text-center text-2xl font-black"}))

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        if not code.isdigit():
            raise forms.ValidationError(_("الرمز أرقام فقط."))
        return code


class ForgotPasswordForm(StyledFormMixin, EgyptianPhoneMixin, forms.Form):
    phone = forms.CharField(label=_("رقم الموبايل"), max_length=15, widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "dir": "ltr"}))


class ResetPasswordForm(StyledFormMixin, forms.Form):
    password1 = forms.CharField(label=_("كلمة السر الجديدة"), widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), max_length=128)
    password2 = forms.CharField(label=_("تأكيد كلمة السر"), widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), max_length=128)

    def clean_password2(self):
        p1, p2 = self.cleaned_data.get("password1"), self.cleaned_data.get("password2")
        if p1 and p1 != p2:
            raise forms.ValidationError(_("كلمتا السر غير متطابقتين."))
        validate_password(p1)
        return p2


class _DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs={**(attrs or {}), "placeholder": "YYYY-MM-DD"}, format="%Y-%m-%d")


class ProfileForm(StyledFormMixin, forms.ModelForm):
    birth_date = forms.DateField(required=False, label=_("تاريخ الميلاد"), widget=_DateInput(), input_formats=["%Y-%m-%d"])

    class Meta:
        model = Profile
        fields = [
            "full_name_ar", "full_name_en", "birth_date", "gender", "national_id",
            "address", "governorate", "photo", "emergency_contact_name",
            "emergency_contact_phone", "health_notes", "shirt_size",
        ]
        widgets = {
            "full_name_ar": forms.TextInput(attrs={"autocomplete": "name"}),
            "full_name_en": forms.TextInput(attrs={"autocomplete": "name", "dir": "ltr"}),
            "national_id": forms.TextInput(attrs={"inputmode": "numeric", "dir": "ltr", "autocomplete": "off"}),
            "emergency_contact_phone": forms.TextInput(attrs={"inputmode": "tel", "dir": "ltr"}),
            "address": forms.TextInput(attrs={"autocomplete": "street-address"}),
            "health_notes": forms.Textarea(attrs={"rows": 2}),
            "photo": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp,image/heic,image/heif,*/*"}),
        }

    def clean_photo(self):
        return validate_photo(self.cleaned_data.get("photo"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["governorate"] = forms.ChoiceField(label=_("المحافظة"), choices=[(g, g) for g in GOVERNORATES])

    def clean_national_id(self):
        nid = (self.cleaned_data.get("national_id") or "").strip()
        validate_national_id(nid)
        return nid

    def clean_emergency_contact_phone(self):
        phone = (self.cleaned_data.get("emergency_contact_phone") or "").strip().replace(" ", "")
        if phone:
            validate_egyptian_phone(phone)
        return phone


class DependentForm(StyledFormMixin, forms.ModelForm):
    birth_date = forms.DateField(required=True, label=_("تاريخ الميلاد"), widget=_DateInput(), input_formats=["%Y-%m-%d"])

    class Meta:
        model = Dependent
        fields = ["full_name_ar", "full_name_en", "birth_date", "gender", "relation", "national_id", "health_notes", "photo"]
        widgets = {
            "full_name_en": forms.TextInput(attrs={"dir": "ltr"}),
            "national_id": forms.TextInput(attrs={"inputmode": "numeric", "dir": "ltr", "autocomplete": "off"}),
            "health_notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_photo(self):
        return validate_photo(self.cleaned_data.get("photo"))

    def clean_national_id(self):
        nid = (self.cleaned_data.get("national_id") or "").strip()
        validate_national_id(nid)
        return nid

    def clean_birth_date(self):
        bd = self.cleaned_data.get("birth_date")
        if bd and bd > datetime.date.today():
            raise forms.ValidationError(_("تاريخ الميلاد لا يمكن أن يكون في المستقبل."))
        if bd and (datetime.date.today().year - bd.year) >= 18:
            raise forms.ValidationError(_("التابع يجب أن يكون أقل من 18 سنة — الأعضاء الكبار يسجلون بأنفسهم."))
        return bd
