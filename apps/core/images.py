# -*- coding: utf-8 -*-
"""تعديلات موحّدة على رفع الصور: رسائل خطأ مفهومة + حد حجم + دعم HEIC (آيفون)."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

MAX_PHOTO_MB = 5
# الصيغ المقبولة: JPG/PNG/WebP + HEIC (صور آيفون)
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
    "image/heic-sequence": "heic",
    "image/heif-sequence": "heif",
}


def clean_photo(photo):
    """يتحقق إن الملف صورة فعلًا وحجمه معقول — برسالة عربية واضحة."""
    if not photo:
        return photo

    size_mb = getattr(photo, "size", 0) / (1024 * 1024)
    if size_mb > MAX_PHOTO_MB:
        raise ValidationError(
            _("الصورة كبيرة أوي (%(size)d ميجا) — الحد %(max)d ميجا. صغّر الصورة أو صوّرها تاني.") % {
                "size": round(size_mb, 1),
                "max": MAX_PHOTO_MB,
            }
        )

    content_type = (getattr(photo, "content_type", "") or "").lower()
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(
            _("الصورة لازم تكون JPG أو PNG أو WebP (أو HEIC لو صورتك من آيفون).")
        )

    # نتأكد إن Pillow بيقراها فعلًا (بيطلع خطأ واضح لو الملف تالف أو HEIC من غير دعم)
    try:
        from PIL import Image

        photo.seek(0)
        with Image.open(photo) as im:
            im.verify()
        photo.seek(0)
    except ValidationError:
        raise
    except Exception:
        raise ValidationError(
            _("مش قادر يقرأ الصورة دي. جرّب صورة تانية، أو لو دي من آيفون اعملها «أصغر» الأول.")
        )

    return photo
