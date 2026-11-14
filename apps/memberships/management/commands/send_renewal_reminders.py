"""
تذكيرات انتهاء الاشتراك — تنشئ إشعارات حقيقية لكل عضو يقرب اشتراكه على الانتهاء.
    python manage.py send_renewal_reminders            # 30 و 7 و 1 يوم
    python manage.py send_renewal_reminders --days 7
شغّل عبر cron يوميًا (المرحلة 10: جدولة على السيرفر).
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.memberships.models import Membership
from apps.notifications.services import notify_user

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "أنشئ إشعارات تذكير للاشتراكات التي ستنتهي خلال N يوم."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None, help="يوم واحد فقط (افتراضي: 30, 7, 1)")

    def handle(self, *args, **options):
        today = timezone.now().date()
        day_sets = [options["days"]] if options["days"] else [30, 7, 1]
        total = 0
        for days in day_sets:
            target = today + timezone.timedelta(days=days)
            expiring = Membership.objects.filter(status=Membership.Status.ACTIVE, end_date=target).select_related(
                "member", "membership_type", "for_dependent"
            )
            for membership in expiring:
                notify_user(
                    user=membership.member,
                    type="membership_expiring",
                    code=f"renewal_{days}",
                    context={
                        "name": membership.member.get_full_name() or membership.member.phone,
                        "days": days,
                        "end_date": membership.end_date,
                        "type": membership.membership_type.name_ar,
                    },
                    action_url="/memberships/renew/",
                )
                total += 1
                self.stdout.write(f"[تذكير {days} يوم] {membership.member.phone} — ينتهي {membership.end_date}")
        if total == 0:
            self.stdout.write("لا توجد اشتراكات تنتهي في الأيام المحددة.")
