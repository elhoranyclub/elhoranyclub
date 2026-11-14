from django import forms
from django.utils.translation import gettext_lazy as _

from .models import ContactMessage


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "phone", "email", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "phone": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "dir": "ltr"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "dir": "ltr", "required": False}),
            "message": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")
        if self.is_bound:
            for name in self.errors:
                self.fields[name].widget.attrs["class"] += " input-error"

    def clean_phone(self):
        from apps.accounts.validators import validate_egyptian_phone

        phone = (self.cleaned_data.get("phone") or "").strip().replace(" ", "")
        # هاتف تواصل عادي — نقبل أيضًا 02 (أرضي)
        if phone.startswith("0") and not phone.startswith("01"):
            import re

            if not re.match(r"^0\d{8,10}$", phone):
                raise forms.ValidationError(_("رقم الهاتف غير صحيح."))
            return phone
        validate_egyptian_phone(phone)
        return phone
