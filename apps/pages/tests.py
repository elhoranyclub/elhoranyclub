"""Contact form persists a message + صفحة «اعرف الموقع أكتر»."""
import pytest
from django.urls import reverse

from apps.pages.models import ContactMessage


@pytest.mark.django_db
def test_contact_form_saves_message(client):
    response = client.post(reverse("pages:contact"), {
        "name": "عميل تجريبي",
        "phone": "01012345678",
        "email": "",
        "subject": "استفسار عن الاشتراك",
        "message": "عايز أعرف مواعيد التجديد",
    })
    assert response.status_code == 302
    assert ContactMessage.objects.filter(phone="01012345678", is_read=False).exists()


@pytest.mark.django_db
def test_guide_page_is_filtered_by_role(client):
    """الدليل التفاعلي — كل دور بياخد أقسامه بس (فلترة على السيرفر)."""
    from django.contrib.auth.models import Group

    from apps.accounts.models import Profile, User

    # زائر
    body = client.get(reverse("pages:guide")).content.decode()
    assert "القوائم الإدارية" not in body
    assert "مدخل بيانات" not in body
    assert "الإدارة" not in body

    # عضو
    member = User.objects.create_user(username="01222222230", phone="01222222230", password="x", is_active=True)
    Profile.objects.create(user=member, full_name_ar="عضو")
    client.force_login(member)
    body = client.get(reverse("pages:guide")).content.decode()
    assert "كارت العضوية" in body
    assert "القوائم الإدارية" not in body

    # مدخل بيانات
    dataentry, _ = Group.objects.get_or_create(name="مدخل بيانات")
    staff = User.objects.create_user(username="01222222231", phone="01222222231", password="x", is_active=True)
    staff.is_staff = True
    staff.save()
    staff.groups.add(dataentry)
    Profile.objects.create(user=staff, full_name_ar="موظف")
    client.force_login(staff)
    body = client.get(reverse("pages:guide")).content.decode()
    assert "القوائم الإدارية" in body
    assert "حسابات التجربة" not in body   # قسم الإدارة بس
    assert "قبل النشر" not in body

    # الإدارة — تشوف الكل
    admin = User.objects.create_user(username="01222222232", phone="01222222232", password="x",
                                     is_active=True, is_staff=True, is_superuser=True)
    Profile.objects.create(user=admin, full_name_ar="مدير")
    client.force_login(admin)
    body = client.get(reverse("pages:guide")).content.decode()
    assert "القوائم الإدارية" in body
    assert "حسابات التجربة" in body
    assert "قبل النشر" in body


@pytest.mark.django_db
def test_learn_more_page_is_public_and_has_video(client):
    response = client.get(reverse("pages:learn_more"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "guide-video" in body
    # زائر = فيديو الزائر
    assert "guide/video/guest/" in body


@pytest.mark.django_db
def test_guide_video_changes_with_role(client):
    """كل دور يشوف الفيديو بتاعه — والصفحة بتتغيّر بتغيّر الصلاحية."""
    from apps.accounts.models import Profile, User
    from django.contrib.auth.models import Group

    dataentry, _ = Group.objects.get_or_create(name="مدخل بيانات")
    user = User.objects.create_user(username="01222222223", phone="01222222223", password="x", is_active=True)
    user.is_staff = True
    user.save()
    user.groups.add(dataentry)
    Profile.objects.create(user=user, full_name_ar="موظف")

    client.force_login(user)
    body = client.get(reverse("pages:learn_more")).content.decode()
    assert "guide/video/dataentry/" in body

    # سوبر أدمن
    admin = User.objects.create_user(username="01222222224", phone="01222222224", password="x",
                                     is_active=True, is_staff=True, is_superuser=True)
    Profile.objects.create(user=admin, full_name_ar="مدير")
    client.force_login(admin)
    body = client.get(reverse("pages:learn_more")).content.decode()
    assert "guide/video/admin/" in body

    # عضو عادي
    member = User.objects.create_user(username="01222222225", phone="01222222225", password="x", is_active=True)
    Profile.objects.create(user=member, full_name_ar="عضو")
    client.force_login(member)
    body = client.get(reverse("pages:learn_more")).content.decode()
    assert "guide/video/member/" in body


@pytest.mark.django_db
def test_first_login_redirects_to_guide_then_marks_seen(client):
    from apps.accounts.models import Profile, User

    user = User.objects.create_user(username="01111111111", phone="01111111111", password="Demo@12345")
    profile = Profile.objects.create(user=user, full_name_ar="عضو تجريبي")
    assert profile.guide_seen is False

    response = client.post(reverse("accounts:login"), {"phone": "01111111111", "password": "Demo@12345"})
    assert response.status_code == 302
    assert response.url.startswith(reverse("pages:learn_more"))

    # بعد ما يقفل الدليل — الدخول التاني يروح عادي
    profile.refresh_from_db()
    profile.guide_seen = True
    profile.guide_seen_role = "member"
    profile.save(update_fields=["guide_seen", "guide_seen_role"])
    client.logout()
    response = client.post(reverse("accounts:login"), {"phone": "01111111111", "password": "Demo@12345"})
    assert response.url == reverse("core:home")


@pytest.mark.django_db
def test_role_change_shows_new_guide_again(client):
    """لو صلاحية العضو اتغيّرت (عضو → مدخل بيانات) — الفيديو الجديد يظهر تاني."""
    from django.contrib.auth.models import Group

    from apps.accounts.models import Profile, User

    user = User.objects.create_user(username="01111111112", phone="01111111112", password="Demo@12345")
    profile = Profile.objects.create(user=user, full_name_ar="عضو", guide_seen=True, guide_seen_role="member")

    # نفس الصلاحية → مفيش تحويل
    client.post(reverse("accounts:login"), {"phone": "01111111112", "password": "Demo@12345"})
    client.logout()
    response = client.post(reverse("accounts:login"), {"phone": "01111111112", "password": "Demo@12345"})
    assert response.url == reverse("core:home")

    # اترقّى لـ مدخل بيانات → الفيديو الجديد يظهر
    dataentry, _ = Group.objects.get_or_create(name="مدخل بيانات")
    user.is_staff = True
    user.save()
    user.groups.add(dataentry)
    client.logout()
    response = client.post(reverse("accounts:login"), {"phone": "01111111112", "password": "Demo@12345"})
    assert response.url.startswith(reverse("pages:learn_more"))
    body = client.get(reverse("pages:learn_more")).content.decode()
    assert "guide/video/dataentry/" in body


@pytest.mark.django_db
def test_guide_done_marks_profile_and_redirects_safely(client):
    from apps.accounts.models import Profile, User

    user = User.objects.create_user(username="01222222222", phone="01222222222", password="Demo@12345")
    Profile.objects.create(user=user, full_name_ar="عضو تجريبي")
    client.force_login(user)

    response = client.post(reverse("pages:learn_more_done"), {"next": "/accounts/card/"})
    assert response.status_code == 302
    assert response.url == "/accounts/card/"
    assert Profile.objects.get(user=user).guide_seen is True

    # منفذ التحويل لدومين بره الموقع — لازم يتمنع
    response = client.post(reverse("pages:learn_more_done"), {"next": "https://evil.example.com/"})
    assert response.url == reverse("core:home")
