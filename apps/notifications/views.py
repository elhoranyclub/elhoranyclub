"""Notifications views — قائمة + تفضيلات القنوات + تحديد كمقروء."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import NotificationPreferenceForm
from .models import Notification, NotificationPreference
from .services import mark_all_read


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by("-sent_at")[:100]
    return render(request, "notifications/list.html", {"notifications": notifications})


@login_required
def preferences(request):
    pref, _created = NotificationPreference.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = NotificationPreferenceForm(request.POST, instance=pref)
        if form.is_valid():
            form.save()
            messages.success(request, _("تم حفظ تفضيلات إشعاراتك."))
            return redirect("notifications:preferences")
    else:
        form = NotificationPreferenceForm(instance=pref)
    return render(request, "notifications/preferences.html", {"form": form})


@login_required
@require_POST
def mark_read(request, notification_id: int):
    Notification.objects.filter(pk=notification_id, user=request.user).update(read=True)
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all(request):
    count = mark_all_read(request.user)
    messages.success(request, _("تم تحديد %(n)s إشعارًا كمقروء.") % {"n": count})
    return redirect("notifications:list")
