"""Public pages — من نحن، المرافق، الأسعار، اللائحة، FAQ، تواصل معنا، اعرف الموقع أكتر."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import ContactForm
from .models import BoardMember, FAQ, Facility

GUIDE_DATA = Path(__file__).resolve().parent / "data" / "guide.json"

ROLE_LABELS = {
    "guest": "زائر",
    "member": "عضو",
    "dataentry": "مدخل بيانات",
    "admin": "الإدارة",
}


@lru_cache(maxsize=1)
def _guide_manifest() -> dict:
    """بيانات فيديوهات الأدوار (فصول + مدة) — بتتولّد مع الفيديوهات."""
    try:
        with open(GUIDE_DATA, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def guide_role(user) -> str:
    """دور المستخدم الحالي — بيحدد أي فيديو يتعرض.

    زائر → عضو → مدخل بيانات → إدارة.
    """
    if not getattr(user, "is_authenticated", False):
        return "guest"
    if user.is_superuser:
        return "admin"
    groups = set(user.groups.values_list("name", flat=True))
    if "أدمن" in groups:
        return "admin"
    if user.is_staff or "مدخل بيانات" in groups:
        return "dataentry"
    return "member"


def _safe_next(request, default="core:home"):
    """يمنع التحويل لدومين بره الموقع (open redirect)."""
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return reverse(default)


def guide_view(request):
    """الدليل التفاعلي — بيعرض أقسام دور المستخدم الحالي بس (فلترة على السيرفر)."""
    from .guide_content import ROLE_TITLES, sections_for

    role = guide_role(request.user)
    sections = sections_for(role)
    label = ROLE_LABELS.get(role, role)
    return render(request, "pages/guide.html", {
        "sections": sections,
        "role": role,
        "role_label": label,
        "title": ROLE_TITLES.get(role, "الدليل التفاعلي"),
        "intro": "دليل مصوّر بالموقع — كل اللي يخصك، خطوة بخطوة.",
        "meta_description": f"الدليل التفاعلي لمركز شباب الحوراني — {label}.",
    })


def learn_more(request):
    """صفحة «اعرف الموقع أكتر» — فيديو التدريب حسب دور المستخدم."""
    from apps.accounts.models import Profile

    profile = None
    if request.user.is_authenticated:
        profile = Profile.objects.filter(user=request.user).first()

    if request.method == "POST":
        if profile:
            profile.guide_seen = True
            profile.guide_seen_role = guide_role(request.user)
            profile.save(update_fields=["guide_seen", "guide_seen_role"])
        return redirect(_safe_next(request))

    role = guide_role(request.user)
    manifest = _guide_manifest()
    info = manifest.get(role, {})
    chapters = info.get("chapters", [])

    return render(request, "pages/learn_more.html", {
        "chapters": chapters,
        "role": role,
        "role_label": ROLE_LABELS.get(role, role),
        "video_role": role,
        "video_duration": info.get("duration", 0),
        "welcome": request.GET.get("welcome") == "1",
        "next": request.GET.get("next", ""),
        "meta_description": "فيديو يشرح موقع مركز شباب الحوراني: الحساب، كارت العضوية، تجديد الاشتراك، الحجز، وأدوات الإدارة.",
    })


@require_POST
def learn_more_done(request):
    """المستخدم خلّص الفيديو — نعلّمه إنه شاف الدليل ونوديه لصفحته."""
    from apps.accounts.models import Profile

    profile = Profile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    if profile and not profile.guide_seen:
        profile.guide_seen = True
        profile.guide_seen_role = guide_role(request.user)
        profile.save(update_fields=["guide_seen", "guide_seen_role"])
    return redirect(_safe_next(request))



def about(request):
    return render(request, "pages/about.html", {
        "board": BoardMember.objects.all(),
        "meta_description": "تعرف على تاريخ مركز شباب الحوراني، رؤيته ورسالته ومجلس إدارته.",
    })


def facilities(request):
    return render(request, "pages/facilities.html", {
        "facilities": Facility.objects.all(),
        "meta_description": "ملاعب وصالات وحمام سباحة مركز شباب الحوراني — مواعيد ومرافق.",
    })


def pricing(request):
    return render(request, "pages/pricing.html", {
        "meta_description": "أسعار اشتراكات مركز شباب الحوراني السنوية — فردي وأسرة (قريبًا).",
    })


def regulation(request):
    return render(request, "pages/regulation.html", {
        "meta_description": "لائحة مركز شباب الحوراني — القواعد والشروط وسياسات الإلغاء والاسترداد.",
    })


def faq(request):
    return render(request, "pages/faq.html", {
        "faqs": FAQ.objects.filter(is_active=True),
        "meta_description": "أسئلة شائعة عن العضوية والاشتراكات والبطولات والدورات في مركز الحوراني.",
    })


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "وصلتنا رسالتك — سنرد عليك في أقرب وقت.")
            return redirect("pages:contact")
    else:
        form = ContactForm()
    return render(request, "pages/contact.html", {
        "form": form,
        "meta_description": "تواصل مع مركز شباب الحوراني — هاتف، واتساب، بريد أو زيارتنا.",
    })
