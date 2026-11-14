"""
Manage — محرك إدارة داخلي بسيط على الموديلات، بصلاحية Django (view/add/change/delete).

- لا حاجة لشاشة مخصصة لكل موديل — سجل واحد في MANAGE_REGISTRY لكل موديل.
- كل اللينكات بتختفي تلقائيًا حسب الصلاحيات.
- كل شاشة بتطلب: view (لعرض) و add (للإنشاء) و change (للتعديل) و delete (للحذف).
"""
from __future__ import annotations

from dataclasses import dataclass

from django.apps import apps


@dataclass(frozen=True)
class ManageCfg:
    app_label: str
    model_name: str          # lower-case model name
    emoji: str = "📦"
    list_display: tuple = ()
    list_filter: tuple = ()
    search_fields: tuple = ()
    ordering: tuple = ()
    exclude_fields: tuple = ("created_at", "updated_at")
    readonly_fields: tuple = ()
    quick_note: str = ""


REGISTRY: dict[str, ManageCfg] = {
    # ---------------- الأخبار ----------------
    "news.newsarticle": ManageCfg("news", "newsarticle", "📰",
        list_display=("title", "category", "status", "is_featured", "published_at"),
        list_filter=("status", "is_featured"),
        search_fields=("title", "title_en", "summary"),
        ordering=("-published_at",),
        readonly_fields=("author",),
    ),
    "news.newsimage": ManageCfg(
        "news", "newsimage", "🖼️",
        list_display=("article", "caption", "order"),
        search_fields=("article__title", "caption"),
        readonly_fields=("article",),
    ),
    "news.newscategory": ManageCfg("news", "newscategory", "🏷️",
        list_display=("name_ar", "slug"),
        search_fields=("name_ar", "name_en"),
    ),
    "news.tag": ManageCfg("news", "tag", "🏷️",
        list_display=("name",),
        search_fields=("name",),
    ),
    # ---------------- الأنشطة ----------------
    "events.event": ManageCfg("events", "event", "🗓️",
        list_display=("title", "start_at", "status", "capacity", "price"),
        list_filter=("status",),
        search_fields=("title", "title_en", "location"),
        ordering=("-start_at",),
        readonly_fields=("created_by",),
    ),
    "events.eventregistration": ManageCfg("events", "eventregistration", "📝",
        list_display=("user", "event", "status", "created_at"),
        list_filter=("status",),
        ordering=("-created_at",),
        readonly_fields=("user", "event"),
    ),
    # ---------------- الدورات ----------------
    "courses.course": ManageCfg("courses", "course", "📚",
        list_display=("name", "sport", "level", "status", "start_date", "price"),
        list_filter=("status", "level", "gender"),
        search_fields=("name", "name_en", "schedule", "location"),
        ordering=("-created_at",),
        readonly_fields=("coach",),
    ),
    "courses.coursegroup": ManageCfg("courses", "coursegroup", "👥",
        list_display=("course", "name", "capacity"),
        search_fields=("course__name", "name"),
        ordering=("name",),
        readonly_fields=("coach",),
    ),
    "courses.courseenrollment": ManageCfg("courses", "courseenrollment", "📝",
        list_display=("beneficiary_name", "course", "status", "reference", "created_at"),
        list_filter=("status",),
        search_fields=("reference", "course__name", "member__phone"),
        ordering=("-created_at",),
        readonly_fields=("course", "group", "member", "for_user", "for_dependent", "reference", "fee_amount"),
    ),
    "courses.attendance": ManageCfg("courses", "attendance", "✅",
        list_display=("enrollment", "session_date", "present"),
        list_filter=("present", "session_date"),
        search_fields=("enrollment__course__name", "enrollment__member__phone"),
        ordering=("-session_date",),
        readonly_fields=("enrollment", "marked_by"),
    ),
    "courses.courseevaluation": ManageCfg("courses", "courseevaluation", "⭐",
        list_display=("enrollment", "coach", "rating", "created_at"),
        list_filter=("rating",),
        ordering=("-created_at",),
    ),
    "courses.certificate": ManageCfg("courses", "certificate", "📜",
        list_display=("recipient_name", "number", "issued_at"),
        search_fields=("number", "enrollment__member__phone"),
        ordering=("-issued_at",),
        readonly_fields=("enrollment",),
    ),
    # ---------------- الرحلات ----------------
    "trips.trip": ManageCfg("trips", "trip", "✈️",
        list_display=("name", "trip_date", "destination", "status", "capacity", "member_price"),
        list_filter=("status",),
        search_fields=("name", "name_en", "destination"),
        ordering=("-trip_date",),
    ),
    "trips.tripbooking": ManageCfg("trips", "tripbooking", "🎟️",
        list_display=("reference", "trip", "booked_by", "status", "passengers_count", "total_amount"),
        list_filter=("status",),
        search_fields=("reference", "booked_by__phone", "trip__name"),
        ordering=("-created_at",),
        readonly_fields=("trip", "booked_by", "reference"),
    ),
    "trips.trippassenger": ManageCfg("trips", "trippassenger", "🧍",
        list_display=("full_name", "booking", "relation", "age", "present"),
        search_fields=("full_name", "booking__reference"),
        readonly_fields=("booking",),
    ),
    "trips.guardianconsent": ManageCfg("trips", "guardianconsent", "✍️",
        list_display=("passenger", "signature_name", "agreed_at"),
        search_fields=("passenger__full_name", "signature_name"),
        readonly_fields=("passenger", "booking", "guardian", "agreed_at", "ip_address"),
    ),
    # ---------------- البطولات ----------------
    "tournaments.sport": ManageCfg("tournaments", "sport", "🏅",
        list_display=("id", "name_en", "is_team_sport", "order"),
        search_fields=("name_en",),
        ordering=("order",),
    ),
    "tournaments.tournament": ManageCfg("tournaments", "tournament", "🏆",
        list_display=("name", "sport", "status", "start_date", "max_teams", "entry_fee"),
        list_filter=("status", "sport"),
        search_fields=("name", "name_en"),
        ordering=("-start_date",),
    ),
    "tournaments.tournamentcategory": ManageCfg("tournaments", "tournamentcategory", "🗂️",
        list_display=("tournament", "name_ar", "gender", "entry_fee"),
        list_filter=("gender",),
        search_fields=("tournament__name", "name_ar", "name_en"),
    ),
    "tournaments.team": ManageCfg("tournaments", "team", "👥",
        list_display=("name", "category", "captain", "coach_name"),
        search_fields=("name", "category__tournament__name"),
    ),
    "tournaments.teammember": ManageCfg("tournaments", "teammember", "🧍",
        list_display=("player", "team", "jersey_number", "position"),
        search_fields=("team__name", "player__phone", "dependent__full_name_ar"),
    ),
    "tournaments.tournamentregistration": ManageCfg("tournaments", "tournamentregistration", "📝",
        list_display=("reference", "tournament", "registered_by", "kind", "status", "created_at"),
        list_filter=("status", "kind"),
        search_fields=("reference", "registered_by__phone", "tournament__name"),
        ordering=("-created_at",),
        readonly_fields=("tournament", "category", "registered_by", "team", "player", "dependent", "reference", "fee_amount"),
    ),
    "tournaments.match": ManageCfg("tournaments", "match", "⚽",
        list_display=("tournament", "category", "team_a", "team_b", "scheduled_at", "status", "score_a", "score_b"),
        list_filter=("status", "tournament"),
        search_fields=("tournament__name", "team_a__name", "team_b__name"),
        ordering=("scheduled_at",),
    ),
    "tournaments.standing": ManageCfg("tournaments", "standing", "📊",
        list_display=("category", "team", "played", "points", "goal_difference"),
        search_fields=("team__name", "category__tournament__name"),
        ordering=("-points",),
    ),
    "tournaments.matchgoal": ManageCfg("tournaments", "matchgoal", "🥅",
        list_display=("match", "team", "scorer", "minute", "is_own_goal"),
        search_fields=("match__tournament__name", "scorer__phone", "scorer_name"),
    ),
    # ---------------- العضويات ----------------
    "memberships.membershiptype": ManageCfg("memberships", "membershiptype", "🪪",
        list_display=("name_ar", "price", "duration_months", "is_active", "order"),
        list_filter=("is_active",),
        search_fields=("name_ar", "name_en"),
        ordering=("order",),
    ),
    "memberships.coupon": ManageCfg("memberships", "coupon", "🎟️",
        list_display=("code", "kind", "value", "valid_from", "valid_to", "used_count", "is_active"),
        list_filter=("kind", "is_active"),
        search_fields=("code",),
        ordering=("-valid_from",),
    ),
    "memberships.membership": ManageCfg("memberships", "membership", "💳",
        list_display=("reference", "member", "membership_type", "status", "start_date", "end_date", "total_amount"),
        list_filter=("status", "membership_type"),
        search_fields=("reference", "member__phone", "member__first_name"),
        ordering=("-created_at",),
        readonly_fields=("member", "for_user", "for_dependent", "reference", "membership_type", "coupon"),
    ),
    "memberships.membershiprenewal": ManageCfg("memberships", "membershiprenewal", "🔁",
        list_display=("membership", "initiator", "note", "created_at"),
        search_fields=("membership__reference", "initiator__phone"),
        ordering=("-created_at",),
        readonly_fields=("membership", "initiator"),
    ),
    "memberships.couponredemption": ManageCfg("memberships", "couponredemption", "🧾",
        list_display=("coupon", "membership", "user", "discount_amount", "created_at"),
        ordering=("-created_at",),
        readonly_fields=("coupon", "membership", "user"),
    ),
    # ---------------- المدفوعات ----------------
    "payments.payment": ManageCfg("payments", "payment", "💳",
        list_display=("reference", "member", "kind", "method", "status", "amount", "created_at"),
        list_filter=("status", "kind", "method"),
        search_fields=("reference", "member__phone", "provider_ref", "membership__membership_type__name_ar"),
        ordering=("-created_at",),
        readonly_fields=("member", "membership", "tournament_registration", "course_enrollment", "trip_booking", "reference", "provider", "provider_ref", "provider_payload", "paid_at"),
        quick_note="لتأكيد الدفع كاش/إيصالات استخدم «مراجعة المدفوعات»",
    ),
    "payments.paymentproof": ManageCfg("payments", "paymentproof", "🧾",
        list_display=("payment", "amount_claimed", "operation_number", "status", "created_at"),
        list_filter=("status",),
        search_fields=("payment__reference", "payment__member__phone", "operation_number"),
        ordering=("-created_at",),
        readonly_fields=("payment", "reviewer", "reviewed_at"),
        quick_note="مراجعة وقبول/رفض الإيصالات من هنا أو من «مراجعة المدفوعات»",
    ),
    "payments.refund": ManageCfg("payments", "refund", "💸",
        list_display=("payment", "amount", "reason", "created_by", "created_at"),
        search_fields=("payment__reference", "payment__member__phone"),
        ordering=("-created_at",),
        readonly_fields=("payment", "created_by"),
    ),
    "payments.invoice": ManageCfg("payments", "invoice", "🧾",
        list_display=("number", "payment", "issued_at"),
        search_fields=("number", "payment__reference"),
        ordering=("-issued_at",),
        readonly_fields=("payment", "number", "issued_at"),
    ),
    # ---------------- الأعضاء ----------------
    "accounts.profile": ManageCfg("accounts", "profile", "🪪",
        list_display=("membership_number", "full_name_ar", "user__phone", "national_id_masked", "is_general_assembly", "assembly_position"),
        list_filter=("is_general_assembly",),
        search_fields=("membership_number", "full_name_ar", "user__phone", "national_id"),
        ordering=("-joined_at",),
        readonly_fields=("membership_number", "user", "joined_at", "created_at", "updated_at"),
        exclude_fields=("photo", "birth_date", "gender", "governorate", "address", "national_id", "health_notes", "shirt_size", "emergency_contact_name", "emergency_contact_phone", "full_name_en"),
        quick_note="ضع/أزل علامة عضوية «اللجنة العمومية» واكتب المنصب — دول بس اللي بيتغيروا من هنا",
    ),
    "accounts.memberregistry": ManageCfg("accounts", "memberregistry", "📒",
        list_display=("membership_number", "full_name_ar", "national_id", "is_general_assembly", "paid_until", "linked_profile"),
        list_filter=("is_general_assembly",),
        search_fields=("membership_number", "full_name_ar", "national_id"),
        ordering=("membership_number",),
        readonly_fields=("linked_profile",),
        quick_note="سجلات الدفتر الورقية — الربط بحساب مسجل بيتم من: /manage/registry/",
    ),
    # ---------------- صفحات وعناوين ----------------
    "pages.facility": ManageCfg("pages", "facility", "🏟️",
        list_display=("id", "name_en", "hours", "order"),
        search_fields=("name_ar", "name_en"),
        ordering=("order",),
    ),
    "pages.boardmember": ManageCfg("pages", "boardmember", "👔",
        list_display=("id", "name_en", "role_ar", "order"),
        search_fields=("name_ar", "name_en", "role_ar"),
        ordering=("order",),
    ),
    "pages.faq": ManageCfg("pages", "faq", "❓",
        list_display=("question_ar", "order", "is_active"),
        list_filter=("is_active",),
        search_fields=("question_ar", "question_en", "answer_ar"),
        ordering=("order",),
    ),
    "pages.contactmessage": ManageCfg("pages", "contactmessage", "📨",
        list_display=("id", "subject", "email", "phone", "is_read", "created_at"),
        list_filter=("is_read",),
        search_fields=("subject", "message", "email", "phone"),
        ordering=("-created_at",),
        readonly_fields=("created_at",),
    ),
    # ---------------- الإشعارات ----------------
    "notifications.notificationtemplate": ManageCfg("notifications", "notificationtemplate", "🧩",
        list_display=("code", "subject_ar", "is_active"),
        list_filter=("is_active",),
        search_fields=("code", "subject_ar", "subject_en"),
    ),
    "notifications.notification": ManageCfg("notifications", "notification", "🔔",
        list_display=("user", "type", "channel", "subject", "read", "created_at"),
        list_filter=("type", "channel", "read"),
        search_fields=("user__phone", "subject"),
        ordering=("-created_at",),
        readonly_fields=("user",),
    ),
}

def model_cfg(app_label: str, model_name: str) -> ManageCfg | None:
    return REGISTRY.get(f"{app_label}.{model_name}")


def model_for(cfg: ManageCfg):
    return apps.get_model(cfg.app_label, cfg.model_name)


def perms_for(user, cfg: ManageCfg) -> dict[str, bool]:
    base = f"{cfg.app_label}.{{action}}_{cfg.model_name}"
    return {
        "view": user.has_perm(base.format(action="view")),
        "add": user.has_perm(base.format(action="add")),
        "change": user.has_perm(base.format(action="change")),
        "delete": user.has_perm(base.format(action="delete")),
    }


def manageable_models_for(user) -> list[tuple[ManageCfg, object]]:
    """كل الموديلز اللي المستخدم عنده أي صلاحية عليها — مترتبة حسب المجموعة."""
    result = []
    for cfg in REGISTRY.values():
        model = model_for(cfg)
        perms = perms_for(user, cfg)
        if any(perms.values()):
            result.append((cfg, model, perms))
    return result


def grouped_manageable_for(user):
    """per-group list of plain context dicts (templates can't use model._meta)."""
    all_ = manageable_models_for(user)
    by_app: dict[str, list] = {}
    for cfg, model, perms in all_:
        by_app.setdefault(cfg.app_label, []).append({
            "emoji": cfg.emoji,
            "label": str(model._meta.verbose_name_plural),
            "app": cfg.app_label,
            "model": cfg.model_name,
            "perms": perms,
        })
    groups = {
        "📚 المحتوى والنشر": ["news", "events", "courses", "trips"],
        "🏆 البطولات والمعارض": ["tournaments", "gallery"],
        "🪪 الاشتراكات والمدفوعات": ["memberships", "payments", "accounts"],
        "📄 صفحات الموقع ورسائل الجمهور": ["pages", "notifications"],
    }
    out = []
    for title, apps_ in groups.items():
        items = [item for app in apps_ for item in by_app.get(app, [])]
        if items:
            out.append((title, items))
    return out
