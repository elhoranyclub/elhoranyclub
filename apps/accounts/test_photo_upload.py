# -*- coding: utf-8 -*-
"""اختبارات رفع الصور: HEIC (آيفون) · الحجم · الملفات المش صورة."""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.images import MAX_PHOTO_MB, clean_photo


def _png(size=(8, 8)):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, (200, 40, 40)).save(buf, "PNG")
    return buf.getvalue()


def test_valid_image_passes():
    f = SimpleUploadedFile("p.png", _png(), content_type="image/png")
    assert clean_photo(f) is f


def test_plain_text_rejected_with_arabic_message():
    f = SimpleUploadedFile("p.png", b"this is not an image", content_type="image/png")
    with pytest.raises(ValidationError) as e:
        clean_photo(f)
    assert "مش قادر يقرأ الصورة" in str(e.value)


def test_oversized_image_rejected():
    import io

    from PIL import Image

    buf = io.BytesIO()
    # ضجيج عشوائي — ملوش ضغط، فحجمه كبير فعلًا
    noise = Image.effect_noise((6000, 6000), 255).convert("RGB")
    noise.save(buf, "PNG", optimize=False, compress_level=0)
    data = buf.getvalue()
    f = SimpleUploadedFile("big.png", data, content_type="image/png")
    assert len(data) / 1_048_576 > MAX_PHOTO_MB, f"الحجم الفعلي {len(data)/1_048_576:.1f} MB"
    with pytest.raises(ValidationError) as e:
        clean_photo(f)
    assert "الصورة كبيرة أوي" in str(e.value)


def test_unknown_content_type_rejected():
    f = SimpleUploadedFile("x.txt", _png(), content_type="text/plain")
    with pytest.raises(ValidationError) as e:
        clean_photo(f)
    assert "JPG أو PNG" in str(e.value)


@pytest.mark.django_db
def test_profile_form_accepts_iheic_heic_photo(client):
    """صورة HEIC (آيفون) لازم تتقبل — وده هو الموقف الحقيقي بتاع المستخدم."""
    import io

    from PIL import Image

    from django.contrib.auth import get_user_model

    from apps.accounts.models import Profile

    User = get_user_model()
    user = User.objects.create_user(username="01077770001", phone="01077770001", password="x")
    Profile.objects.create(user=user, full_name_ar="اختبار")
    client.force_login(user)

    from pillow_heif import register_heif_opener

    register_heif_opener()

    # HEIC حقيقي (Pillow بيولّده مع pillow-heif)
    heic_bytes = None
    try:
        buf = io.BytesIO()
        Image.new("RGB", (100, 100), (10, 200, 30)).save(buf, "HEIF")
        heic_bytes = buf.getvalue()
    except Exception:
        heic_bytes = None

    if not heic_bytes:
        pytest.skip("Pillow/heif مش قادر يولّد HEIC في البيئة دي")

    f = SimpleUploadedFile("photo.HEIC", heic_bytes, content_type="image/heic")
    from django.urls import reverse

    r = client.post(reverse("accounts:profile_edit"), {
        "full_name_ar": "اختبار", "full_name_en": "", "birth_date": "",
        "gender": "M", "national_id": "", "address": "", "governorate": "القاهرة",
        "shirt_size": "", "emergency_contact_name": "", "emergency_contact_phone": "",
        "health_notes": "", "photo": f,
    }, follow=True)
    assert r.status_code == 200
    body = r.content.decode()
    assert "مش قادر يقرأ الصورة" not in body
    assert "الصورة كبيرة أوي" not in body
    assert Profile.objects.get(user=user).photo.name


@pytest.mark.django_db
def test_profile_form_rejects_broken_photo_with_clear_message(client):
    from django.contrib.auth import get_user_model

    from django.urls import reverse

    from apps.accounts.models import Profile

    User = get_user_model()
    user = User.objects.create_user(username="01077770002", phone="01077770002", password="x")
    Profile.objects.create(user=user, full_name_ar="اختبار")
    client.force_login(user)

    f = SimpleUploadedFile("photo.jpg", b"not really a jpeg", content_type="image/jpeg")
    r = client.post(reverse("accounts:profile_edit"), {
        "full_name_ar": "اختبار", "full_name_en": "", "birth_date": "",
        "gender": "M", "national_id": "", "address": "", "governorate": "القاهرة",
        "shirt_size": "", "emergency_contact_name": "", "emergency_contact_phone": "",
        "health_notes": "", "photo": f,
    }, follow=True)
    body = r.content.decode()
    assert "رفع صورة صالحة" in body
