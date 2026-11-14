"""
Paymob gateway — واجهة جاهزة للتكامل (تُفعل بمفاتيح من Paymob dashboard).
ملاحظة: التحقق من الـ HMAC عند Paymob يكون على سلسلة مرتبة من حقول محددة —
راجع مستندات Paymob الرسمية وطابق القائمة مع نسختهم الحالية قبل الإنتاج.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from urllib.parse import urlencode

from django.conf import settings

from .base import GatewayNotConfigured, PaymentGateway

logger = logging.getLogger(__name__)

# حقول Paymob المستخدمة في توقيع HMAC (حسب مستندات unified checkout — تحقق منها)
_HMAC_FIELDS = [
    "amount_cents", "created_at", "currency", "error_occured", "has_parent_transaction",
    "id", "integration_id", "is_3d_secure", "is_auth", "is_capture", "is_refunded",
    "is_standalone_payment", "is_voided", "order", "owner", "pending",
    "source_data.pan", "source_data.sub_type", "source_data.type", "success",
]


class PaymobGateway(PaymentGateway):
    name = "paymob"

    def __init__(self):
        self.api_key = getattr(settings, "PAYMOB_API_KEY", "")
        self.integration_id = getattr(settings, "PAYMOB_INTEGRATION_ID", "")
        self.hmac_secret = getattr(settings, "PAYMOB_HMAC_SECRET", "")
        if not (self.api_key and self.integration_id and self.hmac_secret):
            raise GatewayNotConfigured("PAYMOB_API_KEY / PAYMOB_INTEGRATION_ID / PAYMOB_HMAC_SECRET مطلوبة في .env")

    def create_checkout(self, payment) -> dict:
        # التنفيذ الحقيقي: auth token → order register → payment key → iframe/URL
        # محجوز للمرحلة الإنتاجية — راجع README (قسم المدفوعات).
        raise NotImplementedError(
            "تكامل Paymob مؤجل حتى توفير المفاتيح — بدّل PAYMENT_PROVIDER=mock للتجربة"
        )

    def verify_webhook(self, headers, body: bytes) -> tuple[bool, dict]:
        try:
            data = json.loads(body.decode() or "{}")
        except json.JSONDecodeError:
            return False, {"error": "bad json"}
        obj = data.get("obj", data)
        received = (headers.get("hmac") or data.get("hmac") or "").strip()

        def field(name: str) -> str:
            cur = obj
            for part in name.split("."):
                cur = (cur or {}).get(part, "")
            if isinstance(cur, bool):
                return "true" if cur else "false"
            return str(cur)

        concatenated = "".join(field(f) for f in _HMAC_FIELDS)
        expected = hmac.new(self.hmac_secret.encode(), concatenated.encode(), hashlib.sha512).hexdigest()
        if not hmac.compare_digest(expected, received):
            logger.warning("Paymob webhook HMAC mismatch")
            return False, {"error": "bad hmac"}
        return True, obj
