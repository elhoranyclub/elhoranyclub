from django import forms
from django.utils.translation import gettext_lazy as _

from .models import NotificationPreference


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = ["in_app", "email", "whatsapp", "sms"]
        widgets = {
            "in_app": forms.CheckboxInput(attrs={"class": "w-6 h-6 accent-[var(--brand-green)]"}),
            "email": forms.CheckboxInput(attrs={"class": "w-6 h-6 accent-[var(--brand-green)]"}),
            "whatsapp": forms.CheckboxInput(attrs={"class": "w-6 h-6 accent-[var(--brand-green)]"}),
            "sms": forms.CheckboxInput(attrs={"class": "w-6 h-6 accent-[var(--brand-green)]"}),
        }
        labels = {
            "in_app": _("داخل التطبيق (الجرس)"),
            "email": _("البريد الإلكتروني"),
            "whatsapp": _("واتساب"),
            "sms": _("رسائل نصية SMS"),
        }
