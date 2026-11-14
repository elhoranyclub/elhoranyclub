"""Grant all accounts-app permissions to the «أدمن» group, so the member screens
(«حسابات الأعضاء» / «سجل الدفتر») show up for the club manager role inside /manage/.

No-op when the group doesn't exist (fresh installs).
"""
from django.db import migrations


def grant_admin_accounts_perms(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    try:
        group = Group.objects.get(name="أدمن")
    except Group.DoesNotExist:
        return
    perms = Permission.objects.filter(content_type__app_label="accounts")
    group.permissions.add(*perms)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_membershipnumbercounter_profile_assembly_position_and_more"),
    ]

    operations = [
        migrations.RunPython(grant_admin_accounts_perms, migrations.RunPython.noop),
    ]
