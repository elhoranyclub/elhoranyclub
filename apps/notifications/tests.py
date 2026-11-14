"""Critical: template rendering, notify_user, unread badge, dashboard access, reminders, CSV."""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Profile, User
from apps.memberships.models import Membership, MembershipType
from apps.notifications.models import Notification, NotificationTemplate
from apps.notifications.services import notify_user, unread_count


def _user(phone="01055551001", name="مستلم"):
    u = User.objects.create_user(username=phone, phone=phone, password="pw#12345", is_active=True)
    Profile.objects.create(user=u, full_name_ar=name)
    return u


@pytest.mark.django_db
class TestNotify:
    def test_notify_renders_template(self):
        NotificationTemplate.objects.create(code="payment_confirmed", subject_ar="شكرًا {name}", body_ar="دفعتك {ref} اتأكدت")
        user = _user()
        created = notify_user(user=user, type="payment_confirmed", code="payment_confirmed", context={"name": "أحمد", "ref": "PAY-1"})
        assert created
        note = created[0]
        assert "أحمد" in note.subject and "PAY-1" in note.body
        assert unread_count(user) >= 1

    def test_mark_all_read(self, client):
        user = _user()
        notify_user(user=user, type="welcome", code=None, subject="أهلاً", body="أهلاً بيك")
        client.force_login(user)
        response = client.post(reverse("notifications:mark_all"))
        assert response.status_code == 302
        assert unread_count(user) == 0


@pytest.mark.django_db
class TestDashboard:
    def test_member_cannot_open_dashboard(self, client):
        user = _user()
        client.force_login(user)
        response = client.get(reverse("dashboard:home"))
        assert response.status_code in (302, 403)

    def test_staff_sees_dashboard(self, client):
        staff = _user("01055551002", "موظف")
        staff.is_staff = True
        staff.save()
        client.force_login(staff)
        response = client.get(reverse("dashboard:home"))
        assert response.status_code == 200

    def test_members_csv_exports(self, client):
        staff = _user("01055551003", "موظف")
        staff.is_staff = True
        staff.save()
        client.force_login(staff)
        response = client.get(reverse("dashboard:export_members"))
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]


@pytest.mark.django_db
class TestReminders:
    def test_reminders_create_notifications(self):
        from django.core.management import call_command
        from io import StringIO

        today = timezone.now().date()
        mtype = MembershipType.objects.create(name_ar="فردي", name_en="Ind", price=10, duration_months=12)
        user = _user("01055551004")
        Membership.objects.create(
            member=user, for_user=user, membership_type=mtype,
            start_date=today - timezone.timedelta(days=358), end_date=today + timezone.timedelta(days=7),
            status=Membership.Status.ACTIVE, base_amount=10, total_amount=10,
        )
        out = StringIO()
        call_command("send_renewal_reminders", days=7, stdout=out)
        assert user.notifications.filter(type="membership_expiring").exists()
