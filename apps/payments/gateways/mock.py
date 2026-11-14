"""
Mock gateway — للتطوير والتجربة بدل Paymob.
create_checkout ترجع {"kind": "mock", "token": ...} والجلسة تتحول لصفحة «دفع تجريبي».
لا يوجد اتصال شبكي ولا بيانات حقيقية هنا.
"""
from __future__ import annotations

import hashlib
import hmac
import json

from django.conf import settings

from .base import PaymentGateway


class MockGateway(PaymentGateway):
    name = "mock"

    def create_checkout(self, payment) -> dict:
        return {"kind": "mock", "token": payment.reference}

    def verify_webhook(self, headers, body: bytes) -> tuple[bool, dict]:
        secret = getattr(settings, "MOCK_WEBHOOK_SECRET", "mock-secret").encode()
        signature = b""
        for key, value in headers.items():
            if key.lower() == "x-mock-signature":
                signature = (value or b"").encode() if isinstance(value, str) else value
                break
        expected = hmac.new(secret, body, hashlib.sha256).hexdigest().encode()
        if not hmac.compare_digest(signature, expected):
            return False, {"error": "bad signature"}
        try:
            data = json.loads(body.decode() or "{}")
        except json.JSONDecodeError:
            return False, {"error": "bad json"}
        return True, data
