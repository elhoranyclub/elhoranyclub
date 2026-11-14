import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

EGYPT_PHONE_RE = re.compile(r"^01[0125]\d{8}$")
NATIONAL_ID_RE = re.compile(r"^\d{14}$")


def validate_egyptian_phone(value: str) -> None:
    value = (value or "").strip().replace(" ", "")
    if not EGYPT_PHONE_RE.match(value):
        raise ValidationError(_("رقم الموبايل غير صحيح — الصيغة 01xxxxxxxxx (مثل 01012345678)."))


def validate_national_id(value: str) -> None:
    value = (value or "").strip()
    if value and not NATIONAL_ID_RE.match(value):
        raise ValidationError(_("الرقم القومي يجب أن يكون 14 رقمًا."))
