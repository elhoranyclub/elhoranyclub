"""Security headers — CSP عملي متوافق مع الحزم الخارجية الحالية.

مهم: Alpine.js بيقيّم تعبيراته بـ eval — فلازم 'unsafe-eval' في script-src.
من غيرها: Alpine مش بيشتغل، فتبقى الرسالة العالقة (تثبيت التطبيق) مش بتتقفل
والقائمة الكاملة مش بتتفتح.
"""
from django.conf import settings

CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
    "font-src 'self' https://fonts.gstatic.com; "
    # 'unsafe-eval' مطلوب لـ Alpine.js · 'unsafe-inline' للسكريبتات المدمجة
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com; "
    "connect-src 'self'; "
    "frame-src https://maps.google.com https://www.google.com; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if settings.DEBUG:
            return response
        response.setdefault("Content-Security-Policy", CSP)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response
