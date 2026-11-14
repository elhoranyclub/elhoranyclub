"""
Payment gateway abstraction.
كل مزود (Paymob / Fawry / mock) ينفذ نفس الواجهة — الخدمات لا تتعامل إلا معها.
"""
from __future__ import annotations

import abc


class GatewayNotConfigured(Exception):
    """المزود المختار غير مهيأ (مفاتيح ناقصة)."""


class PaymentGateway(abc.ABC):
    """عقد موحد بين التطبيق وأي بوابة دفع."""

    name: str = "abstract"

    @abc.abstractmethod
    def create_checkout(self, payment) -> dict:
        """
        يبدأ عملية الدفع لدى المزود.
        ترجع dict مثل: {"kind": "redirect", "url": "https://..."} أو {"kind": "mock", "token": "..."}
        """

    @abc.abstractmethod
    def verify_webhook(self, headers, body: bytes) -> tuple[bool, dict]:
        """تحقق من توقيع الـ webhook (HMAC). ترجع (صالح؟, البيانات)."""


def get_gateway(name: str | None = None) -> PaymentGateway:
    from django.conf import settings

    from .mock import MockGateway
    from .paymob import PaymobGateway

    provider = (name or getattr(settings, "PAYMENT_PROVIDER", "mock")).lower()
    if provider == "paymob":
        return PaymobGateway()
    return MockGateway()
