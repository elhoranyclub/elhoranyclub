"""صلاحيات أدوار الموظفين — عزل أدمن عن مدخل البيانات عن السوبر أدمن."""
import pytest
from django.core.management import call_command
from django.contrib.auth.models import Permission

from apps.accounts.models import User


@pytest.fixture
def roles(db):
    call_command("setup_roles")
    return True


def _user_with_group(name, username, phone, is_superuser=False):
    u = User.objects.create_user(username=username, phone=phone, password="Test#2026pass", is_active=True)
    u.is_staff = True
    u.is_superuser = is_superuser
    u.save()
    from django.contrib.auth.models import Group
    u.groups.add(Group.objects.get(name=name))
    return u


@pytest.mark.django_db
def test_super_admin_has_everything(roles):
    u = _user_with_group("أدمن", "su9", "01077770001", is_superuser=True)
    assert u.has_perm("auth.change_user")
    assert u.has_perm("core.change_sitesettings")
    assert u.has_perm("payments.delete_payment")


@pytest.mark.django_db
def test_admin_group_permissions(roles):
    u = _user_with_group("أدمن", "adm9", "01077770002")
    # content: full access on news
    assert u.has_perm("news.change_newsarticle")
    assert u.has_perm("news.delete_newsarticle")
    # payments: review but no delete
    assert u.has_perm("payments.change_payment")
    assert not u.has_perm("payments.delete_payment")
    assert not u.has_perm("memberships.delete_membership")
    # NOT users/settings
    assert not u.has_perm("auth.change_user")
    assert not u.has_perm("accounts.change_user")
    assert not u.has_perm("core.change_sitesettings")
    assert not u.has_perm("core.change_auditlog")


@pytest.mark.django_db
def test_data_clerk_permissions(roles):
    u = _user_with_group("مدخل بيانات", "clk9", "01077770003")
    # content access
    assert u.has_perm("news.add_newsarticle")
    assert u.has_perm("news.change_newsarticle")
    assert u.has_perm("events.add_event")
    assert u.has_perm("trips.add_trip")
    assert u.has_perm("tournaments.change_match")
    # memberships & payments review
    assert u.has_perm("memberships.change_membership")
    assert u.has_perm("payments.change_paymentproof")
    assert u.has_perm("payments.view_payment")
    # delete ONLY gallery
    assert u.has_perm("gallery.delete_mediaitem")
    assert u.has_perm("gallery.delete_galleryalbum")
    # cannot delete content or money
    assert not u.has_perm("news.delete_newsarticle")
    assert not u.has_perm("events.delete_event")
    assert not u.has_perm("payments.delete_payment")
    assert not u.has_perm("memberships.delete_membership")
    # no users/settings/audit
    assert not u.has_perm("auth.change_user")
    assert not u.has_perm("core.change_sitesettings")
    assert not u.has_perm("core.change_auditlog")
    # cannot add settings or invoices
    assert not u.has_perm("payments.add_invoice")


@pytest.mark.django_db
def test_clerk_is_not_admin(roles):
    u = _user_with_group("مدخل بيانات", "clk8", "01077770004")
    from django.contrib.auth.models import Group
    assert list(u.groups.values_list("name", flat=True)) == ["مدخل بيانات"]


@pytest.mark.django_db
def test_setup_roles_is_idempotent(roles):
    call_command("setup_roles")  # running twice must not error or duplicate group names
    from django.contrib.auth.models import Group
    assert Group.objects.filter(name="مدخل بيانات").count() == 1
    assert Group.objects.filter(name="أدمن").count() == 1
