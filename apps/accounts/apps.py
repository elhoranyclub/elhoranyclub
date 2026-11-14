from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"

    def ready(self):
        """تفعّل قراءة صور آيفون (HEIC/HEIF) — Pillow مش بيقراها افتراضيًا."""
        try:
            from pillow_heif import register_heif_opener

            register_heif_opener()
        except Exception:  # الحزمة اختيارية — من غيرها JPG/PNG/WebP بيشتغلوا عادي
            pass
